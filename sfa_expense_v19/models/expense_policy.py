# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SfaExpensePolicyRule(models.Model):
    """Eligibility rule: per band × expense-type × duty-type combination."""
    _name = 'sfa.expense.policy.rule'
    _description = 'Expense Policy Rule'
    _order = 'band_id, sequence, id'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ── Parent policy (for compatibility with employee_dashboard_v19) ──────────
    # policy_id = fields.Many2one('sfa.expense.policy', string='Policy', ondelete='cascade')

    # ── Rule identity ──────────────────────────────────────────────────────────
    band_id = fields.Many2one('sfa.expense.band', string='Band', required=True, ondelete='cascade')
    expense_type_id = fields.Many2one('sfa.expense.type', string='Expense Type', required=True, ondelete='cascade')
    duty_type_id = fields.Many2one('sfa.duty.type', string='Duty Type',
                                   help="Leave empty to apply to all duty types")
    category = fields.Char('Category', help="e.g. Travel, Accommodation, Food")

    # ── Rate configuration ─────────────────────────────────────────────────────
    rate_type = fields.Selection([
        ('actual', 'Actual'),
        ('per_day', 'Per Day'),
        ('per_km', 'Per KM'),
        ('flat_monthly', 'Flat Monthly'),
        ('per_hour', 'Per Hour'),
    ], required=True, default='actual')
    rate = fields.Float('Rate', digits=(16, 2))

    # ── City tier limits ───────────────────────────────────────────────────────
    tier1_limit = fields.Float('Tier 1 Limit', digits=(16, 2))
    tier2_limit = fields.Float('Tier 2 Limit', digits=(16, 2))
    tier3_limit = fields.Float('Tier 3 Limit', digits=(16, 2))

    # ── Receipt settings ───────────────────────────────────────────────────────
    receipt_required = fields.Boolean('Receipt Required', default=False)
    receipt_threshold = fields.Float('Receipt Threshold', digits=(16, 2),
                                     help="Receipt required only above this amount (0 = always)")
    remarks_required = fields.Boolean('Remarks Required', default=False)

    # ── Travel modes ───────────────────────────────────────────────────────────
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
