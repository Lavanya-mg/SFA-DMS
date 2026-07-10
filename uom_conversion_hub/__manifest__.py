{
    'name': 'Custom  UoM Conversion Hub',
    'version': '19.0.1.0.0',
    'summary': 'Manage specific item packaging metrics from simple units to master containers',
    'category': 'Inventory/Logistics',
    'depends': [
        'base',
        'sale',
        'product',
        'uom',
        'stock',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/uom_conversion_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}