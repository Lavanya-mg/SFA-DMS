# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from dateutil.relativedelta import relativedelta


class KpiTargetPeriod(models.Model):
    _name = 'kpi.target.period'
    _description = 'KPI Target Period'
    _order = 'date_from desc'

    name = fields.Char(string='Period Name', required=True)
    period_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
    ], string='Period Type', required=True, default='monthly')
    date_from = fields.Date(string='Start Date', required=True)
    date_to = fields.Date(string='End Date', required=True)
    active = fields.Boolean(string='Active', default=True)

    is_default = fields.Boolean(
        string='Is Default',
        help="The default period pre-selected on target screens. Only one period can be the default.")
    cumulative_calculation = fields.Boolean(
        string='Cumulative Calculation',
        help="If checked, the incentive calculation for this period aggregates achievements from all "
             "child periods (linked via Parent Period). Example: a Quarterly period with cumulative "
             "enabled sums achievements from its 3 monthly child periods. Useful for FMCG quarterly "
             "PBIS where Q2 = Q1+Q2 cumulative.")
    parent_period_id = fields.Many2one(
        'kpi.target.period', string='Parent Period', ondelete='set null',
        help="Links this period to a parent for cumulative calculations. Example: monthly periods "
             "(Apr, May, Jun) link to their parent Quarterly period (Q1); quarterly periods link to "
             "their parent Annual period. Leave blank for standalone periods.")
    child_period_ids = fields.One2many('kpi.target.period', 'parent_period_id', string='Child Periods')

    target_ids = fields.One2many('kpi.target', 'period_id', string='Individual Targets', copy=False)
    manager_target_ids = fields.One2many('kpi.manager.target', 'period_id', string='Team Targets', copy=False)

    target_count = fields.Integer(string='Individual Targets', compute='_compute_counts', store=True)
    team_target_count = fields.Integer(string='Team Targets', compute='_compute_counts', store=True)

    @api.depends('target_ids', 'manager_target_ids')
    def _compute_counts(self):
        for record in self:
            record.target_count = len(record.target_ids)
            record.team_target_count = len(record.manager_target_ids)

    @api.constrains('parent_period_id')
    def _check_parent_period(self):
        for rec in self:
            parent = rec.parent_period_id
            seen = rec
            while parent:
                if parent in seen:
                    raise ValidationError(_("A period cannot be its own ancestor (cyclic Parent Period)."))
                seen |= parent
                parent = parent.parent_period_id

    def _clear_other_defaults(self):
        """Ensure at most one default period."""
        defaults = self.filtered('is_default')
        if defaults:
            others = self.search([('is_default', '=', True), ('id', 'not in', defaults.ids)])
            if others:
                others.write({'is_default': False})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._clear_other_defaults()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_default'):
            self._clear_other_defaults()
        return res

    def copy(self, default=None):
        default = dict(default or {})
        default.setdefault('name', _("%s (copy)", self.name))
        default.setdefault('is_default', False)
        return super().copy(default)

    def action_clone(self):
        """Clone this period and open the copy."""
        self.ensure_one()
        new_period = self.copy()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Cloned Period'),
            'res_model': 'kpi.target.period',
            'res_id': new_period.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.onchange('period_type', 'date_from')
    def _onchange_auto_fill(self):
        """Auto-generate period name and end date based on type and start date."""
        if self.period_type and self.date_from:
            if self.period_type == 'monthly':
                if not self.name:
                    self.name = self.date_from.strftime('%B %Y')
                self.date_to = self.date_from + relativedelta(months=1, days=-1)
            elif self.period_type == 'quarterly':
                if not self.name:
                    q = (self.date_from.month - 1) // 3 + 1
                    self.name = f'Q{q} {self.date_from.year}'
                self.date_to = self.date_from + relativedelta(months=3, days=-1)
            elif self.period_type == 'yearly':
                if not self.name:
                    self.name = str(self.date_from.year)
                self.date_to = self.date_from + relativedelta(years=1, days=-1)

    def action_view_targets(self):
        self.ensure_one()
        return {
            'name': f'Individual Targets – {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'kpi.target',
            'view_mode': 'list,form',
            'domain': [('period_id', '=', self.id)],
            'context': {'default_period_id': self.id},
        }

    def action_view_team_targets(self):
        self.ensure_one()
        return {
            'name': f'Team Targets – {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'kpi.manager.target',
            'view_mode': 'list,form',
            'domain': [('period_id', '=', self.id)],
            'context': {'default_period_id': self.id},
        }
