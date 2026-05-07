# -*- coding: utf-8 -*-
# Part of Odoo Module Developed by Bizople Solutions Pvt. Ltd.
# See LICENSE file for full copyright and licensing details.
{
    # Theme information
    'name': 'Grocery Theme Common',
    'category': 'Website',
    'version': '18.0.0.0',
    'author': 'Bizople Solutions Pvt. Ltd.',
    'website': 'https://www.bizople.com',
    'summary': 'Grocery Theme Common',
    'description': """Grocery Theme Common""",
    'depends': [
        'website_blog',
        'website_sale_wishlist',
        'website_sale_comparison',
        # 'website_sale_product_configurator',
    ],

    'data': [
        'security/ir.model.access.csv',
        'data/data.xml',
        'views/manifest.xml',
        'views/pwa_offline.xml',
        'views/brand_template.xml',
        'views/category_template.xml',
        'views/megamenus/megamenu_one_snippet.xml',
        'views/megamenus/megamenu_four_snippet.xml',
        'report/sale_order_store_field.xml',
    ],

    'images': [
        'static/description/banner.png'
    ],

    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
    'price': 25,
    'currency': 'EUR',
}
