# -*- coding: utf-8 -*-
from odoo import models, fields


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    band_id = fields.Many2one(
        'sfa.expense.band', string='Expense Band',
        help="Band that drives this employee's expense eligibility rules "
             "(auto-created lines, eligible amounts, allowed expense types).")
