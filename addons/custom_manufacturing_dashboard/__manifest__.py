# -*- coding: utf-8 -*-
{
    'name': 'Custom Manufacturing Dashboard',
    'version': '18.0.1.2.0',
    'category': 'Manufacturing',
    'summary': 'Dashboard de manufactura dental con timer en tiempo real y sistema de alertas',
    'description': """
        Manufacturing Dashboard para Laboratorio Dental
        ===============================================

        Características principales:
        * Dashboard en tiempo real con timer
        * Sistema de alertas automáticas (delayed/urgent/pending)
        * Gestión de órdenes de manufactura de prótesis dentales
        * Sistema de dientes (FDI)
        * Dashboard individual por empleado
        * Vistas Kanban para asignación de operaciones
        * Sistema de notificaciones por email
        * Seguimiento de materiales recibidos
        * Alertas en cascada para operaciones
    """,
    'author': 'Your Company',
    'website': 'https://www.yourcompany.com',
    'license': 'LGPL-3',

    # Dependencias
    'depends': [
        'base',
        'mrp',                      # Manufacturing
        'account',                  # Facturación
        'portal',                   # Portal functionality
        'mail',                     # Para notificaciones por email
        'web',                      # Para componentes OWL
        'mrp_workorder_chatter',    # Mensajería en workorders
    ],

    # Archivos de datos
    'data': [
        # Seguridad (debe ir primero)
        'security/security.xml',
        'security/ir.model.access.csv',
        'security/ir_rule.xml',

        # Data inicial (categorías de contactos)
        'data/contact_categories.xml',

        # Vistas
        'views/manufacturing_bill_views.xml',
        'views/dashboard_view.xml',
        'views/employee_dashboard_view.xml',
        'views/mrp_production_views.xml',
        'views/mrp_workorder_views.xml',
        'views/mrp_workorder_test_button.xml',
        'views/portal_templates.xml',
        'views/appbot_appointment_views.xml',

        # Wizard (debe ir antes del menú para que la acción esté disponible)
        'wizard/create_order_wizard_views_fixed.xml',
        'wizard/create_invoice_wizard_views.xml',

        # Menú (debe ir después de todas las acciones)
        'views/menu.xml',

        # Data (templates y acciones programadas)
        'data/mail_templates.xml',
        'data/scheduled_actions.xml',
        'data/server_actions.xml',

        # Reportes PDF
        'reports/mrp_patient_report.xml',
        'reports/mrp_tooth_chart_report.xml',
        'reports/manufacturing_bill_report.xml',
    ],

    # Datos de demostración
    'demo': [
        'data/demo_data.xml',
    ],

    # Assets para Odoo 18
    'assets': {
        'web.assets_backend': [
            # JavaScript (OWL components)
            'custom_manufacturing_dashboard/static/src/js/dashboard.js',
            'custom_manufacturing_dashboard/static/src/js/employee_dashboard.js',
            'custom_manufacturing_dashboard/static/src/js/form_pager_patch.js',
            'custom_manufacturing_dashboard/static/src/js/teeth_selector.js',
            'custom_manufacturing_dashboard/static/src/js/teeth_selector_edit.js',
            'custom_manufacturing_dashboard/static/src/js/teeth_display.js',

            # QWeb Templates
            'custom_manufacturing_dashboard/static/src/xml/dashboard.xml',
            'custom_manufacturing_dashboard/static/src/xml/employee_dashboard.xml',
            'custom_manufacturing_dashboard/static/src/xml/teeth_selector.xml',
            'custom_manufacturing_dashboard/static/src/xml/teeth_selector_edit.xml',
            'custom_manufacturing_dashboard/static/src/xml/teeth_display.xml',

            # Estilos SCSS
            'custom_manufacturing_dashboard/static/src/scss/backend.scss',
            'custom_manufacturing_dashboard/static/src/scss/dashboard.scss',
            'custom_manufacturing_dashboard/static/src/scss/workorder_kanban.scss',
        ],
        'web.assets_frontend': [
            'custom_manufacturing_dashboard/static/src/scss/portal_dashboard.scss',
        ],
    },

    # Información adicional
    'application': True,
    'installable': True,
    'auto_install': False,

    # Imágenes
    'images': ['static/description/banner.png'],

    # External dependencies (si las hay)
    'external_dependencies': {
        'python': [],
        'bin': [],
    },
}