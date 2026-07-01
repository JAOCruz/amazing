from odoo import models, fields, api


class GauchPropaneOrder(models.Model):
    _name = 'gauch.propane.order'
    _description = 'Entrega de Gas Propano'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Número',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('gauch.propane.order') or 'Nuevo'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
        tracking=True
    )
    date = fields.Date(
        string='Fecha',
        default=fields.Date.today,
        required=True
    )
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('confirmed', 'Confirmada'),
        ('delivered', 'Entregada'),
        ('returned', 'Devuelta'),
        ('done', 'Finalizada'),
        ('cancel', 'Cancelada'),
    ], string='Estado', default='draft', tracking=True)

    line_ids = fields.One2many(
        'gauch.propane.order.line',
        'order_id',
        string='Líneas'
    )

    total_full_delivered = fields.Integer(
        string='Cilindros llenos entregados',
        compute='_compute_totals',
        store=True
    )
    total_empty_returned = fields.Integer(
        string='Cilindros vacíos devueltos',
        compute='_compute_totals',
        store=True
    )
    total_empty_pending = fields.Integer(
        string='Cilindros vacíos pendientes',
        compute='_compute_totals',
        store=True
    )

    @api.depends('line_ids.quantity_full', 'line_ids.quantity_empty_returned')
    def _compute_totals(self):
        for order in self:
            order.total_full_delivered = sum(order.line_ids.mapped('quantity_full'))
            order.total_empty_returned = sum(order.line_ids.mapped('quantity_empty_returned'))
            order.total_empty_pending = order.total_full_delivered - order.total_empty_returned

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_deliver(self):
        self.write({'state': 'delivered'})

    def action_return(self):
        self.write({'state': 'returned'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})


class GauchPropaneOrderLine(models.Model):
    _name = 'gauch.propane.order.line'
    _description = 'Línea de Entrega de Gas'

    order_id = fields.Many2one(
        'gauch.propane.order',
        string='Orden',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        domain=[('categ_id.name', '=', 'Propano')],
        required=True
    )
    quantity_full = fields.Integer(
        string='Cilindros llenos',
        default=1,
        required=True
    )
    quantity_empty_returned = fields.Integer(
        string='Vacíos devueltos',
        default=0,
        required=True
    )
    notes = fields.Char(string='Notas')
