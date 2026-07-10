# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — Dashboard Report data provider
from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class DashboardReport(models.AbstractModel):
    """Aggregated data provider for the Employee 360 Dashboard."""
    _name = 'dashboard.report'
    _description = 'Dashboard Report – Data Provider'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None,
                           employee_id=None, department_id=None):
        today = fields.Date.today()
        if not date_from:
            date_from = today.replace(day=1)
        if not date_to:
            date_to = today

        dt_from = str(date_from) + ' 00:00:00'
        dt_to = str(date_to) + ' 23:59:59'

        emp_filter = [('employee_id', '=', employee_id)] if employee_id else []
        dept_emp_filter = []
        if department_id and not employee_id:
            dept_emps = self.env['hr.employee'].sudo().search(
                [('department_id', '=', department_id)])
            if dept_emps:
                dept_emp_filter = [('employee_id', 'in', dept_emps.ids)]

        eff_emp = emp_filter or dept_emp_filter

        # ── Visits ────────────────────────────────────────────────
        Visit = self.env['visit.model'].sudo()
        visits = Visit.search([
            ('actual_start_time', '>=', dt_from),
            ('actual_start_time', '<=', dt_to),
        ] + eff_emp)
        completed = visits.filtered(lambda v: v.status == 'completed')
        productive = visits.filtered(lambda v: v.is_productive)
        order_amount = sum(completed.mapped('total_order_amount'))

        visit_status_map = {}
        for v in visits:
            lbl = dict(v._fields['status'].selection).get(v.status, v.status or '')
            visit_status_map[lbl] = visit_status_map.get(lbl, 0) + 1

        monthly_v = {}
        for v in visits:
            if v.actual_start_time:
                mk = v.actual_start_time.strftime('%b %Y')
                if mk not in monthly_v:
                    monthly_v[mk] = {'completed': 0, 'planned': 0,
                                     'in_progress': 0, 'cancelled': 0}
                monthly_v[mk][v.status or 'planned'] = (
                    monthly_v[mk].get(v.status or 'planned', 0) + 1)

        emp_visit = {}
        for v in visits:
            name = v.employee_id.name if v.employee_id else 'Unknown'
            if name not in emp_visit:
                emp_visit[name] = {'count': 0, 'amount': 0.0}
            emp_visit[name]['count'] += 1
            emp_visit[name]['amount'] += v.total_order_amount or 0.0

        top_emp_visits = sorted(
            emp_visit.items(), key=lambda x: x[1]['count'], reverse=True)[:10]

        # ── Attendance ────────────────────────────────────────────
        Att = self.env['hr.attendance'].sudo()
        atts = Att.search([
            ('check_in', '>=', dt_from), ('check_in', '<=', dt_to)] + eff_emp)
        total_worked = sum(atts.mapped('worked_hours'))

        emp_att = {}
        for a in atts:
            name = a.employee_id.name if a.employee_id else 'Unknown'
            emp_att[name] = emp_att.get(name, 0.0) + (a.worked_hours or 0.0)

        monthly_att = {}
        for a in atts:
            if a.check_in:
                mk = a.check_in.strftime('%b %Y')
                monthly_att[mk] = monthly_att.get(mk, 0.0) + (a.worked_hours or 0.0)

        # ── Beat Reports ──────────────────────────────────────────
        BeatRep = self.env['executive.beat.report'].sudo()
        beat_reps = BeatRep.search([
            ('date', '>=', str(date_from)),
            ('date', '<=', str(date_to))] + eff_emp)
        total_switches = sum(beat_reps.mapped('switch_count'))

        beat_switch_dist = {
            'With Switches': len(beat_reps.filtered(lambda r: r.switch_count > 0)),
            'No Switches': len(beat_reps.filtered(lambda r: r.switch_count == 0)),
        }
        emp_sw = {}
        for br in beat_reps:
            name = br.employee_id.name if br.employee_id else 'Unknown'
            emp_sw[name] = emp_sw.get(name, 0) + (br.switch_count or 0)
        top_sw = sorted(emp_sw.items(), key=lambda x: x[1], reverse=True)[:10]

        Beat = self.env['beat.module'].sudo()
        all_beats = Beat.search([
            ('beat_date', '>=', str(date_from)),
            ('beat_date', '<=', str(date_to))] + eff_emp)
        beat_status = {}
        for b in all_beats:
            lbl = dict(b._fields['status'].selection).get(b.status, b.status or '')
            beat_status[lbl] = beat_status.get(lbl, 0) + 1

        # ── PJP ──────────────────────────────────────────────────
        PJP = self.env['pjp.model'].sudo()
        pjps = PJP.search([
            ('start_date', '<=', str(date_to)),
            ('end_date', '>=', str(date_from))] + eff_emp)
        pjp_status = {}
        for p in pjps:
            lbl = dict(p._fields['state'].selection).get(p.state, p.state or '')
            pjp_status[lbl] = pjp_status.get(lbl, 0) + 1

        # ── Recent lists ──────────────────────────────────────────
        recent_visits = []
        for v in sorted(visits, key=lambda x: x.actual_start_time or
                        x.planned_start_time, reverse=True)[:10]:
            recent_visits.append({
                'name': v.name or '',
                'employee': v.employee_id.name if v.employee_id else '',
                'customer': v.partner_id.name if v.partner_id else '',
                'status': dict(v._fields['status'].selection).get(v.status, v.status or ''),
                'date': v.actual_start_time.strftime('%d/%m/%Y') if v.actual_start_time else '',
                'amount': round(v.total_order_amount or 0.0, 2),
            })

        mv_labels = list(monthly_v.keys())
        currency = self.env.company.currency_id.symbol or '$'

        return {
            'kpi': {
                'total_visits': len(visits),
                'completed_visits': len(completed),
                'productive_visits': len(productive),
                'total_order_amount': round(order_amount, 2),
                'currency_symbol': currency,
                'total_worked_hours': round(total_worked, 2),
                'total_attendance': len(atts),
                'total_pjp': len(pjps),
                'approved_pjp': len(pjps.filtered(lambda p: p.state == 'approved')),
                'active_pjp': len(pjps.filtered(lambda p: p.state == 'active')),
                'total_beat_reports': len(beat_reps),
                'total_switches': total_switches,
                'total_beats': len(all_beats),
            },
            'visit_status': {
                'labels': list(visit_status_map.keys()),
                'data': list(visit_status_map.values()),
            },
            'visit_productivity': {
                'labels': ['Productive', 'Non-Productive'],
                'data': [len(productive), len(visits) - len(productive)],
            },
            'monthly_visits': {
                'labels': mv_labels,
                'completed': [monthly_v[m].get('completed', 0) for m in mv_labels],
                'planned': [monthly_v[m].get('planned', 0) for m in mv_labels],
                'in_progress': [monthly_v[m].get('in_progress', 0) for m in mv_labels],
                'cancelled': [monthly_v[m].get('cancelled', 0) for m in mv_labels],
            },
            'employee_visits': {
                'labels': [x[0] for x in top_emp_visits],
                'counts': [x[1]['count'] for x in top_emp_visits],
                'amounts': [round(x[1]['amount'], 2) for x in top_emp_visits],
            },
            'attendance': {
                'labels': [x[0] for x in sorted(
                    emp_att.items(), key=lambda x: x[1], reverse=True)[:10]],
                'hours': [round(x[1], 2) for x in sorted(
                    emp_att.items(), key=lambda x: x[1], reverse=True)[:10]],
            },
            'monthly_attendance': {
                'labels': list(monthly_att.keys()),
                'hours': [round(v, 2) for v in monthly_att.values()],
            },
            'beat_coverage': {
                'labels': list(beat_status.keys()),
                'data': list(beat_status.values()),
            },
            'beat_switch_dist': {
                'labels': list(beat_switch_dist.keys()),
                'data': list(beat_switch_dist.values()),
            },
            'employee_switches': {
                'labels': [x[0] for x in top_sw],
                'counts': [x[1] for x in top_sw],
            },
            'pjp_status': {
                'labels': list(pjp_status.keys()),
                'data': list(pjp_status.values()),
            },
            'recent_visits': recent_visits,
            'recent_beat_reports': [],
            'recent_switch_history': [],
        }
    

    @api.model
    def get_filter_options(self):
        employees = self.env['hr.employee'].sudo().search([], order='name asc')
        departments = self.env['hr.department'].sudo().search([], order='name asc')
        return {
            'employees': [{'id': e.id, 'name': e.name} for e in employees],
            'departments': [{'id': d.id, 'name': d.name} for d in departments],
        }
