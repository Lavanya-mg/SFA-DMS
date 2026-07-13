# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    profile_id = fields.Many2one(
        'sfa.incentive.profile', string='Incentive Profile',
        help="Incentive profile (role) that drives which profile-specific "
             "incentive slabs apply to this employee.")
