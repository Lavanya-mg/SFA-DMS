# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SfaTargetAllocation(models.Model):
    """One target/achievement row per (period, employee, criteria).

    'Individual' values are the employee's own; 'Team' values are aggregated
    from the employee's direct subordinates for the same period + criteria.
    """
    _name = 'sfa.target.allocation'
    _description = 'Target Allocation'
    _order = 'period_id, employee_id, criteria_id'
    _sql_constraints = [
        ('uniq_alloc', 'UNIQUE(period_id, employee_id, criteria_id)',
         'A target already exists for this period, employee and criteria.'),
    ]

    period_id = fields.Many2one('kpi.target.period', string='Period', required=True,
                                ondelete='cascade', index=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True,
                                  ondelete='cascade', index=True)
    criteria_id = fields.Many2one('sfa.target.criteria', string='Criteria', required=True,
                                  ondelete='cascade', index=True)

    target_individual = fields.Float('Individual Target', digits=(16, 2))
    achievement_individual = fields.Float('Individual Achievement', digits=(16, 2))
    last_sync = fields.Datetime('Last Synced')

    target_team = fields.Float('Team Target', compute='_compute_team', digits=(16, 2))
    achievement_team = fields.Float('Team Achievement', compute='_compute_team', digits=(16, 2))
    target_total = fields.Float('Total Target', compute='_compute_totals', digits=(16, 2))
    achievement_total = fields.Float('Total Achievement', compute='_compute_totals', digits=(16, 2))
    achievement_pct = fields.Float('Achievement %', compute='_compute_totals', digits=(16, 2))

    @api.model
    def _direct_subordinates(self, employee):
        """Employees who report to `employee` (their parent_id points to it).
        Never includes the employee itself, even with corrupt self-referencing
        hierarchy data."""
        if not employee:
            return self.env['hr.employee']
        return self.env['hr.employee'].search([
            ('parent_id', '=', employee.id),
            ('id', '!=', employee.id),
        ])

    def _compute_team(self):
        for rec in self:
            subs = self._direct_subordinates(rec.employee_id)
            if subs and rec.period_id and rec.criteria_id:
                lines = self.search([
                    ('period_id', '=', rec.period_id.id),
                    ('criteria_id', '=', rec.criteria_id.id),
                    ('employee_id', 'in', subs.ids),
                ])
                rec.target_team = sum(lines.mapped('target_individual'))
                rec.achievement_team = sum(lines.mapped('achievement_individual'))
            else:
                rec.target_team = 0.0
                rec.achievement_team = 0.0

    @api.depends('target_individual', 'achievement_individual', 'target_team', 'achievement_team')
    def _compute_totals(self):
        for rec in self:
            rec.target_total = rec.target_individual + rec.target_team
            rec.achievement_total = rec.achievement_individual + rec.achievement_team
            rec.achievement_pct = (rec.achievement_total / rec.target_total * 100.0) \
                if rec.target_total else 0.0

    # ── Internals ─────────────────────────────────────────────────────────────
    def _get_or_create(self, period_id, employee_id, criteria_id):
        alloc = self.search([
            ('period_id', '=', period_id),
            ('employee_id', '=', employee_id),
            ('criteria_id', '=', criteria_id),
        ], limit=1)
        if not alloc:
            alloc = self.create({
                'period_id': period_id, 'employee_id': employee_id, 'criteria_id': criteria_id,
            })
        return alloc

    # ══════════════════════════════════════════════════════════════════════════
    #  RPC API for the Target Allocation OWL client action
    # ══════════════════════════════════════════════════════════════════════════
    @api.model
    def get_options(self):
        periods = self.env['kpi.target.period'].search([('active', '=', True)], order='date_from desc')
        employees = self.env['hr.employee'].search([], order='name')
        current = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        return {
            'periods': [{'id': p.id, 'name': p.name} for p in periods],
            'employees': [{'id': e.id, 'name': e.name} for e in employees],
            'default_period_id': periods[:1].id or False,
            'default_employee_id': (current.id if current else (employees[:1].id or False)),
        }

    @api.model
    def get_allocation_data(self, period_id, employee_id):
        if not period_id or not employee_id:
            return {'rows': [], 'has_subordinates': False, 'last_sync': False}
        period = self.env['kpi.target.period'].browse(int(period_id))
        employee = self.env['hr.employee'].browse(int(employee_id))
        criteria = self.env['sfa.target.criteria'].search([('active', '=', True)], order='sequence, name')
        subs = self._direct_subordinates(employee)
        emp_ids = [employee.id] + subs.ids

        allocs = self.search([
            ('period_id', '=', period.id),
            ('employee_id', 'in', emp_ids),
        ])
        amap = {(a.employee_id.id, a.criteria_id.id): a for a in allocs}
        last_sync = max(allocs.mapped('last_sync') or [False]) if allocs else False

        rows = []
        for c in criteria:
            own = amap.get((employee.id, c.id))
            ind_target = own.target_individual if own else 0.0
            ind_ach = own.achievement_individual if own else 0.0
            team_target = sum(
                (amap[(s, c.id)].target_individual if (s, c.id) in amap else 0.0) for s in subs.ids)
            team_ach = sum(
                (amap[(s, c.id)].achievement_individual if (s, c.id) in amap else 0.0) for s in subs.ids)
            tot_target = ind_target + team_target
            tot_ach = ind_ach + team_ach
            pct = (tot_ach / tot_target * 100.0) if tot_target else 0.0
            rows.append({
                'criteria_id': c.id,
                'criteria': c.name,
                'target_individual': ind_target,
                'target_team': team_target,
                'target_total': tot_target,
                'achievement_individual': ind_ach,
                'achievement_team': team_ach,
                'achievement_total': tot_ach,
                'achievement_pct': round(pct, 1),
            })
        return {
            'rows': rows,
            'has_subordinates': bool(subs),
            'last_sync': str(last_sync) if last_sync else False,
        }

    @api.model
    def save_targets(self, period_id, employee_id, targets):
        """targets = { criteria_id: value } — the employee's own (individual) targets."""
        if not period_id or not employee_id:
            raise UserError(_("Period and User are required."))
        for crit_id, val in (targets or {}).items():
            alloc = self._get_or_create(int(period_id), int(employee_id), int(crit_id))
            alloc.target_individual = float(val or 0)
        return True

    @api.model
    def get_distribute_data(self, period_id, employee_id):
        if not period_id or not employee_id:
            return {'criteria': [], 'executives': [], 'manager_targets': {}}
        employee = self.env['hr.employee'].browse(int(employee_id))
        # Only direct subordinates (parent_id = selected user) may receive a
        # distribution — never the selected user themself.
        subs = self._direct_subordinates(employee)
        criteria = self.env['sfa.target.criteria'].search([('active', '=', True)], order='sequence, name')

        sub_allocs = self.search([
            ('period_id', '=', int(period_id)), ('employee_id', 'in', subs.ids)]) if subs else self.browse()
        amap = {(a.employee_id.id, a.criteria_id.id): a.target_individual for a in sub_allocs}
        mgr_allocs = self.search([
            ('period_id', '=', int(period_id)), ('employee_id', '=', employee.id)])
        mgr_map = {a.criteria_id.id: a.target_individual for a in mgr_allocs}

        return {
            'criteria': [{'id': c.id, 'name': c.name} for c in criteria],
            'executives': [{
                'id': s.id, 'name': s.name,
                'values': {c.id: amap.get((s.id, c.id), 0.0) for c in criteria},
            } for s in subs],
            'manager_targets': {c.id: mgr_map.get(c.id, 0.0) for c in criteria},
        }

    @api.model
    def save_distribution(self, period_id, manager_id, distribution):
        """distribution = { employee_id: { criteria_id: value } }.
        Per criteria, the distributed total must not exceed the manager's own target."""
        if not period_id or not manager_id:
            raise UserError(_("Period and manager are required."))
        manager = self.env['hr.employee'].browse(int(manager_id))
        mgr_allocs = self.search([
            ('period_id', '=', int(period_id)), ('employee_id', '=', manager.id)])
        mgr_map = {a.criteria_id.id: a.target_individual for a in mgr_allocs}

        # Validate distributed sums against the manager's own targets.
        sums = {}
        for _emp_id, crit_vals in (distribution or {}).items():
            for crit_id, val in crit_vals.items():
                sums[int(crit_id)] = sums.get(int(crit_id), 0.0) + float(val or 0)
        for crit_id, total in sums.items():
            cap = mgr_map.get(crit_id, 0.0)
            if cap and total > cap:
                crit = self.env['sfa.target.criteria'].browse(crit_id)
                raise UserError(_(
                    "Distributed total for '%(name)s' is %(total)s, which exceeds your "
                    "own target of %(cap)s.",
                    name=crit.name, total=total, cap=cap))

        for emp_id, crit_vals in (distribution or {}).items():
            for crit_id, val in crit_vals.items():
                alloc = self._get_or_create(int(period_id), int(emp_id), int(crit_id))
                alloc.target_individual = float(val or 0)
        return True

    @api.model
    def sync_achievements(self, period_id, employee_id):
        """Run each active criterion's query for the employee (and subordinates,
        so team achievement populates) and store the result as achievement."""
        if not period_id or not employee_id:
            raise UserError(_("Period and User are required."))
        period = self.env['kpi.target.period'].browse(int(period_id))
        if not period.exists() or not period.date_from or not period.date_to:
            raise UserError(_("The selected period has no start/end date."))
        employee = self.env['hr.employee'].browse(int(employee_id))
        employees = employee + self._direct_subordinates(employee)
        criteria = self.env['sfa.target.criteria'].search([('active', '=', True)])
        now = fields.Datetime.now()
        for emp in employees:
            for c in criteria:
                value = c.compute_value_for(emp, period.date_from, period.date_to)
                alloc = self._get_or_create(period.id, emp.id, c.id)
                alloc.achievement_individual = value
                alloc.last_sync = now
        return True

    # ══════════════════════════════════════════════════════════════════════════
    #  KPI Dashboard payload (My / Team / Organization views)
    # ══════════════════════════════════════════════════════════════════════════
    def _scope_employees(self, view, employee):
        Emp = self.env['hr.employee']
        if view == 'org':
            return Emp.search([])
        if view == 'team':
            team = employee
            frontier = employee
            for _i in range(20):  # bounded descent to avoid loops
                frontier = Emp.search([('parent_id', 'in', frontier.ids),
                                       ('id', 'not in', team.ids)])
                if not frontier:
                    break
                team |= frontier
            return team
        return employee | self._direct_subordinates(employee)  # 'my' = self + direct reports

    def _aggregate(self, period, employees):
        """Sum target/achievement per criteria over a set of employees for a period."""
        per_crit = {}
        if not period or not employees:
            return per_crit
        allocs = self.search([
            ('period_id', '=', period.id), ('employee_id', 'in', employees.ids)])
        for a in allocs:
            d = per_crit.setdefault(a.criteria_id.id, {'target': 0.0, 'actual': 0.0})
            d['target'] += a.target_individual
            d['actual'] += a.achievement_individual
        return per_crit

    @api.model
    def get_kpi_dashboard(self, view, period_id, employee_id, compare_period_id=None):
        view = view or 'my'
        if not period_id or not employee_id:
            return {}
        period = self.env['kpi.target.period'].browse(int(period_id))
        employee = self.env['hr.employee'].browse(int(employee_id))
        employees = self._scope_employees(view, employee)
        criteria = self.env['sfa.target.criteria'].search([('active', '=', True)], order='sequence, name')

        agg = self._aggregate(period, employees)

        def pct(actual, target):
            return round(actual / target * 100.0, 1) if target else 0.0

        breakdown = []
        total_target = total_actual = 0.0
        for c in criteria:
            d = agg.get(c.id, {'target': 0.0, 'actual': 0.0})
            total_target += d['target']
            total_actual += d['actual']
            breakdown.append({
                'criteria_id': c.id, 'name': c.name,
                'target': d['target'], 'actual': d['actual'], 'pct': pct(d['actual'], d['target']),
            })

        # Incentive earned (best-effort, from sfa.incentive.record for this month/scope)
        incentive = 0.0
        try:
            if period.date_from:
                recs = self.env['sfa.incentive.record'].search([
                    ('employee_id', 'in', employees.ids),
                    ('period_month', '=', period.date_from.month),
                    ('period_year', '=', period.date_from.year),
                ])
                incentive = sum(recs.mapped('final_amount'))
        except Exception:
            incentive = 0.0

        # Per-employee ranking (top performers + team table)
        people = []
        for emp in employees:
            ea = self._aggregate(period, emp)
            et = sum(v['target'] for v in ea.values())
            eaa = sum(v['actual'] for v in ea.values())
            if et == 0 and eaa == 0:
                continue
            people.append({
                'name': emp.name,
                'profile': emp.job_id.name if emp.job_id else (emp.department_id.name if emp.department_id else ''),
                'target': et, 'actual': eaa, 'pct': pct(eaa, et), 'incentive': 0.0,
            })
        people.sort(key=lambda p: p['pct'], reverse=True)

        # Performance trend across the last monthly periods up to this one
        trend = []
        if period.date_from:
            months = self.env['kpi.target.period'].search([
                ('period_type', '=', 'monthly'), ('date_from', '<=', period.date_from),
            ], order='date_from asc')[-6:]
            for mp in months:
                magg = self._aggregate(mp, employees)
                trend.append({
                    'label': mp.name,
                    'target': sum(v['target'] for v in magg.values()),
                    'achievement': sum(v['actual'] for v in magg.values()),
                })

        # Optional comparison period totals
        compare = None
        if compare_period_id:
            cp = self.env['kpi.target.period'].browse(int(compare_period_id))
            cagg = self._aggregate(cp, employees)
            compare = {
                'name': cp.name,
                'total_target': sum(v['target'] for v in cagg.values()),
                'total_actual': sum(v['actual'] for v in cagg.values()),
            }

        return {
            'summary': {
                'overall_pct': pct(total_actual, total_target),
                'total_target': total_target,
                'total_actual': total_actual,
                'incentive': incentive,
                'compare': compare,
            },
            'criteria': [{'id': c.id, 'name': c.name} for c in criteria],
            'breakdown': breakdown,
            'top_performers': people[:10],
            'team_performance': people,
            'trend': trend,
            'by_criteria': [{'name': b['name'], 'pct': b['pct']} for b in breakdown],
        }
