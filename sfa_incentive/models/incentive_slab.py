# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SfaIncentiveSlab(models.Model):
    _name = 'sfa.incentive.slab'
    _description = 'Incentive Slab'
    _order = 'sort_order, id'
    _sql_constraints = [
        ('check_achievement', 'CHECK(min_achievement <= max_achievement)',
         'Min Achievement % must be less than or equal to Max Achievement %.'),
    ]

    name = fields.Char('Slab Name', required=True)
    criteria_id = fields.Many2one('sfa.target.criteria', 'Target Criteria',
                                   help='Leave empty for Universal (applies to all criteria)')
    profile_id = fields.Many2one('sfa.incentive.profile', 'Profile',
                                  help='Leave empty for Universal (applies to all profiles)')
    territory_id = fields.Many2one('fmcg.territory', 'Territory',
                                    help='Leave empty for Universal (applies to all territories)')

    min_achievement = fields.Float('Min Achievement %', default=0.0, digits=(16, 2))
    max_achievement = fields.Float('Max Achievement %', default=100.0, digits=(16, 2))

    payout_type = fields.Selection([
        ('percentage', 'Percentage of Target Value'),
        ('fixed', 'Fixed Amount'),
        ('salary_pct', 'Salary % of Gross Salary'),
    ], string='Payout Type', required=True, default='percentage')
    payout_value = fields.Float('Payout Value', default=0.0, digits=(16, 2))
    multiplier = fields.Float('Multiplier', default=1.0, digits=(16, 4))

    sort_order = fields.Integer('Sort Order', default=0)
    date_from = fields.Date('Effective From')
    date_to = fields.Date('Effective To')
    description = fields.Text('Description')
    active = fields.Boolean(default=True)

    # Computed display fields
    range_display = fields.Char('Range', compute='_compute_range_display')
    payout_display = fields.Char('Payout', compute='_compute_payout_display')

    @api.depends('min_achievement', 'max_achievement')
    def _compute_range_display(self):
        for rec in self:
            rec.range_display = '%.0f%% – %.0f%%' % (rec.min_achievement, rec.max_achievement)

    @api.depends('payout_type', 'payout_value')
    def _compute_payout_display(self):
        for rec in self:
            v = rec.payout_value
            if rec.payout_type == 'fixed':
                rec.payout_display = 'Fixed %g' % v
            elif rec.payout_type == 'percentage':
                rec.payout_display = '%g%% of target' % v
            elif rec.payout_type == 'salary_pct':
                rec.payout_display = '%g%% of salary' % v
            else:
                rec.payout_display = str(v)

    def action_toggle_active(self):
        for rec in self:
            rec.active = not rec.active
