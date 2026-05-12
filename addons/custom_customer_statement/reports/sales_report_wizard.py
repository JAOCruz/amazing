# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SalesReportWizard(models.TransientModel):
    _name = 'sales.report.wizard'
    _description = 'Sales Report by Period'

    date_from = fields.Date(string='Desde', required=True)
    date_to = fields.Date(string='Hasta', required=True)
    group_by = fields.Selection([
        ('customer', 'Por Cliente'),
        ('product', 'Por Producto'),
    ], string='Agrupar por', default='customer')
    partner_id = fields.Many2one('res.partner', string='Cliente específico')

    def action_generate_report(self):
        """Generate and return the sales report PDF."""
        return {
            'type': 'ir.actions.report',
            'report_name': 'custom_customer_statement.report_sales_by_period',
            'report_type': 'qweb-pdf',
            'data': {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'group_by': self.group_by,
                'partner_id': self.partner_id.id if self.partner_id else False,
            },
        }

    def _get_report_data(self):
        """Compute report lines grouped by customer or product."""
        self.ensure_one()
        domain = [
            ('move_id.move_type', 'in', ['out_invoice', 'out_refund']),
            ('move_id.state', '=', 'posted'),
            ('move_id.invoice_date', '>=', self.date_from),
            ('move_id.invoice_date', '<=', self.date_to),
        ]
        if self.partner_id:
            domain.append(('move_id.partner_id', '=', self.partner_id.id))

        lines = self.env['account.move.line'].search(domain)
        results = []
        total = 0.0

        if self.group_by == 'customer':
            grouped = {}
            for line in lines:
                partner = line.move_id.partner_id
                if partner not in grouped:
                    grouped[partner] = {'amount': 0.0, 'count': 0}
                grouped[partner]['amount'] += line.price_subtotal
                grouped[partner]['count'] += line.quantity
            for partner, data in sorted(grouped.items(), key=lambda x: x[1]['amount'], reverse=True):
                results.append({
                    'name': partner.name,
                    'quantity': data['count'],
                    'amount': data['amount'],
                })
                total += data['amount']
        else:  # product
            grouped = {}
            for line in lines:
                product = line.product_id
                name = product.name if product else line.name
                if name not in grouped:
                    grouped[name] = {'amount': 0.0, 'count': 0}
                grouped[name]['amount'] += line.price_subtotal
                grouped[name]['count'] += line.quantity
            for name, data in sorted(grouped.items(), key=lambda x: x[1]['amount'], reverse=True):
                results.append({
                    'name': name,
                    'quantity': data['count'],
                    'amount': data['amount'],
                })
                total += data['amount']

        return {
            'lines': results,
            'total': total,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'group_by_label': 'Cliente' if self.group_by == 'customer' else 'Producto',
        }
