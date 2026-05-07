# -*- coding: utf-8 -*-

import json
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)


class ManufacturingBill(models.Model):
    _name = 'manufacturing.bill'
    _description = 'Factura de Manufactura'
    _order = 'create_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # ============================================
    # CAMPOS PRINCIPALES
    # ============================================

    name = fields.Char(
        string='Número',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de Manufactura',
        required=True,
        index=True,
        ondelete='restrict',
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Facturar a',
        required=True,
        tracking=True,
        help='Doctor o clínica a quien se emite la factura',
    )
    patient_name = fields.Char(
        string='Paciente',
        help='Nombre del paciente (copiado de la MO)',
    )
    extra_percentage = fields.Float(
        related='production_id.extra_percentage',
        string='% Recargo Extra',
        store=True,
    )
    extra_percentage_reason = fields.Char(
        related='production_id.extra_percentage_reason',
        string='Motivo del Recargo',
        store=True,
    )
    date_bill = fields.Date(
        string='Fecha',
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmada'),
        ('invoiced', 'Facturada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', default='draft', required=True, tracking=True, copy=False)

    line_ids = fields.One2many(
        'manufacturing.bill.line',
        'bill_id',
        string='Líneas',
        copy=True,
    )
    notes = fields.Text(string='Notas Internas')

    # ============================================
    # COMPROBANTE FISCAL
    # ============================================

    fiscal_receipt = fields.Selection([
        ('with', 'Con Comprobante Fiscal'),
        ('without', 'Sin Comprobante Fiscal'),
    ], string='Comprobante Fiscal', default='with', required=True, tracking=True,
        help='Indica si la factura lleva comprobante fiscal (NCF) o no')
    fiscal_position_id = fields.Many2one(
        'account.fiscal.position',
        string='Posición Fiscal',
        tracking=True,
        help='Posición fiscal que determina las reglas de impuestos (NCF, tipo de comprobante)',
    )

    # ============================================
    # MONTOS
    # ============================================

    amount_untaxed = fields.Float(
        string='Subtotal',
        compute='_compute_amounts',
        store=True,
    )
    amount_discount = fields.Float(
        string='Descuento Global',
        default=0.0,
        tracking=True,
    )
    amount_total = fields.Float(
        string='Total',
        compute='_compute_amounts',
        store=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id.id,
        required=True,
    )

    # ============================================
    # ENLACE A FACTURA ODOO
    # ============================================

    invoice_id = fields.Many2one(
        'account.move',
        string='Factura Odoo',
        readonly=True,
        copy=False,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compañía',
        default=lambda self: self.env.company,
        required=True,
    )

    # ============================================
    # COMPUTED FIELDS
    # ============================================

    @api.depends('line_ids.price_subtotal', 'amount_discount')
    def _compute_amounts(self):
        for bill in self:
            amount_untaxed = sum(line.price_subtotal for line in bill.line_ids)
            bill.amount_untaxed = amount_untaxed
            bill.amount_total = amount_untaxed - bill.amount_discount

    # ============================================
    # CRUD OVERRIDES
    # ============================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('manufacturing.bill') or _('New')
        return super().create(vals_list)

    # ============================================
    # BUSINESS METHODS
    # ============================================

    def action_confirm(self):
        for bill in self:
            if bill.state != 'draft':
                raise UserError(_("Solo se pueden confirmar facturas en estado borrador."))
            if not bill.line_ids:
                raise UserError(_("Debe agregar al menos una línea antes de confirmar."))
            bill.state = 'confirmed'

    def action_cancel(self):
        for bill in self:
            if bill.state == 'invoiced':
                raise UserError(_("No se puede cancelar una factura ya generada en contabilidad. Cancele primero la factura Odoo."))
            bill.state = 'cancelled'

    def action_reset_to_draft(self):
        for bill in self:
            if bill.state == 'invoiced':
                raise UserError(_("No se puede regresar a borrador una factura ya generada."))
            bill.state = 'draft'

    def action_create_invoice(self):
        """Generate a linked account.move (Odoo invoice) from this bill. Manager only."""
        self.ensure_one()

        if not self.env.user.has_group('custom_manufacturing_dashboard.group_manufacturing_manager'):
            raise AccessError(_("Solo un gerente puede generar facturas contables."))

        if self.state != 'confirmed':
            raise UserError(_("La factura de manufactura debe estar confirmada antes de generar la factura contable."))

        if self.invoice_id:
            raise UserError(_("Ya existe una factura Odoo vinculada: %s") % self.invoice_id.name)

        # Build invoice lines
        invoice_line_vals = []
        for line in self.line_ids:
            invoice_line_vals.append((0, 0, {
                'name': line.name,
                'quantity': line.quantity,
                'price_unit': line.price_unit,
            }))

        # Add discount line if applicable
        if self.amount_discount > 0:
            invoice_line_vals.append((0, 0, {
                'name': _('Descuento Global'),
                'quantity': 1,
                'price_unit': -self.amount_discount,
            }))

        # Create the Odoo invoice
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'production_id': self.production_id.id,
            'invoice_date': self.date_bill,
            'payment_reference': '%s / %s' % (self.production_id.name, self.name),
            'narration': self.notes,
            'invoice_line_ids': invoice_line_vals,
        }
        if self.fiscal_position_id:
            invoice_vals['fiscal_position_id'] = self.fiscal_position_id.id

        invoice = self.env['account.move'].create(invoice_vals)

        # Link and update state
        self.write({
            'invoice_id': invoice.id,
            'state': 'invoiced',
        })

        _logger.info("Invoice %s created from manufacturing bill %s", invoice.name, self.name)

        # Open the created invoice
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura'),
            'res_model': 'account.move',
            'res_id': invoice.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_invoice(self):
        """Open the linked Odoo invoice."""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError(_("No hay factura Odoo vinculada."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Factura'),
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }


class ManufacturingBillLine(models.Model):
    _name = 'manufacturing.bill.line'
    _description = 'Línea de Factura de Manufactura'
    _order = 'sequence, id'

    bill_id = fields.Many2one(
        'manufacturing.bill',
        string='Factura',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sequence = fields.Integer(string='Secuencia', default=10)
    product_type = fields.Selection(
        selection=[
            ('corona_zirconia', 'Corona Zirconia'),
            ('corona_zirconia_multicapa', 'Corona Zirconia Multicapa'),
            ('corona_emax', 'Corona E-max'),
            ('puente', 'Puente'),
            ('incrustacion', 'Incrustación'),
            ('carilla', 'Carilla'),
            ('protesis_parcial', 'Prótesis Parcial'),
            ('protesis_completa', 'Prótesis Completa'),
            ('provisional', 'Provisional'),
            ('otro', 'Otro'),
            ('encerado', 'Encerado'),
            ('planificacion', 'Planificación'),
            ('hibrida_metal', 'Híbrida Metal'),
            ('hibrida_zirconio', 'Híbrida Zirconio'),
            ('disilicato_monolitico', 'Disilicato Monolítico'),
            ('disilicato_estratificado', 'Disilicato Estratificado'),
            ('zirconio_monolitico', 'Zirconio Monolítico'),
            ('zirconio_estratificado', 'Zirconio Estratificado'),
            ('barra_blender', 'Barra Blender'),
        ],
        string='Producto',
        required=True,
    )
    name = fields.Char(
        string='Descripción',
    )
    quantity = fields.Float(
        string='Cantidad',
        default=1.0,
        required=True,
    )
    price_unit = fields.Float(
        string='Precio Unitario',
        required=True,
        default=0.0,
    )
    price_subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_price_subtotal',
        store=True,
    )

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
