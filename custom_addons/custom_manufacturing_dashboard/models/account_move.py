# -*- coding: utf-8 -*-

from odoo import models, fields


class AccountMove(models.Model):
    _inherit = 'account.move'

    production_id = fields.Many2one(
        'mrp.production',
        string='Orden de Manufactura',
        index=True,
        copy=False,
        help='Orden de manufactura asociada a esta factura',
    )
