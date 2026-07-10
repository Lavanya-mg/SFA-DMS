# -*- coding: utf-8 -*-
{
    'name': 'KPI Target & Actual Tracker ',
    'version': '19.0.2.0.0',
    'category': 'Human Resources',
    'summary': 'Track employee KPI targets and actuals with OWL dashboard ',
    'description': """
        Employee KPI Target & Actual Tracker
        =====================================
        * Track KPI targets by period (monthly/quarterly/yearly)
        * Individual and team targets with distribution mode
        * Record actual achievements (manual + auto-computed)
        * Calculate achievement percentages per KPI type
        * Interactive OWL dashboard for data entry and visualization
        * Odoo 19 Enterprise — updated APIs, Enterprise UI
    """,
    'author': 'Senior Odoo Developer',
    'website': '',
    'license': 'OPL-1',
    'depends': ['base', 'hr', 'web', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/kpi_target_views.xml',
        'views/kpi_metric_views.xml',
        'views/kpi_analytics_views.xml',
        'views/kpi_target_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'kpi_target_v19/static/src/components/kpi_dashboard/**/*',
            'kpi_target_v19/static/src/components/kpi_metric_manager/kpi_metric_manager.css',
            'kpi_target_v19/static/src/components/kpi_metric_manager/kpi_metric_manager.js',
            'kpi_target_v19/static/src/components/kpi_metric_manager/kpi_metric_manager.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
