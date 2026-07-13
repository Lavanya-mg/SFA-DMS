# -*- coding: utf-8 -*-
import calendar as cal
import logging
from datetime import date as date_cls
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# Maps sfa.target.criteria code → (target_field, actual_field) on kpi.target
_CRITERIA_FIELD_MAP = {
    'collection': ('target_payment_collected', 'actual_payment_collected'),
    'new_outlets': ('target_new_dealers', 'actual_new_dealers'),
    'productive_calls': ('target_visits', 'actual_visits'),
    'revenue': ('target_orders', 'actual_order_amount'),
}

# Maps sfa.target.criteria code → the achievement-% field kpi.target already
# computes (consistent target/actual units, and matches the KPI dashboard).
_CRITERIA_ACHIEVEMENT_MAP = {
    'collection': 'achievement_payment_collected',
    'new_outlets': 'achievement_new_dealers',
    'productive_calls': 'achievement_visits',
    'revenue': 'achievement_orders',
}


class SfaIncentiveDashboard(models.Model):
    """Service model providing RPC methods for the Incentive Dashboard OWL component."""
    _name = 'sfa.incentive.dashboard'
    _description = 'Incentive Dashboard'

    # ── Helper ──────────────────────────────────────────────────────────────────

    def _month_range(self, month, year):
        last_day = cal.monthrange(year, month)[1]
        return date_cls(year, month, 1), date_cls(year, month, last_day)

    def _period_domain(self, period_id=None, month=None, year=None):
        """Build domain for filtering incentive records by period."""
        return [('period_month', '=', month), ('period_year', '=', year)]

    def _best_slab(self, criteria, achievement, territory_ids, profile_id, ref_date):
        """Pick the slab that applies to (criteria, achievement, territory, profile).

        A slab matches when its achievement range contains the achievement AND
        each of its criteria / territory / profile is either blank (Universal) or
        matches the employee's. When several match, the MOST SPECIFIC one wins
        (criteria-specific beats universal, then territory, then profile), then
        sort_order. This implements the transcript's rule: leave a dimension blank
        to apply to all, or set it to target a specific criteria/role/territory."""
        Slab = self.env['sfa.incentive.slab']
        domain = [
            ('active', '=', True),
            ('min_achievement', '<=', achievement),
            ('max_achievement', '>=', achievement),
            '|', ('criteria_id', '=', criteria.id), ('criteria_id', '=', False),
            '|', ('date_from', '=', False), ('date_from', '<=', str(ref_date)),
            '|', ('date_to', '=', False), ('date_to', '>=', str(ref_date)),
        ]
        if territory_ids:
            domain += ['|', ('territory_id', '=', False), ('territory_id', 'in', list(territory_ids))]
        else:
            domain += [('territory_id', '=', False)]
        if profile_id:
            domain += ['|', ('profile_id', '=', False), ('profile_id', '=', profile_id)]
        else:
            domain += [('profile_id', '=', False)]

        slabs = Slab.search(domain, order='sort_order, id')
        if not slabs:
            return Slab

        def _specificity(s):
            return ((4 if s.criteria_id else 0)
                    + (2 if s.territory_id else 0)
                    + (1 if s.profile_id else 0))

        return sorted(slabs, key=lambda s: (-_specificity(s), s.sort_order, s.id))[0]

    # ── OWL RPC methods ─────────────────────────────────────────────────────────

    @api.model
    def get_periods(self):
        """Return all active kpi.target.period records for the Period dropdown."""
        periods = self.env['kpi.target.period'].search(
            [('active', '=', True)], order='date_from desc'
        )
        return [{'id': p.id, 'name': p.name, 'type': p.period_type,
                 'date_from': str(p.date_from), 'date_to': str(p.date_to)}
                for p in periods]

    @api.model
    def get_dashboard_data(self, month, year, criteria_id=None, profile_id=None,
                           territory_id=None, status=None, period_id=None):
        """Return stats + filtered incentive records for the dashboard."""
        base = self._period_domain(month=month, year=year)
        domain = list(base)
        if criteria_id:
            domain.append(('criteria_id', '=', criteria_id))
        if profile_id:
            domain.append(('profile_id', '=', profile_id))
        if territory_id:
            domain.append(('territory_id', '=', territory_id))
        if status and status != 'all':
            domain.append(('status', '=', status))

        Record = self.env['sfa.incentive.record']
        records = Record.search(domain)

        # Stats (without status filter)
        all_domain = list(base)
        if criteria_id:
            all_domain.append(('criteria_id', '=', criteria_id))
        if profile_id:
            all_domain.append(('profile_id', '=', profile_id))
        if territory_id:
            all_domain.append(('territory_id', '=', territory_id))

        all_records = Record.search(all_domain)

        def _stat(stat_status):
            recs = all_records.filtered(lambda r: r.status == stat_status)
            return {
                'count': len(recs),
                'amount': sum(recs.mapped('calculated_amount')),
            }

        # Filter options
        criteria_list = self.env['sfa.target.criteria'].search([]).read(['id', 'name'])
        profile_list = self.env['sfa.incentive.profile'].search([]).read(['id', 'name'])
        territory_list = self.env['fmcg.territory'].search([]).read(['id', 'name'])

        return {
            'stats': {
                'calculated': _stat('calculated'),
                'pending_approval': _stat('pending_approval'),
                'approved': _stat('approved'),
                'paid': _stat('paid'),
            },
            'records': [{
                'id': r.id,
                'employee': r.employee_id.name or '',
                'criteria': r.criteria_id.name or '',
                'territory': r.territory_id.name or '',
                'achievement_percent': r.achievement_percent,
                'slab': r.slab_id.name or '',
                'calculated_amount': r.calculated_amount,
                'final_amount': r.final_amount,
                'status': r.status,
                'period': r.period_display or '',
            } for r in records],
            'filter_options': {
                'criteria': criteria_list,
                'profiles': profile_list,
                'territories': territory_list,
            },
        }

    @api.model
    def run_calculation(self, month, year, criteria_ids=None, territory_ids=None,
                        annual=False, period_id=None):
        """Calculate incentives for all employees for the given period."""
        Slab = self.env['sfa.incentive.slab']
        Record = self.env['sfa.incentive.record']
        KpiTarget = self.env['kpi.target']
        created = 0

        # Determine date ranges to process
        if annual:
            date_ranges = [(self._month_range(m, year)[0], self._month_range(m, year)[1])
                           for m in range(1, 13)]
        else:
            df, dt = self._month_range(month, year)
            date_ranges = [(df, dt)]

        for df, dt in date_ranges:
            m = df.month
            calc_year = df.year

            # Find all KPI targets in this period
            kpi_targets = KpiTarget.search([
                ('period_id.date_from', '<=', str(dt)),
                ('period_id.date_to', '>=', str(df)),
            ])

            criteria_recs = self.env['sfa.target.criteria'].search(
                [('id', 'in', criteria_ids)] if criteria_ids else []
            ) or self.env['sfa.target.criteria'].search([])

            for kpi in kpi_targets:
                employee = kpi.employee_id
                if not employee:
                    continue

                # Employee's territories (M2m) and incentive profile drive which
                # profile-/territory-specific slabs are eligible.
                territory_ids = employee.territory_id.ids if 'territory_id' in employee._fields else []
                emp_profile = employee.profile_id if 'profile_id' in employee._fields else False
                emp_profile_id = emp_profile.id if emp_profile else False

                for criteria in criteria_recs:
                    field_map = _CRITERIA_FIELD_MAP.get(criteria.code)
                    if field_map:
                        target_val = getattr(kpi, field_map[0], 0) or 0
                        actual_val = getattr(kpi, field_map[1], 0) or 0
                    elif criteria.target_field and criteria.actual_field:
                        target_val = getattr(kpi, criteria.target_field, 0) or 0
                        actual_val = getattr(kpi, criteria.actual_field, 0) or 0
                    else:
                        continue

                    # Achievement %: prefer the value kpi.target already computes
                    # (correct units, matches the KPI dashboard); fall back to
                    # actual/target only for custom criteria without one.
                    ach_field = _CRITERIA_ACHIEVEMENT_MAP.get(criteria.code)
                    if ach_field and ach_field in kpi._fields:
                        achievement = getattr(kpi, ach_field, 0) or 0
                    else:
                        achievement = (actual_val / target_val * 100) if target_val else 0

                    # Match the best slab for this criteria / territory / profile
                    slab = self._best_slab(criteria, achievement, territory_ids,
                                           emp_profile_id, df)

                    # Compute payout
                    calculated = 0.0
                    if slab:
                        if slab.payout_type == 'percentage':
                            calculated = target_val * (slab.payout_value / 100.0) * slab.multiplier
                        elif slab.payout_type == 'fixed':
                            calculated = slab.payout_value * slab.multiplier
                        elif slab.payout_type == 'salary_pct':
                            gross = employee.contract_id.wage if employee.contract_id else 0
                            calculated = gross * (slab.payout_value / 100.0) * slab.multiplier

                    # Upsert record
                    search_domain = [
                        ('employee_id', '=', employee.id),
                        ('criteria_id', '=', criteria.id),
                        ('period_month', '=', m),
                        ('period_year', '=', calc_year),
                        ('status', 'in', ('calculated',)),
                    ]
                    existing = Record.search(search_domain, limit=1)

                    # Record the resolved territory (slab's, else the employee's
                    # first territory) and the employee's incentive profile.
                    rec_territory_id = (slab.territory_id.id if slab and slab.territory_id
                                        else (territory_ids[0] if territory_ids else False))
                    vals = {
                        'target_value': target_val,
                        'actual_value': actual_val,
                        'achievement_percent': achievement,
                        'slab_id': slab.id if slab else False,
                        'territory_id': rec_territory_id,
                        'profile_id': emp_profile_id,
                        'calculated_amount': calculated,
                        'final_amount': calculated,
                        'status': 'calculated',
                    }
                    if existing:
                        existing.write(vals)
                    else:
                        vals.update({
                            'employee_id': employee.id,
                            'period_month': m,
                            'period_year': calc_year,
                            'criteria_id': criteria.id,
                        })
                        Record.create(vals)
                        created += 1

        label = 'Annual %s' % year if annual else '%s %s' % (cal.month_abbr[month], year)
        return {'message': _('Calculation complete for %s. %d records created/updated.') % (label, created)}

    @api.model
    def get_slab_manager_data(self, criteria_id=None, profile_id=None,
                               territory_id=None, payout_type=None, active_filter=None):
        """Return slabs + stats + filter options for the Slab Manager OWL component."""
        domain = []
        if active_filter == 'active':
            domain.append(('active', '=', True))
        elif active_filter == 'inactive':
            domain.append(('active', '=', False))
        else:
            domain.append(('active', 'in', [True, False]))

        if criteria_id:
            domain.append(('criteria_id', '=', criteria_id))
        if profile_id:
            domain.append(('profile_id', '=', profile_id))
        if territory_id:
            domain.append(('territory_id', '=', territory_id))
        if payout_type:
            domain.append(('payout_type', '=', payout_type))

        Slab = self.env['sfa.incentive.slab'].with_context(active_test=False)
        slabs = Slab.search(domain, order='sort_order, id')

        all_slabs = Slab.search([('active', 'in', [True, False])])
        total = len(all_slabs)
        active_count = len(all_slabs.filtered(lambda s: s.active))
        inactive_count = total - active_count

        records = []
        for s in slabs:
            records.append({
                'id': s.id,
                'name': s.name,
                'criteria_id': s.criteria_id.id if s.criteria_id else False,
                'criteria': s.criteria_id.name or 'Universal',
                'profile_id': s.profile_id.id if s.profile_id else False,
                'profile': s.profile_id.name or 'All',
                'territory_id': s.territory_id.id if s.territory_id else False,
                'territory': s.territory_id.name or 'All',
                'range': '%g%% — %g%%' % (s.min_achievement, s.max_achievement),
                'payout': s.payout_display or '',
                'payout_type': s.payout_type,
                'multiplier': ('%gx' % s.multiplier) if s.multiplier == int(s.multiplier) else ('%sx' % round(s.multiplier, 2)),
                'active': s.active,
                'sort_order': s.sort_order,
            })

        criteria_list = self.env['sfa.target.criteria'].search([]).read(['id', 'name'])
        profile_list = self.env['sfa.incentive.profile'].search([]).read(['id', 'name'])
        territory_list = self.env['fmcg.territory'].search([]).read(['id', 'name'])

        return {
            'stats': {'total': total, 'active': active_count, 'inactive': inactive_count},
            'slabs': records,
            'filter_options': {
                'criteria': criteria_list,
                'profiles': profile_list,
                'territories': territory_list,
            },
        }

    @api.model
    def toggle_slab_active(self, slab_id):
        slab = self.env['sfa.incentive.slab'].with_context(active_test=False).browse(slab_id)
        if slab.exists():
            slab.write({'active': not slab.active})
        return {'active': slab.active}

    @api.model
    def delete_slab(self, slab_id):
        slab = self.env['sfa.incentive.slab'].with_context(active_test=False).browse(slab_id)
        if slab.exists():
            slab.unlink()
        return True

    @api.model
    def copy_slab(self, slab_id):
        slab = self.env['sfa.incentive.slab'].with_context(active_test=False).browse(slab_id)
        if not slab.exists():
            raise UserError(_('Slab not found.'))
        new = slab.copy({'name': slab.name + ' (Copy)', 'active': False})
        return new.id

    @api.model
    def update_record_status(self, record_id, new_status, reason=None):
        """Change status of an incentive record (approval workflow)."""
        record = self.env['sfa.incentive.record'].browse(record_id)
        if not record.exists():
            raise UserError(_('Record not found.'))

        vals = {'status': new_status}
        if new_status == 'approved':
            vals.update({
                'approved_by': self.env.user.id,
                'approved_date': fields.Date.today(),
                'final_amount': record.calculated_amount,
            })
        elif new_status == 'rejected' and reason:
            vals['rejection_reason'] = reason
        elif new_status == 'paid':
            vals['payment_date'] = fields.Date.today()

        record.write(vals)
        return {'status': new_status}
