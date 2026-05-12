# -*- coding: utf-8 -*-
{
    'name': 'Estado de Cuenta del Cliente',
    'version': '18.0.1.0.0',
    'category': 'Invoicing',
    'summary': 'Generar y enviar estados de cuenta desde la lista de facturas',
    'description': """
        Custom module to generate customer account statements in Odoo 18 Community.

        Features:
        * Select multiple invoices of same customer → Print Statement
        * PDF statement with company branding (logo, layout, colors)
        * Send statement by email to customer
        * Shows invoice history, payments, running balance, overdue amounts
        * Configurable date range for statement period
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'wizard/customer_statement_wizard_views.xml',
        'wizard/customer_statement_batch_wizard_views.xml',
        'reports/customer_statement_report.xml',
        'reports/conduce_report.xml',
        'reports/sales_report_wizard_views.xml',
        'reports/sales_report_template.xml',
        'views/account_move_actions.xml',
        'views/account_move_views.xml',
    ],
    'application': False,
    'installable': True,
    'auto_install': False,
}
