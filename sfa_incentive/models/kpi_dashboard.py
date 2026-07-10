# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class SfaKpiDashboard(models.Model):
    """Service model providing the aggregated data for the KPI Dashboard OWL component."""
    _name = 'sfa.kpi.dashboard'
    _description = 'KPI Dashboard'

    # ── Scope helpers ─────────────────────────────────────────────────────────
    def _employees_for_view(self, view):
        current = self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)
        if view == 'organization':
            return self.env['hr.employee'].search([])
        if view == 'team':
            return (current | current.child_ids) if current else self.env['hr.employee']
        return current  # 'my'

    def _totals_by_criteria(self, period, employees, criteria):
        """Return {criteria_id: {'target': x, 'actual': y}} over the employee set."""
        result = {c.id: {'target': 0.0, 'actual': 0.0} for c in criteria}
        if not period or not employees:
            return result
        allocs = self.env['sfa.target.allocation'].search([
            ('period_id', '=', period.id),
            ('employee_id', 'in', employees.ids),
        ])
        for a in allocs:
            if a.criteria_id.id in result:
                result[a.criteria_id.id]['target'] += a.target_individual
                result[a.criteria_id.id]['actual'] += a.achievement_individual
        return result

    def _incentive_for(self, period, employees):
        """Incentive earned (total + per-criteria) from sfa.incentive.record for the period."""
        earned, breakdown = 0.0, {}
        if 'sfa.incentive.record' not in self.env or not period or not employees:
            return earned, breakdown
        try:
            recs = self.env['sfa.incentive.record'].search([
                ('employee_id', 'in', employees.ids),
                ('period_month', '=', period.date_from.month),
                ('period_year', '=', period.date_from.year),
            ])
            for r in recs:
                earned += r.final_amount
                key = r.criteria_id.id or 0
                breakdown[key] = breakdown.get(key, 0.0) + r.final_amount
        except Exception as e:
            _logger.warning("KPI dashboard incentive fetch failed: %s", e)
        return earned, breakdown

    @staticmethod
    def _pct(actual, target):
        return round(actual / target * 100.0, 1) if target else 0.0

    # ── Main RPC ──────────────────────────────────────────────────────────────
    @api.model
    def get_dashboard(self, view='my', period_id=None, comparison_period_id=None):
        Period = self.env['kpi.target.period']
        periods = Period.search([('active', '=', True)], order='date_from desc')

        period = Period.browse(int(period_id)) if period_id else (
            periods.filtered('is_default')[:1] or periods[:1])
        comparison = Period.browse(int(comparison_period_id)) if comparison_period_id else Period

        employees = self._employees_for_view(view)
        criteria = self.env['sfa.target.criteria'].search([('active', '=', True)], order='sequence, name')

        totals = self._totals_by_criteria(period, employees, criteria)
        earned, inc_breakdown = self._incentive_for(period, employees)

        crit_rows, total_target, total_actual = [], 0.0, 0.0
        for c in criteria:
            t = totals[c.id]['target']
            a = totals[c.id]['actual']
            total_target += t
            total_actual += a
            crit_rows.append({
                'id': c.id, 'name': c.name, 'category': c.category or '',
                'target': t, 'actual': a, 'pct': self._pct(a, t),
            })

        # Comparison period overall %
        cmp_pct = None
        if comparison:
            cmp_tot = self._totals_by_criteria(comparison, employees, criteria)
            ct = sum(v['target'] for v in cmp_tot.values())
            ca = sum(v['actual'] for v in cmp_tot.values())
            cmp_pct = self._pct(ca, ct)

        # Top performers — overall % per employee
        performers = []
        for emp in employees:
            et = self._totals_by_criteria(period, emp, criteria)
            tt = sum(v['target'] for v in et.values())
            aa = sum(v['actual'] for v in et.values())
            if tt or aa:
                performers.append({'name': emp.name, 'pct': self._pct(aa, tt),
                                   'target': tt, 'actual': aa})
        performers.sort(key=lambda p: p['pct'], reverse=True)

        # Incentive breakdown (per criteria name)
        crit_name = {c.id: c.name for c in criteria}
        incentive_breakdown = [
            {'name': crit_name.get(cid, 'Other'), 'amount': amt}
            for cid, amt in sorted(inc_breakdown.items(), key=lambda kv: kv[1], reverse=True) if amt
        ]

        # Performance trend — last 4 monthly periods up to the selected one
        trend = []
        if period:
            monthly = Period.search([
                ('period_type', '=', 'monthly'),
                ('date_from', '<=', period.date_from),
            ], order='date_from desc', limit=4)
            for p in reversed(monthly):
                pt = self._totals_by_criteria(p, employees, criteria)
                trend.append({
                    'label': p.name,
                    'target': sum(v['target'] for v in pt.values()),
                    'actual': sum(v['actual'] for v in pt.values()),
                })

        return {
            'view': view,
            'periods': [{'id': p.id, 'name': p.name} for p in periods],
            'period_id': period.id or False,
            'comparison_period_id': comparison.id or False,
            'summary': {
                'overall_pct': self._pct(total_actual, total_target),
                'total_target': total_target,
                'total_actual': total_actual,
                'incentive_earned': earned,
                'comparison_pct': cmp_pct,
            },
            'criteria': crit_rows,
            'top_performers': performers[:10],
            'incentive_breakdown': incentive_breakdown,
            'trend': trend,
        }
