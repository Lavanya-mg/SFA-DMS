# -*- coding: utf-8 -*-
{
    'name': 'Beat Module ',
    'version': '19.0.1.1.0',
    'summary': 'Beat tracking with auto sequence, customer and employee link — Odoo 19 Enterprise',
    'author': 'Senior Odoo Developer',
    'category': 'Sales/Field Service',
    'license': 'OPL-1',
    'depends': ['base', 'contacts', 'hr', 'mail', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/beat_views.xml',
        'views/beat_analytics_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
