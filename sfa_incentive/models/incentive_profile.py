# -*- coding: utf-8 -*-
from odoo import models, fields


class SfaIncentiveProfile(models.Model):
    _name = 'sfa.incentive.profile'
    _description = 'Incentive Profile'
    _order = 'name'
    _sql_constraints = [('unique_name', 'UNIQUE(name)', 'Profile name must be unique.')]

    name = fields.Char('Profile Name', required=True)
    active = fields.Boolean(default=True)
