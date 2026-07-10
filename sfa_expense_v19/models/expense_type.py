from odoo import models, fields


class SfaExpenseType(models.Model):
    _name = 'sfa.expense.type'
    _description = 'Expense Type'
    _order = 'sequence, name'
    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Expense Type Code must be unique.'),
    ]

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    product_id = fields.Many2one(
        'product.product', string='Expense Category',
        domain=[('can_be_expensed', '=', True)],
        help="Link to standard Odoo expense category product"
    )
    rate_type = fields.Selection([
        ('actual', 'Actual'),
        ('per_day', 'Per Day'),
        ('per_km', 'Per KM'),
        ('flat_monthly', 'Flat Monthly'),
        ('per_hour', 'Per Hour'),
    ], required=True, default='actual')
    receipt_required = fields.Boolean(default=False)
    remarks_required = fields.Boolean(default=False)
    system_km_enabled = fields.Boolean(
        'Enable System KM', default=False,
        help="Auto-compute distance from GPS/Maps for this expense type"
    )
    auto_create = fields.Boolean(
        'Auto-add on Expense', default=False,
        help="Automatically add this line when creating an expense sheet"
    )
    active = fields.Boolean(default=True)
    color = fields.Integer(default=0)
    sequence = fields.Integer(default=10)
