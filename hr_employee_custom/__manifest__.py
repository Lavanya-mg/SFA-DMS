{
    'name': 'HR Employee Custom Fields',
    'version': '19.0.1.0.0',
    'depends': ['hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/day_data.xml',
        'views/hr_employee_views.xml',
    ],
    'assets': {
    'web.assets_backend': [
        'hr_employee_custom/static/src/css/custom_styles.css',
    ],
},
    'installable': True,
    'application': False,
}