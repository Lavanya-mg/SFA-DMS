from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SfaExpenseType(models.Model):
    _name = 'sfa.expense.type'
    _description = 'Expense Type'
    _order = 'sequence, name'
    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Expense Type Code must be unique.'),
    ]

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    # Classifies the type so the eligibility-rule form can show the right extra
    # fields (travel modes for Travelling Allowance, tier limits for Lodging, …).
    nature = fields.Selection([
        ('daily', 'Daily Allowance'),
        ('travelling', 'Travelling Allowance'),
        ('lodging', 'Lodging'),
        ('fuel', 'Fuel'),
        ('mobile', 'Mobile'),
        ('misc', 'Food / Toll / Stationery / Misc'),
    ], string='Nature',
       help="Drives which extra fields appear on the eligibility rule.")
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

    @api.constrains('name', 'code')
    def _check_unique_name_code(self):
        """No duplicate active expense types (by name or code)."""
        for rec in self:
            if rec.name and self.search_count(
                    [('name', '=ilike', rec.name), ('id', '!=', rec.id)]):
                raise ValidationError(_("An expense type named '%s' already exists.") % rec.name)
            if rec.code and self.search_count(
                    [('code', '=', rec.code), ('id', '!=', rec.id)]):
                raise ValidationError(_("An expense type with code '%s' already exists.") % rec.code)

    @api.model
    def _seed_sync_types(self):
        """Ensure the standard 10 SFA expense types exist with the correct nature,
        and remove the legacy demo types. Idempotent (upsert by name) — safe to
        re-run on every module update, and never duplicates or clashes on code."""
        desired = [
            ('Daily Allowance', 'DA', 'daily', 'per_day'),
            ('Travelling Allowance', 'TA', 'travelling', 'per_km'),
            ('Fuel', 'FUEL', 'fuel', 'actual'),
            ('Lodging', 'LODGING', 'lodging', 'per_day'),
            ('Food', 'FOOD', 'misc', 'actual'),
            ('Toll', 'TOLL', 'misc', 'actual'),
            ('Mobile', 'MOBILE', 'mobile', 'flat_monthly'),
            ('Stationery', 'STATIONERY', 'misc', 'actual'),
            ('Printing', 'PRINTING', 'misc', 'actual'),
            ('Miscellaneous', 'MISC', 'misc', 'actual'),
        ]
        keep_names = [d[0] for d in desired]

        # 0) De-duplicate active types by name (archive the extras). Archiving
        #    doesn't write name/code, so it won't trip the uniqueness constraint.
        by_name = {}
        for t in self.search([], order='id'):
            key = (t.name or '').strip().lower()
            if key in by_name:
                t.active = False
            else:
                by_name[key] = t

        # 1) Remove the legacy demo types FIRST — this frees their codes (e.g.
        #    "Travel & Accommodation" holds TA, "Meals" holds FOOD) so the desired
        #    types below can be created with those codes. Archive if a rule still
        #    references one (can't be deleted).
        legacy = self.with_context(active_test=False).search([
            ('name', 'in', ['Travel & Accommodation', 'Mileage', 'Meals',
                            'Communication', 'Gifts', 'Expenses']),
            ('name', 'not in', keep_names),
        ])
        for t in legacy:
            try:
                t.unlink()
            except Exception:
                t.active = False

        # 2) Upsert the 10 desired types by name.
        seq = 10
        for name, code, nature, rate_type in desired:
            rec = self.with_context(active_test=False).search([('name', '=', name)], limit=1)
            if rec:
                vals = {'nature': nature, 'active': True}
                if not rec.rate_type or rec.rate_type == 'actual':
                    vals['rate_type'] = rate_type
                rec.write(vals)
            else:
                # Ensure a free code (an archived legacy record may still hold it).
                free_code, n = code, 1
                while self.with_context(active_test=False).search([('code', '=', free_code)], limit=1):
                    n += 1
                    free_code = '%s%d' % (code, n)
                self.create({'name': name, 'code': free_code, 'nature': nature,
                             'rate_type': rate_type, 'sequence': seq})
            seq += 10
        return True

    def _effective_nature(self):
        """Return the explicit nature, or infer one from the type name so the
        eligibility-rule form works even before Nature is configured."""
        self.ensure_one()
        if self.nature:
            return self.nature
        n = (self.name or '').lower()
        if any(k in n for k in ('travel', 'mileage', 'conveyance')):
            return 'travelling'
        if any(k in n for k in ('lodg', 'hotel', 'accommod', 'stay')):
            return 'lodging'
        if 'daily' in n:
            return 'daily'
        if any(k in n for k in ('fuel', 'petrol', 'diesel')):
            return 'fuel'
        if any(k in n for k in ('mobile', 'phone', 'communic', 'telecom')):
            return 'mobile'
        return 'misc'
