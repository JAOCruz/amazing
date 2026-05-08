# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CustomerStatementWizard(models.TransientModel):
    _name = 'customer.statement.wizard'
    _description = 'Customer Statement Generator'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    move_ids = fields.Many2many('account.move', string='Invoices')
    date_from = fields.Date(string='Statement From')
    date_to = fields.Date(string='Statement To')
    include_payments = fields.Boolean(string='Include Payments', default=True)

    # Preview fields for display
    total_invoices = fields.Integer('Total Invoices', compute='_compute_statement_preview')
    total_amount = fields.Float('Total Amount', compute='_compute_statement_preview')
    total_paid = fields.Float('Total Paid', compute='_compute_statement_preview')
    balance_due = fields.Float('Balance Due', compute='_compute_statement_preview')
    aging_0_30 = fields.Float('0-30 Days Overdue', compute='_compute_statement_preview')
    aging_31_60 = fields.Float('31-60 Days Overdue', compute='_compute_statement_preview')
    aging_61_90 = fields.Float('61-90 Days Overdue', compute='_compute_statement_preview')
    aging_90_plus = fields.Float('90+ Days Overdue', compute='_compute_statement_preview')
    statement_data = fields.Text('Statement Data', compute='_compute_statement_data')

    @api.depends('move_ids', 'date_from', 'date_to')
    def _compute_statement_preview(self):
        for wizard in self:
            if wizard.partner_id and wizard.move_ids:
                statement_data = wizard.partner_id.get_statement_data(
                    move_ids=wizard.move_ids.ids,
                    date_from=wizard.date_from,
                    date_to=wizard.date_to
                )
                wizard.total_invoices = len(statement_data['transactions'])
                wizard.total_amount = statement_data['total_debit']
                wizard.total_paid = statement_data['total_credit']
                wizard.balance_due = statement_data['final_balance']
                wizard.aging_0_30 = statement_data['aging']['0_30']
                wizard.aging_31_60 = statement_data['aging']['31_60']
                wizard.aging_61_90 = statement_data['aging']['61_90']
                wizard.aging_90_plus = statement_data['aging']['90_plus']
            else:
                wizard.total_invoices = 0
                wizard.total_amount = 0.0
                wizard.total_paid = 0.0
                wizard.balance_due = 0.0
                wizard.aging_0_30 = 0.0
                wizard.aging_31_60 = 0.0
                wizard.aging_61_90 = 0.0
                wizard.aging_90_plus = 0.0

    @api.depends('partner_id', 'move_ids')
    def _compute_statement_data(self):
        for wizard in self:
            if wizard.partner_id:
                data = wizard.partner_id.get_statement_data(
                    move_ids=wizard.move_ids.ids if wizard.move_ids else None,
                    date_from=wizard.date_from,
                    date_to=wizard.date_to
                )
                wizard.statement_data = str(data)
            else:
                wizard.statement_data = ''

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        # Only auto-populate if called from invoice list
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids', [])
        
        if active_model != 'account.move' or not active_ids:
            return res

        # Load the moves
        moves = self.env['account.move'].browse(active_ids)
        moves = moves.filtered(lambda m: m.move_type in ['out_invoice', 'out_refund'] and m.state == 'posted')

        if not moves:
            raise ValidationError('No valid invoices selected.')

        # Check all moves belong to same partner
        partners = moves.mapped('partner_id')
        if len(partners) > 1:
            raise ValidationError('All invoices must belong to the same customer.')

        res['partner_id'] = partners[0].id
        res['move_ids'] = [(6, 0, moves.ids)]

        return res

    def action_print_pdf(self):
        """Generate and print the statement PDF."""
        return {
            'type': 'ir.actions.report',
            'report_name': 'custom_customer_statement.report_customer_statement',
            'report_type': 'qweb-pdf',
            'data': {},
            'context': {
                'wizard_id': self.id,
                'partner_id': self.partner_id.id,
                'move_ids': self.move_ids.ids,
                'date_from': self.date_from,
                'date_to': self.date_to,
            },
        }

    def action_send_email(self):
        """Open email compose wizard with statement PDF attached."""
        # Generate the PDF
        pdf_content, pdf_filename = self.env['ir.actions.report']._render_qweb_pdf(
            'custom_customer_statement.report_customer_statement',
            [self.id],
        )

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'Estado_de_Cuenta_{self.partner_id.name.replace(" ", "_")}.pdf',
            'type': 'binary',
            'datas': pdf_content,
            'res_model': 'res.partner',
            'res_id': self.partner_id.id,
        })

        # Open email compose dialog
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_model': 'res.partner',
                'default_res_id': self.partner_id.id,
                'default_partner_ids': [(4, self.partner_id.id)],
                'default_attachment_ids': [(4, attachment.id)],
                'default_subject': f'Estado de Cuenta - {self.partner_id.name}',
                'default_body': f'Estimado {self.partner_id.name},\n\nAdjunto encontrará su estado de cuenta actualizado.\n\nSaludos cordiales',
            },
        }
