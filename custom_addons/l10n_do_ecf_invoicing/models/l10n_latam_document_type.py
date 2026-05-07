from odoo import fields, models

NCF_TYPE_SELECTION = [
    ("e-31", "e-31 Factura de Crédito Fiscal Electrónica"),
    ("e-32", "e-32 Factura de Consumo Electrónica"),
    ("e-33", "e-33 Nota de Débito Electrónica"),
    ("e-34", "e-34 Nota de Crédito Electrónica"),
    ("e-41", "e-41 Compras Electrónicas"),
    ("e-43", "e-43 Gastos Menores Electrónicos"),
    ("e-44", "e-44 Regímenes Especiales Electrónicos"),
    ("e-45", "e-45 Gubernamental Electrónico"),
    ("e-46", "e-46 Comprobante para Exportaciones Electrónicas"),
    ("e-47", "e-47 Comprobante para Pagos al Exterior Electrónico"),
]


class L10nLatamDocumentType(models.Model):
    _inherit = "l10n_latam.document.type"

    l10n_do_ncf_type = fields.Selection(
        selection=NCF_TYPE_SELECTION,
        string="e-CF NCF Type",
        help="Selects the DGII e-CF document type code for electronic fiscal invoicing.",
    )
