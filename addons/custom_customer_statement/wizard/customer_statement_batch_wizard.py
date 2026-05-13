# -*- coding: utf-8 -*-
import base64
import io

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

    def _merge_pdfs(self, pdf_bytes_list):
        """Merge multiple PDF byte strings into a single PDF."""
        try:
            from pypdf import PdfWriter, PdfReader
        except ImportError:
            # Fallback for older PyPDF2 naming
            from PyPDF2 import PdfFileWriter as PdfWriter, PdfFileReader as PdfReader

        writer = PdfWriter()
        for pdf_bytes in pdf_bytes_list:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    def action_generate_statements(self):
        """Generate PDF statements for all selected customers."""
        if not self.partner_ids:
            raise ValidationError('Please select at least one customer.')

        # Create individual wizard records for each partner
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
        
        # Generate PDFs in small chunks to avoid wkhtmltopdf memory errors
        report = self.env['ir.actions.report']._get_report_from_name(
            'custom_customer_statement.report_customer_statement'
        )
        
        pdf_chunks = []
        chunk_size = 15  # wkhtmltopdf handles 15 pages comfortably
        for i in range(0, len(wizard_ids), chunk_size):
            chunk_ids = wizard_ids[i:i + chunk_size]
            pdf_content, _ = report._render_qweb_pdf(chunk_ids)
            pdf_chunks.append(pdf_content)
        
        # Merge all chunks into one PDF
        merged_pdf = self._merge_pdfs(pdf_chunks)
        
        # Create attachment for download
        attachment = self.env['ir.attachment'].create({
            'name': 'Estados_de_Cuenta.pdf',
            'type': 'binary',
            'datas': base64.b64encode(merged_pdf),
            'mimetype': 'application/pdf',
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=1',
            'target': 'self',
        }
