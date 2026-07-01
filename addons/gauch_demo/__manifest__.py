{
    'name': 'Gauch Demo - Propano y Envases Retornables',
    'version': '18.0.1.0.0',
    'category': 'Sales/CRM',
    'summary': 'Datos demo y flujo básico de propano con envases retornables',
    'description': """
Módulo de demostración para Gauch (distribuidor de gas propano).

Incluye:
- Configuración de empresa de ejemplo
- Contactos y oportunidades demo en CRM
- Productos de propano y tanques retornables
- Modelo simple para rastrear entregas y devoluciones de cilindros
""",
    'author': 'Pillarware',
    'website': 'https://pillarware.io',
    'depends': [
        'base',
        'crm',
        'sale',
        'stock',
        'contacts',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/company_data.xml',
        'data/product_data.xml',
        'data/crm_data.xml',
        'views/propane_order_views.xml',
        'views/menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
