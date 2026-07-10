# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class KpiManagerTarget(models.Model):
    _name = 'kpi.manager.target'
    _description = 'KPI Team Target'
    _order = 'period_id desc, manager_id'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _sql_constraints = [
        ('unique_manager_period', 'UNIQUE(manager_id, period_id)',
         'A manager can have only one team target per period!')
    ]

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    manager_id = fields.Many2one(
        'hr.employee', string='Manager / Executive', required=True, index=True, tracking=True)
    department_id = fields.Many2one(
        'hr.department', related='manager_id.department_id', store=True, string='Department')
    period_id = fields.Many2one(
        'kpi.target.period', string='Period', required=True, index=True)
    period_type = fields.Selection(
        related='period_id.period_type', string='Period Type', store=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
    ], string='Status', default='draft', tracking=True)

    assignment_mode = fields.Selection([
        ('distribute', 'Distribute Total Among Members'),
        ('individual', 'Assign Individually Per Member'),
    ], string='Assignment Mode', default='distribute', required=True)

    total_target_orders = fields.Float(string='Total Orders Target', default=0.0)
    total_target_visits = fields.Float(string='Total Visits Target', default=0.0)
    total_target_new_dealers = fields.Float(string='Total New Dealers Target', default=0.0)
    total_target_payment_collected = fields.Float(string='Total Payment Target', default=0.0)
    total_target_complaints_solved = fields.Float(string='Total Complaints Target', default=0.0)

    member_target_ids = fields.One2many('kpi.target', 'manager_target_id', string='Member Targets')
    member_count = fields.Integer(string='Team Members', compute='_compute_member_count', store=True)

    team_allocated_orders = fields.Float(
        string='Allocated Orders', compute='_compute_team_totals', store=True)
    team_allocated_visits = fields.Float(
        string='Allocated Visits', compute='_compute_team_totals', store=True)
    team_allocated_new_dealers = fields.Float(
        string='Allocated New Dealers', compute='_compute_team_totals', store=True)
    team_allocated_payment_collected = fields.Float(
        string='Allocated Payment', compute='_compute_team_totals', store=True)
    team_allocated_complaints_solved = fields.Float(
        string='Allocated Complaints', compute='_compute_team_totals', store=True)

    team_actual_orders = fields.Float(
        string='Team Actual Orders', compute='_compute_team_actuals', store=True)
    team_actual_visits = fields.Float(
        string='Team Actual Visits', compute='_compute_team_actuals', store=True)
    team_actual_new_dealers = fields.Float(
        string='Team Actual New Dealers', compute='_compute_team_actuals', store=True)
    team_actual_payment_collected = fields.Float(
        string='Team Actual Payment', compute='_compute_team_actuals', store=True)
    team_actual_complaints_solved = fields.Float(
        string='Team Actual Complaints', compute='_compute_team_actuals', store=True)

    team_achievement_orders = fields.Float(
        string='Orders Achievement %', compute='_compute_team_achievement', store=True)
    team_achievement_visits = fields.Float(
        string='Visits Achievement %', compute='_compute_team_achievement', store=True)
    team_achievement_new_dealers = fields.Float(
        string='New Dealers Achievement %', compute='_compute_team_achievement', store=True)
    team_achievement_payment_collected = fields.Float(
        string='Payment Achievement %', compute='_compute_team_achievement', store=True)
    team_achievement_complaints_solved = fields.Float(
        string='Complaints Achievement %', compute='_compute_team_achievement', store=True)
    team_overall_achievement = fields.Float(
        string='Overall Team Achievement %', compute='_compute_team_achievement', store=True)

    unallocated_orders = fields.Float(
        string='Unallocated Orders', compute='_compute_unallocated', store=True)
    unallocated_visits = fields.Float(
        string='Unallocated Visits', compute='_compute_unallocated', store=True)
    unallocated_new_dealers = fields.Float(
        string='Unallocated New Dealers', compute='_compute_unallocated', store=True)
    unallocated_payment_collected = fields.Float(
        string='Unallocated Payment', compute='_compute_unallocated', store=True)
    unallocated_complaints_solved = fields.Float(
        string='Unallocated Complaints', compute='_compute_unallocated', store=True)
    is_fully_allocated = fields.Boolean(
        string='Fully Allocated', compute='_compute_unallocated', store=True)
    notes = fields.Text(string='Notes')

    @api.depends('manager_id', 'period_id')
    def _compute_name(self):
        for rec in self:
            parts = [rec.manager_id.name or '', rec.period_id.name or '']
            rec.name = ' / '.join(p for p in parts if p) or 'New Team Target'

    @api.depends('member_target_ids')
    def _compute_member_count(self):
        for rec in self:
            rec.member_count = len(rec.member_target_ids)

    @api.depends(
        'member_target_ids.target_orders', 'member_target_ids.target_visits',
        'member_target_ids.target_new_dealers',
        'member_target_ids.target_payment_collected',
        'member_target_ids.target_complaints_solved',
    )
    def _compute_team_totals(self):
        for rec in self:
            m = rec.member_target_ids
            rec.team_allocated_orders = sum(m.mapped('target_orders'))
            rec.team_allocated_visits = sum(m.mapped('target_visits'))
            rec.team_allocated_new_dealers = sum(m.mapped('target_new_dealers'))
            rec.team_allocated_payment_collected = sum(m.mapped('target_payment_collected'))
            rec.team_allocated_complaints_solved = sum(m.mapped('target_complaints_solved'))

    @api.depends(
        'member_target_ids.actual_orders', 'member_target_ids.actual_visits',
        'member_target_ids.actual_new_dealers',
        'member_target_ids.actual_payment_collected',
        'member_target_ids.actual_complaints_solved',
    )
    def _compute_team_actuals(self):
        for rec in self:
            m = rec.member_target_ids
            rec.team_actual_orders = sum(m.mapped('actual_orders'))
            rec.team_actual_visits = sum(m.mapped('actual_visits'))
            rec.team_actual_new_dealers = sum(m.mapped('actual_new_dealers'))
            rec.team_actual_payment_collected = sum(m.mapped('actual_payment_collected'))
            rec.team_actual_complaints_solved = sum(m.mapped('actual_complaints_solved'))

    @api.depends(
        'assignment_mode',
        'total_target_orders', 'total_target_visits', 'total_target_new_dealers',
        'total_target_payment_collected', 'total_target_complaints_solved',
        'team_allocated_orders', 'team_allocated_visits', 'team_allocated_new_dealers',
        'team_allocated_payment_collected', 'team_allocated_complaints_solved',
        'team_actual_orders', 'team_actual_visits', 'team_actual_new_dealers',
        'team_actual_payment_collected', 'team_actual_complaints_solved',
    )
    def _compute_team_achievement(self):
        def pct(a, b):
            return round(a / b * 100, 2) if b else 0.0

        for rec in self:
            if rec.assignment_mode == 'distribute':
                bases = (
                    rec.total_target_orders, rec.total_target_visits,
                    rec.total_target_new_dealers, rec.total_target_payment_collected,
                    rec.total_target_complaints_solved,
                )
            else:
                bases = (
                    rec.team_allocated_orders, rec.team_allocated_visits,
                    rec.team_allocated_new_dealers, rec.team_allocated_payment_collected,
                    rec.team_allocated_complaints_solved,
                )
            actuals = (
                rec.team_actual_orders, rec.team_actual_visits,
                rec.team_actual_new_dealers, rec.team_actual_payment_collected,
                rec.team_actual_complaints_solved,
            )
            rec.team_achievement_orders = pct(actuals[0], bases[0])
            rec.team_achievement_visits = pct(actuals[1], bases[1])
            rec.team_achievement_new_dealers = pct(actuals[2], bases[2])
            rec.team_achievement_payment_collected = pct(actuals[3], bases[3])
            rec.team_achievement_complaints_solved = pct(actuals[4], bases[4])

            achieved = [pct(a, b) for a, b in zip(actuals, bases) if b > 0]
            rec.team_overall_achievement = round(
                sum(achieved) / len(achieved), 2) if achieved else 0.0

    @api.depends(
        'assignment_mode',
        'total_target_orders', 'total_target_visits', 'total_target_new_dealers',
        'total_target_payment_collected', 'total_target_complaints_solved',
        'team_allocated_orders', 'team_allocated_visits', 'team_allocated_new_dealers',
        'team_allocated_payment_collected', 'team_allocated_complaints_solved',
    )
    def _compute_unallocated(self):
        for rec in self:
            if rec.assignment_mode == 'distribute':
                rec.unallocated_orders = rec.total_target_orders - rec.team_allocated_orders
                rec.unallocated_visits = rec.total_target_visits - rec.team_allocated_visits
                rec.unallocated_new_dealers = (
                    rec.total_target_new_dealers - rec.team_allocated_new_dealers)
                rec.unallocated_payment_collected = (
                    rec.total_target_payment_collected - rec.team_allocated_payment_collected)
                rec.unallocated_complaints_solved = (
                    rec.total_target_complaints_solved - rec.team_allocated_complaints_solved)
                rec.is_fully_allocated = all([
                    abs(rec.unallocated_orders) < 0.01 if rec.total_target_orders else True,
                    abs(rec.unallocated_visits) < 0.01 if rec.total_target_visits else True,
                    abs(rec.unallocated_new_dealers) < 0.01 if rec.total_target_new_dealers else True,
                    abs(rec.unallocated_payment_collected) < 0.01
                    if rec.total_target_payment_collected else True,
                    abs(rec.unallocated_complaints_solved) < 0.01
                    if rec.total_target_complaints_solved else True,
                ])
            else:
                rec.unallocated_orders = 0.0
                rec.unallocated_visits = 0.0
                rec.unallocated_new_dealers = 0.0
                rec.unallocated_payment_collected = 0.0
                rec.unallocated_complaints_solved = 0.0
                rec.is_fully_allocated = True

    def action_confirm(self):
        self.write({'state': 'confirmed'})
        self.member_target_ids.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})
        self.member_target_ids.write({'state': 'done'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})
        self.member_target_ids.write({'state': 'draft'})

    def action_distribute_equally(self):
        """Divide total targets equally among existing team members."""
        self.ensure_one()
        if self.assignment_mode != 'distribute':
            raise UserError('Equal distribution is only available in Distribute mode.')
        members = self.member_target_ids
        if not members:
            raise UserError('Add at least one team member before distributing.')
        count = len(members)
        vals = {
            'target_orders': round(self.total_target_orders / count, 2),
            'target_visits': round(self.total_target_visits / count, 2),
            'target_new_dealers': round(self.total_target_new_dealers / count, 2),
            'target_payment_collected': round(self.total_target_payment_collected / count, 2),
            'target_complaints_solved': round(self.total_target_complaints_solved / count, 2),
        }
        members.write(vals)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Distribution Complete',
                'message': f'Targets distributed equally among {count} member(s).',
                'sticky': False,
                'type': 'success',
            },
        }

    def action_add_member_target(self):
        self.ensure_one()
        return {
            'name': 'Add Member Target',
            'type': 'ir.actions.act_window',
            'res_model': 'kpi.target',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_manager_target_id': self.id,
                'default_period_id': self.period_id.id,
                'default_state': 'draft',
            },
        }

    def action_view_member_targets(self):
        self.ensure_one()
        return {
            'name': f'Team Members – {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'kpi.target',
            'view_mode': 'list,form',
            'domain': [('manager_target_id', '=', self.id)],
            'context': {
                'default_manager_target_id': self.id,
                'default_period_id': self.period_id.id,
            },
        }
