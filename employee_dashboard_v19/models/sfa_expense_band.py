from odoo import models, fields, api

class SfaExpenseBand(models.Model):
    _name = 'sfa.expense.band'
    _description = 'Expense Band Configuration'

    band_code = fields.Char(string="Band Code", required=True)
    band_name = fields.Char(string="Band Name", required=True)
    grade = fields.Char(string="Grade")
    designation = fields.Char(string="Designation")
    active = fields.Boolean(string="Active", default=True)

class SfaExpenseType(models.Model):
    _name = 'sfa.expense.type'
    _description = 'Expense Type Configuration'

    name = fields.Char(string="Name", required=True, help="e.g. Fuel, Daily Allowance")
    code = fields.Char(string="Code", required=True)
    rate_type = fields.Selection([
        ('actual', 'Actual'),
        ('per_day', 'Per Day'),
        ('per_km', 'Per KM'),
        ('flat_monthly', 'Flat Monthly'),
        ('per_hour', 'Per Hour')
    ], string="Rate Type", required=True, default='actual')
    receipt_required = fields.Boolean(string="Receipt Required", default=True)
    remarks_required = fields.Boolean(string="Remarks Required", default=False)
    active = fields.Boolean(string="Active", default=True)

class SfaCityTierLabel(models.Model):
    _name = 'sfa.city.tier.label'
    _description = 'Configurable City Tier Labels'

    name = fields.Char(string="Tier Label", required=True) # e.g., "Tier 1", "Metro"
    code = fields.Char(string="Code")

class SfaCityTier(models.Model):
    _name = 'sfa.city.tier'
    _description = 'City Tier Master'

    name = fields.Char(string="City Name", required=True)
    city_name = fields.Char('City Name', required=True)
    tier_id = fields.Many2one('sfa.city.tier.config', string='Tier', required=True, ondelete='restrict')
    state_id = fields.Many2one('res.country.state', string="State")
    tier_label_id = fields.Many2one('sfa.city.tier.label', string="Tier Category", required=True)
    active = fields.Boolean(string="Active", default=True)

class SfaTravelMode(models.Model):
    _name = 'sfa.travel.mode'
    _description = 'Travel Mode Configuration'

    name = fields.Char(string="Name", required=True, help="e.g. Own Car, Bike, Train-AC1")
    code = fields.Char(string="Code", required=True)
    active = fields.Boolean(string="Active", default=True)

class SfaExpensePolicy(models.Model):
    _name = 'sfa.expense.policy'
    _description = 'Expense Policy Configuration'

    name = fields.Char(string="Policy Name", required=True)
    company_id = fields.Many2one('res.company', string="Company", default=lambda self: self.env.company)
    date_from = fields.Date(string="Effective From", required=True)
    date_to = fields.Date(string="Effective To")
    active = fields.Boolean(string="Active", default=True)

    rule_ids = fields.One2many('sfa.expense.policy.rule', 'policy_id', string="Policy Rules")


class SfaExpensePolicyRule(models.Model):
    _name = 'sfa.expense.policy.rule'
    _description = 'Expense Policy Rule Lines'

    # Relationships
    policy_id = fields.Many2one('sfa.expense.policy', string="Policy Name", required=True, ondelete='cascade')
    band_id = fields.Many2one('sfa.expense.band', string="Band Name", required=True)
    expense_type_id = fields.Many2one('sfa.expense.type', string="Expense Type", required=True)
    city_tier_id = fields.Many2one('sfa.city.tier', string="City Tier") # Optional
    
    # Selection and Configuration
    duty_type = fields.Selection([
        ('all', 'ALL'),
        ('hq', 'HQ'),
        ('ex_hq', 'EX-HQ'),
        ('os', 'OS')
    ], string="Duty Type", required=True, default='all')
    
    rate_type = fields.Selection([
        ('actual', 'Actual'),
        ('per_day', 'Per Day'),
        ('per_km', 'Per KM'),
        ('flat_monthly', 'Flat Monthly')
    ], string="Rate Type", required=True)
    
    # Financials and Constraints
    rate = fields.Float(string="Rate")
    max_limit = fields.Float(string="Max Limit")
    modes_frequency = fields.Integer(string="Modes / Frequency")
    
    # Flags
    receipt_required = fields.Boolean(string="Receipt Required Override")
    mandatory_remarks = fields.Boolean(string="Mandatory Remarks")
    auto_create = fields.Boolean(string="Auto Create", help="Auto-add this line on expense creation", default=False)
    active = fields.Boolean(string="Active", default=True)
    
    duty_type_id = fields.Many2one('sfa.duty.type', string='Duty Type',
                                   help="Leave empty to apply to all duty types")
    category = fields.Char('Category', help="e.g. Travel, Accommodation, Food")

     # ── City tier limits ───────────────────────────────────────────────────────
    tier1_limit = fields.Float('Tier 1 Limit', digits=(16, 2))
    tier2_limit = fields.Float('Tier 2 Limit', digits=(16, 2))
    tier3_limit = fields.Float('Tier 3 Limit', digits=(16, 2))
    receipt_threshold = fields.Float('Receipt Threshold', digits=(16, 2),
                                     help="Receipt required only above this amount (0 = always)")
    remarks_required = fields.Boolean('Remarks Required', default=False)

    travel_mode_ids = fields.Many2many('sfa.travel.mode', string='Travel Modes')
    travel_mode_count = fields.Integer('# Modes', compute='_compute_travel_mode_count', store=True)

    # ── Policy dates ───────────────────────────────────────────────────────────
    date_from = fields.Date('Valid From')
    date_to = fields.Date('Valid To')

    @api.depends('travel_mode_ids')
    def _compute_travel_mode_count(self):
        for rec in self:
            rec.travel_mode_count = len(rec.travel_mode_ids)

    def name_get(self):
        result = []
        for r in self:
            band = r.band_id.code or ''
            etype = r.expense_type_id.name or ''
            duty = r.duty_type_id.name if r.duty_type_id else 'ALL'
            result.append((r.id, f"{band} / {etype} / {duty}"))
        return result

