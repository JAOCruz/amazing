# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CreateInvoiceWizard(models.TransientModel):
    _name = 'create.invoice.wizard'
    _description = 'Wizard para Crear Factura desde Orden de Manufactura'

    # ============================================
    # CAMPOS DEL ENCABEZADO
    # ============================================

    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de Manufactura',
        readonly=True,
        required=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente (Facturar a)',
        required=True,
        help='Doctor o clínica a quien se emite la factura',
    )
    invoice_date = fields.Date(
        string='Fecha de Factura',
        default=fields.Date.context_today,
        required=True,
    )
    payment_term_id = fields.Many2one(
        'account.payment.term',
        string='Plazo de Pago',
    )
    fiscal_receipt = fields.Selection([
        ('with', 'Con Comprobante Fiscal'),
        ('without', 'Sin Comprobante Fiscal'),
    ], string='Comprobante Fiscal', default='with', required=True,
        help='Indica si la factura lleva comprobante fiscal (NCF) o no')
    fiscal_position_id = fields.Many2one(
        'account.fiscal.position',
        string='Posición Fiscal',
        help='Posición fiscal que determina las reglas de impuestos',
    )
    notes = fields.Text(
        string='Notas',
        help='Notas adicionales que aparecerán en la factura',
    )

    # ============================================
    # LÍNEAS DE FACTURA
    # ============================================

    line_ids = fields.One2many(
        'create.invoice.wizard.line',
        'wizard_id',
        string='Líneas de Factura',
    )

    # ============================================
    # DEFAULT GET
    # ============================================

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        production_id = res.get('production_id') or self.env.context.get('default_production_id')
        if production_id:
            production = self.env['mrp.production'].browse(production_id)
            if production.exists():
                # Auto-fill partner from doctor or clinic
                if not res.get('partner_id'):
                    res['partner_id'] = (
                        production.doctor_id.id
                        if production.doctor_id
                        else production.clinic_id.id
                        if production.clinic_id
                        else False
                    )
                # Pre-create a default line from the MO data
                product_name = production.product_id.name or 'Servicio'
                patient_name = production.patient_name or ''
                description = f"{product_name}"
                if patient_name:
                    description += f" - Paciente: {patient_name}"

                qty = production.teeth_count if production.teeth_count > 0 else 1.0

                res['line_ids'] = [(0, 0, {
                    'name': description,
                    'product_id': production.product_id.id if production.product_id else False,
                    'quantity': qty,
                    'price_unit': 0.0,
                })]
        return res

    # ============================================
    # CREAR FACTURA
    # ============================================

    def action_create_invoice(self):
        self.ensure_one()

        if not self.line_ids:
            raise UserError(_("Debe agregar al menos una línea de factura."))

        if not self.partner_id:
            raise UserError(_("Debe seleccionar un cliente para facturar."))

        # Build invoice line vals
        invoice_line_vals = []
        for line in self.line_ids:
            line_vals = {
                'name': line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
            }
            if line.product_id:
                line_vals['product_id'] = line.product_id.id
            invoice_line_vals.append((0, 0, line_vals))

        # Create the invoice
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'production_id': self.production_id.id,
            'invoice_date': self.invoice_date,
            'payment_reference': self.production_id.name,
            'narration': self.notes,
            'invoice_payment_term_id': self.payment_term_id.id if self.payment_term_id else False,
            'invoice_line_ids': invoice_line_vals,
        }
        if self.fiscal_position_id:
            invoice_vals['fiscal_position_id'] = self.fiscal_position_id.id

        invoice = self.env['account.move'].create(invoice_vals)

        # Open the created invoice in form view
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }


class CreateInvoiceWizardLine(models.TransientModel):
    _name = 'create.invoice.wizard.line'
    _description = 'Línea de Factura del Wizard'

    wizard_id = fields.Many2one(
        'create.invoice.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade',
    )
    name = fields.Char(
        string='Descripción',
        required=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        help='Producto opcional para categorización contable',
    )
    quantity = fields.Float(
        string='Cantidad',
        default=1.0,
        required=True,
    )
    price_unit = fields.Float(
        string='Precio Unitario',
        required=True,
    )
    price_subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_price_subtotal',
    )

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
