"""
e-CF XML Generator for all 10 DGII electronic document types (E31-E47).

The generator follows a dispatch pattern: each e-CF type has its own builder
method that assembles the <ECF> tree with the required/conditional sections.
Common elements (Encabezado subsections, DetallesItems) are shared helpers.
"""
import logging
from datetime import datetime

from lxml import etree

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# e-CF type code → l10n_do_ncf_type mapping
# Values match l10n_do_ncf_type field on l10n_latam.document.type
ECF_TYPE_MAP = {
    "31": "e-31",
    "32": "e-32",
    "33": "e-33",
    "34": "e-34",
    "41": "e-41",
    "43": "e-43",
    "44": "e-44",
    "45": "e-45",
    "46": "e-46",
    "47": "e-47",
}

# Reverse: ncf_type → DGII type code
NCF_TYPE_TO_CODE = {v: k for k, v in ECF_TYPE_MAP.items()}

# ITBIS rate map: Odoo tax amount → DGII IndicadorFacturacion code
ITBIS_RATE_MAP = {
    18: "1",
    16: "2",
    0: "3",
}

# Payment method mapping from Odoo journal type to DGII FormaPago code
PAYMENT_METHOD_MAP = {
    "cash": "1",
    "bank": "2",
    "credit_card": "3",
    "general": "8",
}

ECF_DATE_FORMAT = "%d-%m-%Y"
ECF_DATETIME_FORMAT = "%d-%m-%Y %H:%M:%S"


def _fmt_date(dt):
    """Format a date/datetime to DD-MM-YYYY."""
    if not dt:
        return ""
    if isinstance(dt, datetime):
        return dt.strftime(ECF_DATE_FORMAT)
    return dt.strftime(ECF_DATE_FORMAT)


def _fmt_datetime(dt):
    """Format a datetime to DD-MM-YYYY HH:MM:SS."""
    if not dt:
        return ""
    return dt.strftime(ECF_DATETIME_FORMAT)


def _fmt_amount(amount, decimals=2):
    """Format a numeric amount to string with fixed decimal places."""
    if amount is None:
        amount = 0.0
    return f"{amount:.{decimals}f}"


def _add_element(parent, tag, text=None, attrib=None):
    """Add a sub-element with optional text. Returns the new element."""
    el = etree.SubElement(parent, tag, attrib=attrib or {})
    if text is not None:
        el.text = str(text)
    return el


# DGII structural rules extracted from certified scripts (paso2_send_ecf.py)
HAS_FECHA_VENC     = {"31", "33", "41", "43", "44", "45", "46", "47"}  # NOT 32, 34
HAS_TIPO_INGRESOS  = {"31", "32", "33", "34", "44", "45", "46"}         # NOT 41, 43, 47
HAS_TABLA_FORMAS   = {"31", "32", "33", "41", "44", "45", "46", "47"}   # NOT 34, 43
HAS_COMPRADOR      = {"31", "32", "33", "34", "41", "44", "45", "46", "47"}  # NOT 43
HAS_ITEM_RET_REQ   = {"41", "47"}  # Retencion required in items
HAS_ITEM_RET_OPT   = {"33", "34"}  # Retencion optional in items
HAS_INFO_REF       = {"33", "34"}  # InformacionReferencia required


