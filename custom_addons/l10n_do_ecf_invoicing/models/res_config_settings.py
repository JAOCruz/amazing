from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_do_ecf_service_env = fields.Selection(
        related="company_id.l10n_do_ecf_service_env",
        readonly=False,
    )
    l10n_do_ecf_certificate = fields.Binary(
        related="company_id.l10n_do_ecf_certificate",
        readonly=False,
    )
    l10n_do_ecf_certificate_filename = fields.Char(
        related="company_id.l10n_do_ecf_certificate_filename",
        readonly=False,
    )
    l10n_do_ecf_certificate_password = fields.Char(
        related="company_id.l10n_do_ecf_certificate_password",
        readonly=False,
    )

    def action_test_dgii_connection(self):
        """Test the DGII connection using the current certificate."""
        from odoo.exceptions import UserError
        self.ensure_one()

        if not self.company_id.l10n_do_ecf_certificate:
            raise UserError("❌ No hay certificado P12 configurado. Súbelo primero.")

        try:
            dgii_api = self.env["l10n_do.dgii.api"]
            token = dgii_api._authenticate(self.company_id)
        except ValueError as e:
            if "password" in str(e).lower() or "pkcs12" in str(e).lower():
                raise UserError(
                    "❌ Contraseña incorrecta o archivo P12 inválido.\n\n"
                    "Verifica que:\n"
                    "• La contraseña del certificado sea correcta\n"
                    "• El archivo sea un .p12 o .pfx válido emitido por DGII"
                ) from e
            raise UserError(f"❌ Error al leer el certificado: {e}") from e
        except Exception as e:
            raise UserError(
                f"❌ Error de conexión con DGII TesteCF:\n{str(e)}\n\n"
                "Verifica que Amazing Prosthetics esté habilitada como emisora e-CF en el portal DGII."
            ) from e

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "✅ Conexión DGII Exitosa",
                "message": "Autenticación con TesteCF completada. El certificado es válido.",
                "type": "success",
                "sticky": False,
            },
        }
