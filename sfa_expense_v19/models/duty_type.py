# -*- coding: utf-8 -*-
from odoo import models, fields


class SfaDutyType(models.Model):
    _name = 'sfa.duty.type'
    _description = 'Duty Type Master'
    _order = 'sequence, code'
    _sql_constraints = [('unique_code', 'UNIQUE(code)', 'Duty Type Code must be unique.')]

    name = fields.Char(required=True, help='e.g. Headquarters, Ex-HQ, Outstation')
    code = fields.Char(required=True, help='e.g. HQ, EX-HQ, OS')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
