# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime, timedelta


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def get_statement_data(self, move_ids=None, date_from=None, date_to=None):
        """
        Generate statement data for a partner, including invoices,
        credit notes, and customer payments.
        """
        self.ensure_one()

        today = datetime.now().date()

        # Determine date range
        if date_from:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date() if isinstance(date_from, str) else date_from
        if date_to:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date() if isinstance(date_to, str) else date_to

        # --- 1. Query invoices / credit notes ---
        move_domain = [
            ('partner_id', '=', self.id),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('state', '=', 'posted'),
        ]
        if date_from:
            move_domain.append(('invoice_date', '>=', date_from))
        if date_to:
            move_domain.append(('invoice_date', '<=', date_to))

        moves = self.env['account.move'].search(move_domain, order='invoice_date asc')
        if move_ids:
            moves = moves.filtered(lambda m: m.id in move_ids)

        # --- 2. Query customer payments ---
        payment_domain = [
            ('partner_id', '=', self.id),
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
        ]
        if date_from:
            payment_domain.append(('date', '>=', date_from))
        if date_to:
            payment_domain.append(('date', '<=', date_to))

        payments = self.env['account.payment'].search(payment_domain, order='date asc')

        # --- 3. Build unified transaction list ---
        raw_transactions = []

        for move in moves:
            if move.move_type == 'out_invoice':
                debit = move.amount_total
                credit = 0.0
                ttype = 'invoice'
            else:  # out_refund
                debit = 0.0
                credit = move.amount_total
                ttype = 'refund'

            is_overdue = False
            days_overdue = 0
            if move.move_type == 'out_invoice' and move.invoice_date_due:
                if move.amount_residual > 0 and move.invoice_date_due < today:
                    is_overdue = True
                    days_overdue = (today - move.invoice_date_due).days

            raw_transactions.append({
                'sort_date': move.invoice_date,
                'date': move.invoice_date,
                'due_date': move.invoice_date_due,
                'document': move.name,
                'description': move.ref or move.narration or '',
                'type': ttype,
                'debit': debit,
                'credit': credit,
                'is_overdue': is_overdue,
                'days_overdue': days_overdue,
                'residual': move.amount_residual,
            })

        for payment in payments:
            raw_transactions.append({
                'sort_date': payment.date,
                'date': payment.date,
                'due_date': None,
                'document': payment.name or (payment.move_id.name if payment.move_id else 'Pago'),
                'description': payment.ref or 'Abono / Pago recibido',
                'type': 'payment',
                'debit': 0.0,
                'credit': payment.amount,
                'is_overdue': False,
                'days_overdue': 0,
                'residual': 0,
            })

        # Sort all transactions by date
        raw_transactions.sort(key=lambda t: t['sort_date'] or datetime.min.date())

        # Compute running balance
        transactions = []
        running_balance = 0.0
        for t in raw_transactions:
            running_balance += (t['debit'] - t['credit'])
            t['balance'] = running_balance
            transactions.append(t)

        # Calculate totals
        total_debit = sum(t['debit'] for t in transactions)
        total_credit = sum(t['credit'] for t in transactions)
        final_balance = running_balance

        # Calculate aging buckets (only for overdue invoices)
        aging = {
            '0_30': 0.0,
            '31_60': 0.0,
            '61_90': 0.0,
            '90_plus': 0.0,
        }

        for t in transactions:
            if t['type'] == 'invoice' and t['is_overdue'] and t['residual'] > 0:
                days = t['days_overdue']
                if days <= 30:
                    aging['0_30'] += t['residual']
                elif days <= 60:
                    aging['31_60'] += t['residual']
                elif days <= 90:
                    aging['61_90'] += t['residual']
                else:
                    aging['90_plus'] += t['residual']

        overdue_balance = sum(aging.values())
        total_payments = sum(t['credit'] for t in transactions if t['type'] == 'payment')

        return {
            'partner': self,
            'transactions': transactions,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'total_payments': total_payments,
            'final_balance': final_balance,
            'overdue_balance': max(0, overdue_balance),
            'aging': aging,
            'statement_date': today,
            'date_from': date_from,
            'date_to': date_to,
        }

    def get_consolidated_statement_data(self, date_from=None, date_to=None):
        """
        Generate a consolidated statement covering all selected partners.
        Returns a list of per-partner summaries plus overall totals.
        """
        self.ensure_one()  # kept for compatibility; caller iterates externally

        today = datetime.now().date()

        if date_from:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date() if isinstance(date_from, str) else date_from
        if date_to:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date() if isinstance(date_to, str) else date_to

        # For a single partner in consolidated mode we just return the same structure
        data = self.get_statement_data(date_from=date_from, date_to=date_to)
        data['total_payments'] = sum(
            t['credit'] for t in data['transactions'] if t['type'] == 'payment'
        )
        return data
