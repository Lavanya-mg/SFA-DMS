# -*- coding: utf-8 -*-
from odoo import models, fields

KPI_TYPE_SELECTION = [
    ('orders', 'Orders'),
    ('visits', 'Visits'),
    ('new_dealers', 'New Dealers'),
    ('payment_collected', 'Payment Collected'),
    ('complaints_solved', 'Complaints Solved'),
]


class KpiTargetItem(models.Model):
    _name = 'kpi.target.item'
    _description = 'KPI Target Item'
    _sql_constraints = [
        ('unique_target_kpi', 'UNIQUE(target_id, kpi_type)', 'Each KPI type must be unique per target!')
    ]

    target_id = fields.Many2one('kpi.target', string='Target', required=True, ondelete='cascade')
    kpi_type = fields.Selection(KPI_TYPE_SELECTION, string='KPI Type', required=True)
    target_value = fields.Float(string='Target Value', default=0.0)
