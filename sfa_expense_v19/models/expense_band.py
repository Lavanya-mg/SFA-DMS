from odoo import models, fields


class SfaExpenseBand(models.Model):
    _name = 'sfa.expense.band'
    _description = 'Expense Band'
    _order = 'sequence, code'
    _rec_name = 'code'
    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Band Code must be unique.'),
    ]

    name = fields.Char('Band Name', required=True)
    code = fields.Char('Band Code', required=True)
    grade = fields.Char('Grade')
    designation = fields.Char('Designation')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
