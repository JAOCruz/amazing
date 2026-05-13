# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CustomerStatementBatchWizard(models.TransientModel):
    _name = 'customer.statement.batch.wizard'
    _description = 'Batch Customer Statement Generator'

    partner_ids = fields.Many2many(
        'res.partner',
        string='Customers',
        required=True,
        domain=[('customer_rank', '>', 0)],
        help='Select customers to generate statements for. Defaults to all customers with invoices.'
    )
    date_from = fields.Date(string='Statement From')
    date_to = fields.Date(string='Statement To')
    include_payments = fields.Boolean(string='Include Payments', default=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # If called from partner list with selection, use those
        active_ids = self.env.context.get('active_ids', [])
        active_model = self.env.context.get('active_model', '')
        
        if active_model == 'res.partner' and active_ids:
            res['partner_ids'] = [(6, 0, active_ids)]
        else:
            # Default: all customers with posted invoices
            partners = self.env['res.partner'].search([
                ('customer_rank', '>', 0),
            ])
            # Filter to those who actually have invoices
            partners_with_invoices = partners.filtered(
                lambda p: self.env['account.move'].search_count([
                    ('partner_id', '=', p.id),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                    ('state', '=', 'posted'),
                ]) > 0
            )
            res['partner_ids'] = [(6, 0, partners_with_invoices.ids)]
        
        return res

    def action_generate_statements(self):
        """Generate PDF statements for all selected customers."""
        if not self.partner_ids:
            raise ValidationError('Please select at least one customer.')

        # Limit batch size to avoid wkhtmltopdf memory errors
        MAX_BATCH = 30
        if len(self.partner_ids) > MAX_BATCH:
            raise ValidationError(
                f'Se seleccionaron {len(self.partner_ids)} clientes. '
                f'Por seguridad el limite es {MAX_BATCH} clientes por batch. '
                f'Por favor filtre la seleccion e intente de nuevo.'
            )

        # Create individual wizard records for each partner
        # Use a clean context that explicitly tells the single wizard to skip
        # invoice-list validation (active_model / active_ids may still leak
        # through Odoo's RPC layer even after pop()).
        ctx = dict(self.env.context)
        ctx.pop('active_ids', None)
        ctx.pop('active_model', None)
        ctx.pop('active_id', None)
        ctx['statement_batch_mode'] = True
        Wizard = self.env['customer.statement.wizard'].with_context(**ctx)
        wizard_ids = []
        
        for partner in self.partner_ids:
            wizard = Wizard.create({
                'partner_id': partner.id,
                'date_from': self.date_from,
                'date_to': self.date_to,
                'include_payments': self.include_payments,
            })
            wizard_ids.append(wizard.id)
        
        # Call the existing report for all wizard records
        return {
            'type': 'ir.actions.report',
            'report_name': 'custom_customer_statement.report_customer_statement',
            'report_type': 'qweb-pdf',
            'data': {},
            'context': {
                'active_ids': wizard_ids,
                'active_model': 'customer.statement.wizard',
            },
        }
