"""
Extends account.move with e-CF fields, XML generation, signing, and DGII submission.

This module is self-contained: all fiscal fields needed for e-CF are declared here.
Depends on l10n_latam_invoice_document (provides l10n_latam_document_type_id,
l10n_latam_document_number) and l10n_do (DR chart of accounts).
"""
import base64
import logging
from datetime import datetime
from urllib.parse import urlencode

from lxml import etree

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .ecf_xml_generator import NCF_TYPE_TO_CODE

_logger = logging.getLogger(__name__)

ECF_STATUS_SELECTION = [
    ("draft", "Draft"),
    ("generated", "XML Generated"),
    ("sent", "Sent to DGII"),
    ("accepted", "Accepted"),
    ("rejected", "Rejected"),
    ("error", "Error"),
]

# Map DGII response codes to our status
DGII_STATUS_MAP = {
    "Aceptado": "accepted",
    "AceptadoCondicional": "accepted",
    "Rechazado": "rejected",
    "EnProceso": "sent",
}


class AccountMove(models.Model):
    _inherit = "account.move"

    # --- Base e-CF fields (self-contained, no l10n_do_accounting needed) ---
    is_ecf_invoice = fields.Boolean(
        string="Is e-CF Invoice",
        compute="_compute_is_ecf_invoice",
        store=True,
        help="True if this invoice uses an electronic fiscal document (e-CF).",
    )
    l10n_do_ecf_security_code = fields.Char(
        string="e-CF Security Code",
        copy=False,
        readonly=True,
        help="Security code returned by DGII upon acceptance.",
    )
    l10n_do_ecf_sign_date = fields.Datetime(
        string="e-CF Sign Date",
        copy=False,
        readonly=True,
    )
    l10n_do_ecf_edi_file = fields.Binary(
        string="e-CF XML File",
        copy=False,
        attachment=True,
    )
    l10n_do_ecf_edi_file_name = fields.Char(
        string="e-CF XML Filename",
        copy=False,
    )
    l10n_do_electronic_stamp = fields.Char(
        string="Electronic Stamp URL",
        compute="_compute_l10n_do_electronic_stamp",
        store=True,
        copy=False,
    )

    l10n_do_send_to_dgii = fields.Boolean(
        string="Enviar a DGII",
        default=lambda self: self.env.company.l10n_do_ecf_auto_send_default,
        help="Si está marcado, esta factura se enviará a DGII para obtener un Comprobante Fiscal electrónico (e-CF). Si no, será una factura normal sin NCF electrónico.",
    )

    l10n_do_b_code = fields.Char(
        string="Tipo (B01/B02)",
        compute="_compute_l10n_do_b_code",
        store=True,
    )

    @api.depends("l10n_latam_document_type_id")
    def _compute_l10n_do_b_code(self):
        for move in self:
            ncf = move.l10n_latam_document_type_id.l10n_do_ncf_type
            move.l10n_do_b_code = {"e-31": "B01", "e-32": "B02"}.get(ncf, "")

    @api.depends("l10n_latam_document_type_id", "l10n_do_send_to_dgii")
    def _compute_is_ecf_invoice(self):
        for move in self:
            doc_type = move.l10n_latam_document_type_id
            move.is_ecf_invoice = bool(
                move.l10n_do_send_to_dgii
                and doc_type and doc_type.l10n_do_ncf_type
                and doc_type.l10n_do_ncf_type.startswith("e-")
            )

    # --- e-CF status and tracking fields ---
    l10n_do_ecf_track_id = fields.Char(
        string="DGII Track ID",
        copy=False,
        readonly=True,
        help="Tracking ID returned by DGII after e-CF submission.",
    )
    l10n_do_ecf_status = fields.Selection(
        selection=ECF_STATUS_SELECTION,
        string="e-CF Status",
        copy=False,
        default="draft",
        readonly=True,
        tracking=True,
    )
    l10n_do_ecf_dgii_message = fields.Text(
        string="DGII Message",
        copy=False,
        readonly=True,
        help="Last message received from DGII about this e-CF.",
    )

    # --- Additional DR fiscal fields (self-contained) ---
    l10n_do_income_type = fields.Selection(
        selection=[
            ("01", "01 - Ingresos por Operaciones (No Financieros)"),
            ("02", "02 - Ingresos Financieros"),
            ("03", "03 - Ingresos Extraordinarios"),
            ("04", "04 - Ingresos por Arrendamientos"),
            ("05", "05 - Ingresos por Venta de Activo Depreciable"),
            ("06", "06 - Otros Ingresos"),
        ],
        string="Income Type",
        default="01",
        help="DGII income type (TipoIngresos). Required for e-31, e-32, e-44, e-45, e-46.",
    )
    l10n_do_origin_ncf = fields.Char(
        string="Origin NCF/eNCF",
        copy=False,
        help="Original fiscal number this document modifies (for debit/credit notes).",
    )
    l10n_do_ecf_modification_code = fields.Selection(
        selection=[
            ("1", "1 - Anulación"),
            ("2", "2 - Corrección de Precio"),
            ("3", "3 - Devolución"),
            ("4", "4 - Descuento"),
            ("5", "5 - Ajuste de Precio"),
            ("6", "6 - Otros"),
        ],
        string="Modification Code",
        copy=False,
        help="DGII modification reason code (CodigoModificacion) for credit/debit notes.",
    )

    # --- Computed: Electronic stamp URL (override to ensure correct computation) ---
    @api.depends(
        "l10n_do_ecf_security_code",
        "l10n_do_ecf_sign_date",
        "l10n_latam_document_number",
        "amount_total",
    )
    def _compute_l10n_do_electronic_stamp(self):
        for move in self:
            if (
                move.is_ecf_invoice
                and move.l10n_do_ecf_security_code
                and move.l10n_do_ecf_sign_date
                and move.l10n_latam_document_number
            ):
                company = move.company_id
                rnc = (company.vat or "").replace("-", "").strip()
                encf = move.l10n_latam_document_number or ""
                total = f"{move.amount_total:.2f}"
                code = move.l10n_do_ecf_security_code or ""
                sign_date = move.l10n_do_ecf_sign_date.strftime(
                    "%d-%m-%Y %H:%M:%S"
                )

                env_domain = (
                    "ecf.dgii.gov.do"
                    if company.l10n_do_ecf_service_env == "production"
                    else "ecf.dgii.gov.do/testecf"
                )
                params = urlencode({
                    "RncEmisor": rnc,
                    "eNCF": encf,
                    "MontoTotal": total,
                    "CodigoSeguridad": code,
                    "FechaEmision": sign_date,
                    "FechaFirma": sign_date,
                })
                move.l10n_do_electronic_stamp = (
                    f"https://{env_domain}/ConsultaTimbre?{params}"
                )
            else:
                move.l10n_do_electronic_stamp = False

    # -------------------------------------------------------------------------
    # Actions (UI buttons)
    # -------------------------------------------------------------------------
    def action_generate_ecf_xml(self):
        """Generate (but don't send) the e-CF XML for this invoice."""
        self.ensure_one()
        if not self.is_ecf_invoice:
            raise UserError(_("This invoice is not an e-CF type."))
        if self.state != "posted":
            raise UserError(_("Only posted invoices can generate e-CF XML."))

        xml_generator = self.env["l10n_do.ecf.xml.generator"]
        ncf_type = self.l10n_latam_document_type_id.l10n_do_ncf_type
        type_code = NCF_TYPE_TO_CODE.get(ncf_type)

        # Generate unsigned XML
        xml_root = xml_generator.generate_ecf_xml(self)

        # Validate against XSD (non-blocking if schema missing)
        xsd_validator = self.env["l10n_do.ecf.xsd.validator"]
        try:
            xsd_validator.validate(xml_root, type_code)
        except Exception as e:
            _logger.warning("XSD validation warning: %s", e)

        # Sign the XML
        dgii_api = self.env["l10n_do.dgii.api"]
        p12_bytes, password = self.company_id._get_l10n_do_ecf_certificate_data()
        if not p12_bytes:
            raise UserError(
                _("No e-CF certificate configured. Go to Settings > e-CF.")
            )
        private_key, certificate, _chain = dgii_api._load_p12(p12_bytes, password)
        dgii_api._sign_xml(xml_root, private_key, certificate)

        # Store the signed XML
        signed_bytes = etree.tostring(
            xml_root, xml_declaration=True, encoding="UTF-8", pretty_print=True
        )
        filename = f"{self.l10n_latam_document_number or self.name}.xml"

        self.write({
            "l10n_do_ecf_edi_file": base64.b64encode(signed_bytes),
            "l10n_do_ecf_edi_file_name": filename,
            "l10n_do_ecf_status": "generated",
        })

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("e-CF XML Generated"),
                "message": _("Signed XML created: %s", filename),
                "type": "success",
                "sticky": False,
            },
        }

    def action_send_ecf_to_dgii(self):
        """Send the signed e-CF XML to DGII."""
        self.ensure_one()
        if not self.l10n_do_ecf_edi_file:
            # Auto-generate if not yet done
            self.action_generate_ecf_xml()

        if self.l10n_do_ecf_status in ("accepted",):
            raise UserError(_("This e-CF has already been accepted by DGII."))

        signed_xml_bytes = base64.b64decode(self.l10n_do_ecf_edi_file)
        filename = self.l10n_do_ecf_edi_file_name or "ecf.xml"

        dgii_api = self.env["l10n_do.dgii.api"]
        result = dgii_api._send_ecf(self.company_id, signed_xml_bytes, filename)

        # Parse DGII response
        track_id = result.get("trackId", "")
        mensaje = result.get("mensaje", result.get("message", ""))
        estado = result.get("estado", "")

        status = DGII_STATUS_MAP.get(estado, "sent")
        if not track_id and "error" in str(mensaje).lower():
            status = "error"

        vals = {
            "l10n_do_ecf_track_id": track_id,
            "l10n_do_ecf_status": status,
            "l10n_do_ecf_dgii_message": mensaje,
        }

        # If immediately accepted, capture security code and sign date
        if status == "accepted":
            vals.update(self._extract_acceptance_data(result))

        self.write(vals)

        notif_type = "success" if status in ("sent", "accepted") else "warning"
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("e-CF Sent to DGII"),
                "message": _("Status: %s - %s", estado or status, mensaje),
                "type": notif_type,
                "sticky": status in ("error", "rejected"),
            },
        }

    def action_check_ecf_status(self):
        """Poll DGII for the current status of a sent e-CF."""
        self.ensure_one()
        if not self.l10n_do_ecf_track_id:
            raise UserError(_("No DGII tracking ID found. Send the e-CF first."))

        dgii_api = self.env["l10n_do.dgii.api"]
        result = dgii_api._poll_status(self.company_id, self.l10n_do_ecf_track_id)

        estado = result.get("estado", "")
        mensaje = result.get("mensaje", result.get("message", ""))
        status = DGII_STATUS_MAP.get(estado, self.l10n_do_ecf_status)

        vals = {
            "l10n_do_ecf_status": status,
            "l10n_do_ecf_dgii_message": mensaje,
        }

        if status == "accepted":
            vals.update(self._extract_acceptance_data(result))

        self.write(vals)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("e-CF Status Update"),
                "message": _("Status: %s - %s", estado or status, mensaje),
                "type": "success" if status == "accepted" else "info",
                "sticky": False,
            },
        }

    # -------------------------------------------------------------------------
    # Auto-send on post
    # -------------------------------------------------------------------------
    def _post(self, soft=True):
        """Override to auto-generate e-CF XML after posting."""
        posted = super()._post(soft=soft)
        for move in posted:
            if (
                move.is_ecf_invoice
                and move.l10n_do_send_to_dgii
                and move.company_id.l10n_do_ecf_issuer
                and move.l10n_do_ecf_status == "draft"
            ):
                try:
                    move.action_generate_ecf_xml()
                except Exception as e:
                    _logger.error(
                        "Failed to auto-generate e-CF XML for %s: %s",
                        move.name, e,
                    )
        return posted

    # -------------------------------------------------------------------------
    # Cron: batch poll status
    # -------------------------------------------------------------------------
    @api.model
    def _cron_poll_ecf_status(self):
        """Cron job to poll DGII for status of all sent e-CF documents."""
        moves = self.search([
            ("l10n_do_send_to_dgii", "=", True),
            ("l10n_do_ecf_status", "=", "sent"),
            ("l10n_do_ecf_track_id", "!=", False),
        ])
        dgii_api = self.env["l10n_do.dgii.api"]
        for move in moves:
            try:
                result = dgii_api._poll_status(
                    move.company_id, move.l10n_do_ecf_track_id
                )
                estado = result.get("estado", "")
                mensaje = result.get("mensaje", result.get("message", ""))
                status = DGII_STATUS_MAP.get(estado, "sent")

                vals = {
                    "l10n_do_ecf_status": status,
                    "l10n_do_ecf_dgii_message": mensaje,
                }
                if status == "accepted":
                    vals.update(move._extract_acceptance_data(result))

                move.write(vals)
                _logger.info(
                    "e-CF %s (%s): status=%s",
                    move.l10n_latam_document_number, move.l10n_do_ecf_track_id, status,
                )
            except Exception as e:
                _logger.error(
                    "Failed to poll e-CF status for %s: %s",
                    move.l10n_latam_document_number, e,
                )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _extract_acceptance_data(self, dgii_result):
        """Extract security code and sign date from a DGII acceptance response."""
        vals = {}
        security_code = dgii_result.get("codigoSeguridad", "")
        if security_code:
            vals["l10n_do_ecf_security_code"] = security_code

        sign_date = dgii_result.get("fechaFirma", "")
        if sign_date:
            try:
                # DGII returns DD-MM-YYYY HH:MM:SS
                vals["l10n_do_ecf_sign_date"] = datetime.strptime(
                    sign_date, "%d-%m-%Y %H:%M:%S"
                )
            except (ValueError, TypeError):
                try:
                    vals["l10n_do_ecf_sign_date"] = datetime.fromisoformat(
                        sign_date
                    )
                except (ValueError, TypeError):
                    pass
        return vals
