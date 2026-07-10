# -*- coding: utf-8 -*-
from odoo import models, fields


class SfaTravelMode(models.Model):
    _name = 'sfa.travel.mode'
    _description = 'Travel Mode Master'
    _order = 'sequence, name'
    _sql_constraints = [('unique_code', 'UNIQUE(code)', 'Travel Mode Code must be unique.')]

    name = fields.Char(required=True, help='e.g. Own Car, Bike, Bus, Train-AC1, Air-Economy')
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
