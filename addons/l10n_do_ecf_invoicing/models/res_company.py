import base64
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    # --- e-CF Company Configuration ---
    l10n_do_ecf_issuer = fields.Boolean(
        string="e-CF Issuer",
        help="Enable if this company is registered as an e-CF issuer with DGII.",
        default=False,
    )
    l10n_do_ecf_service_env = fields.Selection(
        selection=[
            ("certecf", "CerteCF (Certificación DGII)"),
            ("test", "Test (TesteCF)"),
            ("production", "Production"),
        ],
        string="e-CF Environment",
        default="certecf",
        help=(
            "CerteCF: Use during the DGII certification process (Pasos 1-15).\n"
            "TesteCF: Development/integration testing.\n"
            "Production: Live invoicing after certification is complete."
        ),
    )
    l10n_do_ecf_certificate = fields.Binary(
        string="e-CF Certificate (P12/PFX)",
        help="Upload your PKCS#12 (.p12 or .pfx) digital certificate.",
        attachment=True,
    )
    l10n_do_ecf_certificate_filename = fields.Char(
        string="Certificate Filename",
    )
    l10n_do_ecf_certificate_password = fields.Char(
        string="Certificate Password",
        help="Password for the P12/PFX certificate file.",
    )

    l10n_do_ecf_deferred_submissions = fields.Boolean(
        string="Deferred e-CF Submissions",
        default=False,
        help="If enabled, e-CF documents are queued and sent in deferred mode (IndicadorEnvioDiferido=1).",
    )
    l10n_do_ecf_auto_send_default = fields.Boolean(
        string="Enviar a DGII por defecto",
        default=False,
        help="Si está activado, las nuevas facturas se marcarán automáticamente para envío a DGII. Desactívalo para usar el sistema dual donde decides factura por factura.",
    )
    l10n_do_ecf_sequence_expiration_date = fields.Date(
        string="Fecha Vencimiento Secuencia e-CF",
        help="Fecha de vencimiento de la secuencia autorizada por DGII (FechaVencimientoSecuencia).",
    )

    def _get_l10n_do_ecf_endpoints(self):
        """Return a dict of DGII API endpoint URLs based on the configured environment.

        Environments:
          certecf    — DGII certification process (Pasos 1-15)
          test       — TesteCF development/integration
          production — Live production after certification

        URL structure from the official dgii-ecf npm package:
          Base: https://ecf.dgii.gov.do/{env}/...
          FC:   https://fc.dgii.gov.do/{env}/...   (for RFCE / E32 < 250K)
        """
        self.ensure_one()
        env = self.l10n_do_ecf_service_env or "certecf"

        env_map = {
            "certecf":    "CerteCF",
            "test":       "TesteCF",
            "production": "eCF",
        }
        env_path = env_map.get(env, "CerteCF")

        base = f"https://ecf.dgii.gov.do/{env_path}"
        fc_base = f"https://fc.dgii.gov.do/{env_path}"

        return {
            # GET  — returns seed XML to sign
            "auth_seed":     f"{base}/Autenticacion/api/Autenticacion/Semilla",
            # POST — returns JWT bearer token
            "auth_validate": f"{base}/autenticacion/api/Autenticacion/ValidarSemilla",
            # POST — send e-CF (all types except E32 < 250K)
            "send_ecf":      f"{base}/recepcion/api/FacturasElectronicas",
            # POST — send RFCE summary (E32 < 250K → different base domain)
            "send_rfce":     f"{fc_base}/recepcionfc/api/recepcion/ecf",
            # GET  — poll e-CF status by trackId
            "poll_status":   f"{base}/consultaresultado/api/Consultas/Estado",
        }

    # Keep backward-compat shim for any code still using _get_l10n_do_ecf_base_url
    def _get_l10n_do_ecf_base_url(self):
        self.ensure_one()
        env_map = {
            "certecf":    "CerteCF",
            "test":       "TesteCF",
            "production": "eCF",
        }
        env_path = env_map.get(self.l10n_do_ecf_service_env or "certecf", "CerteCF")
        return f"https://ecf.dgii.gov.do/{env_path}/"

    def _get_l10n_do_ecf_certificate_data(self):
        """Return the raw bytes of the P12 certificate and the password."""
        self.ensure_one()
        if not self.l10n_do_ecf_certificate:
            return None, None
        cert_bytes = base64.b64decode(self.l10n_do_ecf_certificate)
        password = (
            self.l10n_do_ecf_certificate_password.encode("utf-8")
            if self.l10n_do_ecf_certificate_password
            else None
        )
        return cert_bytes, password
