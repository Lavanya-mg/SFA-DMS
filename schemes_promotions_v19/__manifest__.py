# -*- coding: utf-8 -*-
{
    'name': 'Schemes & Promotions',
    'version': '19.0.1.0.0',
    'summary': 'FMCG Scheme & Promotion management — 8 types × 4 benefit types',
    'category': 'Sales',
    'author': 'Senior Odoo Developer',
    'license': 'OPL-1',
    'depends': [
        'sale_management',
        'product',
        'account',
        'mail',
        'web',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/scheme_promotion_views.xml',
        'views/sale_order_scheme_views.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'schemes_promotions_v19/static/src/css/scheme.css',
            'schemes_promotions_v19/static/src/css/scheme_manager.css',
            'schemes_promotions_v19/static/src/js/scheme_manager.js',
            'schemes_promotions_v19/static/src/xml/scheme_manager.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'sequence': 20,
}
