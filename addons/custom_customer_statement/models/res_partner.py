# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime, timedelta


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def get_statement_data(self, move_ids=None, date_from=None, date_to=None):
        """
        Generate statement data for a partner.

        Args:
            move_ids: list of account.move IDs (invoices) to include
            date_from: start date for statement period (optional)
            date_to: end date for statement period (optional)

        Returns:
            dict with statement data: partner, transactions, totals, overdue, aging
        """
        self.ensure_one()

        today = datetime.now().date()

        # Determine date range
        if date_from:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date() if isinstance(date_from, str) else date_from
        if date_to:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date() if isinstance(date_to, str) else date_to

        # Query invoices for this partner
        domain = [
            ('partner_id', '=', self.id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
        ]

        if date_from:
            domain.append(('invoice_date', '>=', date_from))
        if date_to:
            domain.append(('invoice_date', '<=', date_to))

        moves = self.env['account.move'].search(domain, order='invoice_date asc')

        # If specific move_ids provided, filter to those
        if move_ids:
            moves = moves.filtered(lambda m: m.id in move_ids)

        transactions = []
        running_balance = 0.0

        for move in moves:
            # Determine debit/credit based on move type
            if move.move_type == 'out_invoice':
                debit = move.amount_total
                credit = 0.0
            else:  # out_refund
                debit = 0.0
                credit = move.amount_total

            running_balance += (debit - credit)

            # Check if overdue and calculate days overdue
            is_overdue = False
            days_overdue = 0
            if move.move_type == 'out_invoice' and move.invoice_date_due:
                if move.amount_residual > 0 and move.invoice_date_due < today:
                    is_overdue = True
                    days_overdue = (today - move.invoice_date_due).days

            transactions.append({
                'date': move.invoice_date,
                'due_date': move.invoice_date_due,
                'document': move.name,
                'description': move.ref or move.narration or '',
                'debit': debit,
                'credit': credit,
                'balance': running_balance,
                'is_overdue': is_overdue,
                'days_overdue': days_overdue,
                'residual': move.amount_residual,
            })

        # Calculate totals
        total_debit = sum(t['debit'] for t in transactions)
        total_credit = sum(t['credit'] for t in transactions)
        final_balance = total_debit - total_credit

        # Calculate aging buckets
        aging = {
            '0_30': 0.0,      # 0-30 days overdue
            '31_60': 0.0,     # 31-60 days overdue
            '61_90': 0.0,     # 61-90 days overdue
            '90_plus': 0.0,   # 90+ days overdue
        }

        for trans in transactions:
            if trans['is_overdue'] and trans['residual'] > 0:
                days = trans['days_overdue']
                if days <= 30:
                    aging['0_30'] += trans['residual']
                elif days <= 60:
                    aging['31_60'] += trans['residual']
                elif days <= 90:
                    aging['61_90'] += trans['residual']
                else:
                    aging['90_plus'] += trans['residual']

        overdue_balance = sum(aging.values())

        return {
            'partner': self,
            'transactions': transactions,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'final_balance': final_balance,
            'overdue_balance': max(0, overdue_balance),
            'aging': aging,
            'statement_date': today,
            'date_from': date_from,
            'date_to': date_to,
        }