class EcfXmlGenerator(models.AbstractModel):
    """Generates e-CF XML documents from account.move records."""

    _name = "l10n_do.ecf.xml.generator"
    _description = "e-CF XML Generator"

    # -------------------------------------------------------------------------
    # Main dispatch
    # -------------------------------------------------------------------------
    @api.model
    def generate_ecf_xml(self, move):
        """Generate the unsigned e-CF XML for an account.move.

        Returns an lxml.etree.Element (<ECF> root).
        """
        ncf_type = move.l10n_latam_document_type_id.l10n_do_ncf_type
        type_code = NCF_TYPE_TO_CODE.get(ncf_type)
        if not type_code:
            raise UserError(
                _("Unsupported e-CF type: %s", ncf_type)
            )

        builder = getattr(self, f"_build_ecf_{type_code}", None)
        if not builder:
            raise UserError(
                _("No XML builder implemented for e-CF type E%s.", type_code)
            )

        root = etree.Element("ECF", nsmap={
            "xsd": "http://www.w3.org/2001/XMLSchema",
            "xsi": "http://www.w3.org/2001/XMLSchema-instance",
        })
        builder(root, move, type_code)
        return root

    # -------------------------------------------------------------------------
    # Per-type builders — each appends sections to root
    # -------------------------------------------------------------------------
    def _build_ecf_31(self, root, move, type_code):
        """E31: Factura de Crédito Fiscal (B2B)."""
        self._build_encabezado(root, move, type_code)
        self._build_detalles_items(root, move, type_code)
        self._build_informacion_referencia(root, move)
        self._build_fecha_hora_firma(root)

    def _build_ecf_32(self, root, move, type_code):
        """E32: Factura de Consumo (B2C)."""
        self._build_encabezado(root, move, type_code)
        self._build_detalles_items(root, move, type_code)
        self._build_informacion_referencia(root, move)
        self._build_fecha_hora_firma(root)

    def _build_ecf_33(self, root, move, type_code):
        """E33: Nota de Débito."""
        self._build_encabezado(root, move, type_code)
        self._build_detalles_items(root, move, type_code)
        self._build_informacion_referencia(root, move, required=True)
        self._build_fecha_hora_firma(root)

    def _build_ecf_34(self, root, move, type_code):
        """E34: Nota de Crédito."""
        self._build_encabezado(root, move, type_code)
        self._build_detalles_items(root, move, type_code)
        self._build_informacion_referencia(root, move, required=True)
        self._build_fecha_hora_firma(root)

    def _build_ecf_41(self, root, move, type_code):
        """E41: Comprobante de Compras (informal supplier)."""
        self._build_encabezado(root, move, type_code)
        self._build_detalles_items(root, move, type_code)
        self._build_informacion_referencia(root, move)
        self._build_fecha_hora_firma(root)

    def _build_ecf_43(self, root, move, type_code):
        """E43: Gastos Menores."""
        self._build_encabezado(root, move, type_code)
        self._build_detalles_items(root, move, type_code)
        self._build_informacion_referencia(root, move)
        self._build_fecha_hora_firma(root)

    def _build_ecf_44(self, root, move, type_code):
        """E44: Regímenes Especiales."""
        self._build_encabezado(root, move, type_code)
        self._build_detalles_items(root, move, type_code)
        self._build_informacion_referencia(root, move)
        self._build_fecha_hora_firma(root)

    def _build_ecf_45(self, root, move, type_code):
        """E45: Gubernamental."""
        self._build_encabezado(root, move, type_code)
        self._build_detalles_items(root, move, type_code)
        self._build_informacion_referencia(root, move)
        self._build_fecha_hora_firma(root)

    def _build_ecf_46(self, root, move, type_code):
        """E46: Exportaciones."""
        self._build_encabezado(root, move, type_code, export_info=True)
        self._build_detalles_items(root, move, type_code)
        self._build_informacion_referencia(root, move)
        self._build_fecha_hora_firma(root)

    def _build_ecf_47(self, root, move, type_code):
        """E47: Pagos al Exterior."""
        self._build_encabezado(root, move, type_code, exterior=True)
        self._build_detalles_items(root, move, type_code)
        self._build_informacion_referencia(root, move)
        self._build_fecha_hora_firma(root)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _format_encf(self, document_number, type_code):
        """Format eNCF to DGII standard: E{type}{10-digit-sequence}.

        Examples:
          - Input: "3062" → Output: "E310000003062"
          - Input: "E310000003062" → Output: "E310000003062" (already formatted)
        """
        if not document_number:
            return ""

        expected_prefix = f"E{type_code}"
        if document_number.startswith(expected_prefix) and len(document_number) == 13:
            return document_number

        try:
            seq = int(document_number)
            return f"E{type_code}{seq:010d}"
        except ValueError:
            # Try extracting trailing digits (handles corrupt names like "False False False 3086")
            import re
            match = re.search(r'(\d+)$', document_number.strip())
            if match:
                seq = int(match.group(1))
                _logger.warning("eNCF extracted from corrupt name '%s' → %d", document_number, seq)
                return f"E{type_code}{seq:010d}"
            _logger.warning("eNCF format invalid, cannot parse: %s", document_number)
            return document_number

    # -------------------------------------------------------------------------
    # Encabezado (Header)
    # -------------------------------------------------------------------------
    def _build_encabezado(
        self, root, move, type_code,
        export_info=False, exterior=False
    ):
        encabezado = _add_element(root, "Encabezado")
        _add_element(encabezado, "Version", "1.0")

        self._build_id_doc(encabezado, move, type_code)
        self._build_emisor(encabezado, move)
        if type_code in HAS_COMPRADOR:
            self._build_comprador(encabezado, move, type_code, exterior=exterior)
        if export_info:
            self._build_informaciones_adicionales(encabezado, move)
        self._build_totales(encabezado, move, type_code)
        if move.currency_id != move.company_id.currency_id:
            self._build_otra_moneda(encabezado, move)

    # --- IdDoc ---
    def _build_id_doc(self, encabezado, move, type_code):
        id_doc = _add_element(encabezado, "IdDoc")
        _add_element(id_doc, "TipoeCF", type_code)

        # Use DGII-assigned sequence number if available, else fall back to document number
        dgii_seq = move.l10n_do_ecf_sequence_number
        if dgii_seq:
            encf = f"E{type_code}{dgii_seq:010d}"
        else:
            encf = self._format_encf(move.l10n_latam_document_number, type_code)
        _add_element(id_doc, "eNCF", encf)

        # E34: IndicadorNotaCredito right after eNCF
        if type_code == "34":
            _add_element(id_doc, "IndicadorNotaCredito", "0")

        # Sequence expiration date — NOT for types 32, 34 (required by DGII)
        if type_code in HAS_FECHA_VENC:
            exp_date = self._get_sequence_expiration(move)
            if not exp_date:
                exp_date = move.company_id.l10n_do_ecf_sequence_expiration_date
            if exp_date:
                _add_element(id_doc, "FechaVencimientoSecuencia", exp_date.strftime("%Y-%m-%d") if hasattr(exp_date, 'strftime') else str(exp_date))

        # Deferred indicator — NOT for type 43
        # XSD only accepts "1", so only include if deferred submissions are enabled
        if type_code != "43" and move.company_id.l10n_do_ecf_deferred_submissions:
            _add_element(id_doc, "IndicadorEnvioDiferido", "1")

        # Tax indicator — NOT for types 43, 47
        if type_code not in ("43", "47"):
            _add_element(id_doc, "IndicadorMontoGravado", "0")

        # Income type
        if type_code in HAS_TIPO_INGRESOS:
            income_type = move.l10n_do_income_type or "01"
            _add_element(id_doc, "TipoIngresos", income_type.zfill(2))

        # Payment type
        payment_type = self._get_payment_type(move)
        _add_element(id_doc, "TipoPago", payment_type)

        # Payment due date for credit — NOT for type 43
        if payment_type == "2" and move.invoice_date_due and type_code != "43":
            _add_element(
                id_doc, "FechaLimitePago", _fmt_date(move.invoice_date_due)
            )
            if move.invoice_payment_term_id and type_code != "34":
                _add_element(
                    id_doc, "TerminoPago", move.invoice_payment_term_id.name[:50]
                )

        # Payment methods table — NOT for types 34, 43
        if type_code in HAS_TABLA_FORMAS:
            self._build_payment_methods(id_doc, move)

        # TotalPaginas — XSD requires value > 1 (minExclusive="1"), so omit for single-page invoices
        # Only include if explicitly needed for multi-page documents
        # total_paginas = 1  # Default single page — omitted to satisfy XSD
        # if total_paginas > 1:
        #     _add_element(id_doc, "TotalPaginas", str(total_paginas))

    # --- Emisor (Issuer) ---
    def _build_emisor(self, encabezado, move):
        company = move.company_id
        emisor = _add_element(encabezado, "Emisor")
        rnc = self._clean_vat(company.vat)
        _add_element(emisor, "RNCEmisor", rnc)
        _add_element(emisor, "RazonSocialEmisor", company.name[:150])

        if company.company_registry:
            _add_element(emisor, "NombreComercial", company.company_registry[:150])

        if company.street:
            address = self._build_address_string(company)
            _add_element(emisor, "DireccionEmisor", address[:100])

        # Municipio and Provincia — default 010101 (Santo Domingo, Distrito Nacional)
        municipality_code = getattr(company, 'l10n_do_municipality_code', None) or "010101"
        if len(municipality_code) >= 6:
            _add_element(emisor, "Municipio", municipality_code[:6])
            _add_element(emisor, "Provincia", municipality_code[:6])

        if company.phone:
            phones = _add_element(emisor, "TablaTelefonoEmisor")
            _add_element(phones, "TelefonoEmisor", company.phone[:20])

        if company.email:
            _add_element(emisor, "CorreoEmisor", company.email[:80])

        if company.website:
            _add_element(emisor, "WebSite", company.website[:80])

        # Internal invoice reference
        _add_element(emisor, "NumeroFacturaInterna", move.name[:20])

        _add_element(emisor, "FechaEmision", _fmt_date(move.invoice_date))

    # --- Comprador (Buyer) ---
    def _build_comprador(self, encabezado, move, type_code, exterior=False):
        partner = move.commercial_partner_id

        # Type 43 (Gastos Menores) has NO Comprador section
        if type_code == "43":
            return

        comprador = _add_element(encabezado, "Comprador")

        if exterior and not partner.vat:
            # For type 47, use foreign identifier
            ident = partner.ref or partner.name[:20]
            _add_element(comprador, "IdentificadorExtranjero", ident[:20])
        else:
            rnc = self._clean_vat(partner.vat)
            if rnc:
                _add_element(comprador, "RNCComprador", rnc)

        _add_element(comprador, "RazonSocialComprador", partner.name[:150])

        if partner.email:
            _add_element(comprador, "CorreoComprador", partner.email[:80])

        if partner.street:
            address = self._build_address_string(partner)
            _add_element(comprador, "DireccionComprador", address[:100])

    # --- InformacionesAdicionales (for exports) ---
    def _build_informaciones_adicionales(self, encabezado, move):
        info = _add_element(encabezado, "InformacionesAdicionales")
        _add_element(info, "FechaEmbarque", _fmt_date(move.invoice_date))

    # --- Totales ---
    def _build_totales(self, encabezado, move, type_code):
        totales = _add_element(encabezado, "Totales")

        tax_totals = self._compute_tax_totals(move)

        _add_element(totales, "MontoGravadoTotal", _fmt_amount(tax_totals["gravado_total"]))
        if tax_totals["gravado_18"]:
            _add_element(totales, "MontoGravadoI1", _fmt_amount(tax_totals["gravado_18"]))
        if tax_totals["gravado_16"]:
            _add_element(totales, "MontoGravadoI2", _fmt_amount(tax_totals["gravado_16"]))
        if tax_totals["gravado_0"]:
            _add_element(totales, "MontoGravadoI3", _fmt_amount(tax_totals["gravado_0"]))
        if tax_totals["exento"]:
            _add_element(totales, "MontoExento", _fmt_amount(tax_totals["exento"]))

        # ITBIS rates: only include if corresponding gravado exists
        if tax_totals["gravado_18"]:
            _add_element(totales, "ITBIS1", "18")
        if tax_totals["gravado_16"]:
            _add_element(totales, "ITBIS2", "16")
        if tax_totals["gravado_0"]:
            _add_element(totales, "ITBIS3", "0")

        _add_element(totales, "TotalITBIS", _fmt_amount(tax_totals["itbis_total"]))
        if tax_totals["itbis_18"]:
            _add_element(totales, "TotalITBIS1", _fmt_amount(tax_totals["itbis_18"]))
        if tax_totals["itbis_16"]:
            _add_element(totales, "TotalITBIS2", _fmt_amount(tax_totals["itbis_16"]))
        if tax_totals["itbis_0"]:
            _add_element(totales, "TotalITBIS3", _fmt_amount(tax_totals["itbis_0"]))

        # Additional taxes
        if tax_totals.get("impuesto_adicional"):
            _add_element(
                totales, "MontoImpuestoAdicional",
                _fmt_amount(tax_totals["impuesto_adicional"])
            )

        _add_element(totales, "MontoTotal", _fmt_amount(tax_totals["monto_total"]))
        _add_element(totales, "ValorPagar", _fmt_amount(tax_totals["monto_total"]))

        # Withholdings (for types 41, 43, 46, 47)
        if type_code in ("41", "43", "46", "47"):
            if tax_totals.get("itbis_retenido"):
                _add_element(
                    totales, "TotalITBISRetenido",
                    _fmt_amount(tax_totals["itbis_retenido"])
                )
            if tax_totals.get("isr_retencion"):
                _add_element(
                    totales, "TotalISRRetencion",
                    _fmt_amount(tax_totals["isr_retencion"])
                )

    # --- OtraMoneda (Other Currency) ---
    def _build_otra_moneda(self, encabezado, move):
        otra = _add_element(encabezado, "OtraMoneda")
        currency = move.currency_id
        company_currency = move.company_id.currency_id

        _add_element(otra, "TipoMoneda", currency.name)

        # Exchange rate: how many DOP per 1 unit of other currency
        if move.invoice_date:
            rate = currency._get_conversion_rate(
                currency, company_currency, move.company_id, move.invoice_date
            )
        else:
            rate = 1.0
        _add_element(otra, "TipoCambio", _fmt_amount(rate, 4))

        tax_totals = self._compute_tax_totals(move, use_foreign=True)
        _add_element(
            otra, "MontoGravadoTotalOtraMoneda",
            _fmt_amount(tax_totals["gravado_total"])
        )
        _add_element(
            otra, "MontoGravado1OtraMoneda",
            _fmt_amount(tax_totals["gravado_18"])
        )
        _add_element(
            otra, "MontoGravado2OtraMoneda",
            _fmt_amount(tax_totals["gravado_16"])
        )
        _add_element(
            otra, "MontoGravado3OtraMoneda",
            _fmt_amount(tax_totals["gravado_0"])
        )
        _add_element(
            otra, "MontoExentoOtraMoneda",
            _fmt_amount(tax_totals["exento"])
        )
        _add_element(
            otra, "TotalITBISOtraMoneda",
            _fmt_amount(tax_totals["itbis_total"])
        )
        _add_element(
            otra, "TotalITBIS1OtraMoneda",
            _fmt_amount(tax_totals["itbis_18"])
        )
        _add_element(
            otra, "TotalITBIS2OtraMoneda",
            _fmt_amount(tax_totals["itbis_16"])
        )
        _add_element(
            otra, "TotalITBIS3OtraMoneda",
            _fmt_amount(tax_totals["itbis_0"])
        )
        _add_element(
            otra, "MontoTotalOtraMoneda",
            _fmt_amount(tax_totals["monto_total"])
        )

    # -------------------------------------------------------------------------
    # DetallesItems (Line Items)
    # -------------------------------------------------------------------------
    def _build_detalles_items(self, root, move, type_code):
        detalles = _add_element(root, "DetallesItems")
        line_number = 0
        for line in move.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        ):
            # Skip lines with no valid name — XSD requires NombreItem minLength=1
            item_name = (line.name or line.product_id.name or "").strip()
            if not item_name:
                continue
            line_number += 1
            self._build_item(detalles, line, line_number, move, type_code)

    def _build_item(self, detalles, line, line_number, move, type_code):
        item = _add_element(detalles, "Item")
        _add_element(item, "NumeroLinea", str(line_number))

        # Product codes
        if line.product_id:
            codigos = _add_element(item, "TablaCodigosItem")
            cod = _add_element(codigos, "CodigosItem")
            if line.product_id.barcode:
                _add_element(cod, "TipoCodigo", "EAN")
                _add_element(cod, "CodigoItem", line.product_id.barcode[:35])
            else:
                _add_element(cod, "TipoCodigo", "Interno")
                _add_element(
                    cod, "CodigoItem", str(line.product_id.default_code or line.product_id.id)[:35]
                )

        # Tax indicator (IndicadorFacturacion) — BEFORE NombreItem per XSD
        itbis_indicator = self._get_line_tax_indicator(line)
        _add_element(item, "IndicadorFacturacion", itbis_indicator)

        # Retention info — required for 41/47, optional for 33/34
        retention = self._get_line_retention(line)
        ret_ind = "1" if (retention["itbis_retenido"] or retention["isr_retenido"]) else "0"
        if type_code in HAS_ITEM_RET_REQ or (type_code in HAS_ITEM_RET_OPT and ret_ind == "1"):
            ret_el = _add_element(item, "Retencion")
            _add_element(ret_el, "IndicadorAgenteRetencionoPercepcion", ret_ind)
            if retention["itbis_retenido"]:
                _add_element(
                    ret_el, "MontoITBISRetenido",
                    _fmt_amount(retention["itbis_retenido"])
                )
            if retention["isr_retenido"]:
                _add_element(
                    ret_el, "MontoISRRetenido",
                    _fmt_amount(retention["isr_retenido"])
                )

        # Item name and description
        item_name = (line.name or line.product_id.name or "Item").strip()
        if not item_name:
            item_name = "Item"
        _add_element(item, "NombreItem", item_name[:80])

        # Good vs Service indicator
        if line.product_id:
            bien_servicio = "2" if line.product_id.type == "service" else "1"
        else:
            bien_servicio = "1"
        _add_element(item, "IndicadorBienoServicio", bien_servicio)

        if line.name and len(line.name) > 80:
            _add_element(item, "DescripcionItem", line.name[:1000])

        # KEY FIX: CantidadItem as integer string
        _add_element(item, "CantidadItem", str(int(line.quantity)))

        # Unit of measure
        uom_code = self._get_uom_code(line)
        if uom_code:
            _add_element(item, "UnidadMedida", str(uom_code))

        _add_element(item, "PrecioUnitarioItem", _fmt_amount(line.price_unit))

        # Line discount
        if line.discount:
            discount_amount = line.price_unit * line.quantity * line.discount / 100.0
            _add_element(item, "DescuentoMonto", _fmt_amount(discount_amount))

        # Other currency detail
        if move.currency_id != move.company_id.currency_id:
            otra_det = _add_element(item, "OtraMonedaDetalle")
            _add_element(otra_det, "PrecioOtraMoneda", _fmt_amount(line.price_unit))
            if line.discount:
                disc_fc = line.price_unit * line.quantity * line.discount / 100.0
                _add_element(otra_det, "DescuentoOtraMoneda", _fmt_amount(disc_fc))
            _add_element(
                otra_det, "MontoItemOtraMoneda", _fmt_amount(line.price_subtotal)
            )

        _add_element(item, "MontoItem", _fmt_amount(line.price_subtotal))

    # -------------------------------------------------------------------------
    # InformacionReferencia (for credit/debit notes)
    # -------------------------------------------------------------------------
    def _build_informacion_referencia(self, root, move, required=False):
        origin_ncf = move.l10n_do_origin_ncf
        if not origin_ncf:
            if required:
                raise UserError(
                    _(
                        "Credit/Debit notes require a reference to the original "
                        "fiscal document (NCF Modificado)."
                    )
                )
            return

        info_ref = _add_element(root, "InformacionReferencia")
        _add_element(info_ref, "NCFModificado", origin_ncf)

        if move.commercial_partner_id.vat:
            rnc = self._clean_vat(move.commercial_partner_id.vat)
            _add_element(info_ref, "RNCOtroContribuyente", rnc)

        # Find the original invoice date
        origin_move = self._find_origin_move(move, origin_ncf)
        if origin_move:
            _add_element(
                info_ref, "FechaNCFModificado",
                _fmt_date(origin_move.invoice_date)
            )

        mod_code = move.l10n_do_ecf_modification_code or "1"
        _add_element(info_ref, "CodigoModificacion", mod_code)

        if move.l10n_do_ecf_modification_code:
            reasons = {
                "1": "Anulación",
                "2": "Corrección de Precio",
                "3": "Devolución",
                "4": "Descuento",
                "5": "Ajuste de Precio",
                "6": "Otros",
            }
            razon = reasons.get(move.l10n_do_ecf_modification_code, "")
            if razon:
                _add_element(info_ref, "RazonModificacion", razon)

    # -------------------------------------------------------------------------
    # FechaHoraFirma
    # -------------------------------------------------------------------------
    def _build_fecha_hora_firma(self, root):
        now = datetime.now()
        _add_element(root, "FechaHoraFirma", _fmt_datetime(now))

    # -------------------------------------------------------------------------
    # Payment methods
    # -------------------------------------------------------------------------
    def _build_payment_methods(self, id_doc, move):
        tabla = _add_element(id_doc, "TablaFormasPago")
        forma = _add_element(tabla, "FormaDePago")

        # Determine payment form from payment terms or default
        payment_code = self._get_forma_pago_code(move)
        _add_element(forma, "FormaPago", payment_code)
        _add_element(forma, "MontoPago", _fmt_amount(move.amount_total))

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    @api.model
    def _clean_vat(self, vat):
        """Remove non-alphanumeric chars from VAT/RNC."""
        if not vat:
            return ""
        return "".join(c for c in vat if c.isalnum())

    @api.model
    def _build_address_string(self, partner_or_company):
        """Build a single address string from partner/company fields."""
        parts = [
            partner_or_company.street or "",
            partner_or_company.street2 or "",
            partner_or_company.city or "",
        ]
        return ", ".join(p for p in parts if p)

    @api.model
    def _get_payment_type(self, move):
        """Return DGII TipoPago: 1=contado, 2=credito, 3=gratuito."""
        if move.amount_total == 0:
            return "3"
        if move.invoice_payment_term_id:
            # If due date > invoice date, it's credit
            if (
                move.invoice_date_due
                and move.invoice_date
                and move.invoice_date_due > move.invoice_date
            ):
                return "2"
        return "1"

    @api.model
    def _get_forma_pago_code(self, move):
        """Determine DGII FormaPago code."""
        if move.invoice_payment_term_id:
            if (
                move.invoice_date_due
                and move.invoice_date
                and move.invoice_date_due > move.invoice_date
            ):
                return "4"  # Venta a Credito
        # Default to cash or other
        return "8"  # Otras Formas de Pago

    @api.model
    def _get_sequence_expiration(self, move):
        """Get the NCF sequence expiration date for this document type."""
        journal = move.journal_id
        doc_type = move.l10n_latam_document_type_id
        if hasattr(journal, "l10n_do_document_type_ids"):
            for jdt in journal.l10n_do_document_type_ids:
                if jdt.l10n_latam_document_type_id == doc_type:
                    return jdt.l10n_do_ncf_expiration_date
        # l10n_do_ncf_expiration_date is optional (from l10n_do_accounting).
        # For e-CF, DGII manages sequences centrally — no local expiration needed.
        return getattr(move, "l10n_do_ncf_expiration_date", None)

    def _compute_tax_totals(self, move, use_foreign=False):
        """Compute the DGII tax breakdown from invoice lines.

        Returns a dict with keys:
            gravado_total, gravado_18, gravado_16, gravado_0, exento,
            itbis_total, itbis_18, itbis_16, itbis_0,
            impuesto_adicional, monto_total,
            itbis_retenido, isr_retencion
        """
        result = {
            "gravado_total": 0.0,
            "gravado_18": 0.0,
            "gravado_16": 0.0,
            "gravado_0": 0.0,
            "exento": 0.0,
            "itbis_total": 0.0,
            "itbis_18": 0.0,
            "itbis_16": 0.0,
            "itbis_0": 0.0,
            "impuesto_adicional": 0.0,
            "monto_total": 0.0,
            "itbis_retenido": 0.0,
            "isr_retencion": 0.0,
        }

        for line in move.invoice_line_ids.filtered(
            lambda l: l.display_type == "product"
        ):
            subtotal = line.price_subtotal
            if use_foreign and move.currency_id != move.company_id.currency_id:
                # Use foreign currency amounts directly
                subtotal = line.price_subtotal
            elif not use_foreign and move.currency_id != move.company_id.currency_id:
                # Convert to company currency
                subtotal = move.currency_id._convert(
                    line.price_subtotal,
                    move.company_id.currency_id,
                    move.company_id,
                    move.invoice_date or move.date,
                )

            # Classify taxes on this line
            itbis_rate = self._get_line_itbis_rate(line)
            itbis_amount = self._get_line_itbis_amount(line, use_foreign)

            if itbis_rate is None:
                # No ITBIS tax → exempt
                result["exento"] += subtotal
            elif itbis_rate == 18:
                result["gravado_18"] += subtotal
                result["itbis_18"] += itbis_amount
            elif itbis_rate == 16:
                result["gravado_16"] += subtotal
                result["itbis_16"] += itbis_amount
            else:
                result["gravado_0"] += subtotal
                result["itbis_0"] += itbis_amount

            # Withholdings
            retention = self._get_line_retention(line)
            result["itbis_retenido"] += retention.get("itbis_retenido", 0.0)
            result["isr_retencion"] += retention.get("isr_retenido", 0.0)

        result["gravado_total"] = (
            result["gravado_18"] + result["gravado_16"] + result["gravado_0"]
        )
        result["itbis_total"] = (
            result["itbis_18"] + result["itbis_16"] + result["itbis_0"]
        )
        result["monto_total"] = (
            result["gravado_total"] + result["exento"] + result["itbis_total"]
            + result["impuesto_adicional"]
        )
        return result

    @api.model
    def _get_line_itbis_rate(self, line):
        """Return the ITBIS tax rate (18, 16, or 0) for a line, or None if exempt."""
        for tax in line.tax_ids:
            tax_group = tax.tax_group_id
            if tax_group and "itbis" in (tax_group.name or "").lower():
                return int(abs(tax.amount))
            if tax_group and "itbis" in (tax_group.l10n_do_tax_type or "").lower() if hasattr(tax_group, 'l10n_do_tax_type') else False:
                return int(abs(tax.amount))
            # Also check by tax amount for standard ITBIS rates
            if abs(tax.amount) in (18, 16) and tax.amount > 0:
                return int(abs(tax.amount))
        # Check if any tax at all
        positive_taxes = line.tax_ids.filtered(lambda t: t.amount > 0)
        if not positive_taxes:
            return None
        return 0

    @api.model
    def _get_line_itbis_amount(self, line, use_foreign=False):
        """Return the ITBIS tax amount for a line."""
        if hasattr(line, "l10n_do_itbis_amount") and line.l10n_do_itbis_amount:
            return abs(line.l10n_do_itbis_amount)
        # Fallback: compute from tax rate
        rate = self._get_line_itbis_rate(line)
        if rate:
            return line.price_subtotal * rate / 100.0
        return 0.0

    @api.model
    def _get_line_retention(self, line):
        """Return withholding amounts for a line."""
        itbis_ret = 0.0
        isr_ret = 0.0
        for tax in line.tax_ids:
            if tax.amount < 0:
                tax_name = (tax.name or "").lower()
                if "itbis" in tax_name and "ret" in tax_name:
                    itbis_ret += abs(line.price_subtotal * tax.amount / 100.0)
                elif "isr" in tax_name:
                    isr_ret += abs(line.price_subtotal * tax.amount / 100.0)
        return {"itbis_retenido": itbis_ret, "isr_retenido": isr_ret}

    @api.model
    def _get_line_tax_indicator(self, line):
        """Return DGII IndicadorFacturacion code for a line.

        1 = ITBIS 18%, 2 = ITBIS 16%, 3 = ITBIS 0%, 4 = Exempt / No ITBIS
        """
        rate = self._get_line_itbis_rate(line)
        if rate is None:
            return "4"  # Exempt (no ITBIS tax at all)
        if rate == 0:
            return "3"  # ITBIS 0%
        return ITBIS_RATE_MAP.get(rate, "1")

    @api.model
    def _get_uom_code(self, line):
        """Map Odoo UoM to a numeric code. Returns integer."""
        # DGII uses numeric codes; common mappings:
        uom = line.product_uom_id
        if not uom:
            return 43  # Default: "unidad"
        name_lower = (uom.name or "").lower()
        if "unit" in name_lower or "unidad" in name_lower:
            return 43
        if "kg" in name_lower or "kilo" in name_lower:
            return 1
        if "lb" in name_lower or "libra" in name_lower:
            return 2
        if "lt" in name_lower or "litro" in name_lower or "liter" in name_lower:
            return 3
        if "gal" in name_lower:
            return 4
        if "m" == name_lower or "metro" in name_lower or "meter" in name_lower:
            return 5
        if "hora" in name_lower or "hour" in name_lower:
            return 18
        if "day" in name_lower or "día" in name_lower:
            return 19
        return 43

    @api.model
    def _find_origin_move(self, move, origin_ncf):
        """Find the original account.move by fiscal number."""
        if not origin_ncf:
            return None
        return self.env["account.move"].search(
            [
                ("l10n_latam_document_number", "=", origin_ncf),
                ("company_id", "=", move.company_id.id),
            ],
            limit=1,
        )
