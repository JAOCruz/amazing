# -*- coding: utf-8 -*-
{
    'name': 'ChartJS Fix - Workaround for Odoo 18',
    'version': '18.0.1.0.0',
    'category': 'Technical',
    'summary': 'Workaround para chartjs_lib.min.js en Odoo 18',
    'description': """
        Fix para el error de chartjs_lib.min.js
        Incluye Chart.js directamente en los assets del backend
    """,
    'depends': ['web'],
    'data': [],
    'assets': {
        'web.assets_backend': [
            '/web/static/lib/Chart/Chart.js',
            '/web/static/lib/chartjs-adapter-luxon/chartjs-adapter-luxon.js',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'LGPL-3',
}

