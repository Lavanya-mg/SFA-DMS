# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — Executive Beat Report
from odoo import api, fields, models
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class ExecutiveBeatReportWizard(models.TransientModel):
    _name = 'executive.beat.report.wizard'
    _description = 'Generate Executive Beat Report'

    date_from = fields.Date(string='Date From', required=True, default=fields.Date.today)
    date_to = fields.Date(string='Date To', required=True, default=fields.Date.today)
    employee_id = fields.Many2one(
        'hr.employee', string='Executive (Optional)',
        help='Leave empty to generate for all executives.')

    def action_generate(self):
        Report = self.env['executive.beat.report'].sudo()
        current_date = self.date_from
        while current_date <= self.date_to:
            date_start = fields.Datetime.from_string(str(current_date) + ' 00:00:00')
            date_end = fields.Datetime.from_string(str(current_date) + ' 23:59:59')

            att_domain = [('check_in', '>=', date_start), ('check_in', '<=', date_end)]
            if self.employee_id:
                att_domain.append(('employee_id', '=', self.employee_id.id))

            attendances = self.env['hr.attendance'].sudo().search(
                att_domain, order='employee_id asc, check_in asc')

            seen = {}
            for att in attendances:
                if att.employee_id.id not in seen:
                    seen[att.employee_id.id] = att

            for emp_id, attendance in seen.items():
                employee = attendance.employee_id
                existing = Report.search([
                    ('employee_id', '=', employee.id), ('date', '=', current_date)], limit=1)
                if existing:
                    existing.unlink()

                switches = self.env['beat.switch.history'].sudo().search([
                    ('employee_id', '=', employee.id), ('switch_date', '=', current_date)],
                    order='switch_time asc')

                starting_beat = (switches[0].start_beat_id if switches
                                 else self.env['beat.module'].sudo().search([
                                     ('employee_id', '=', employee.id),
                                     ('beat_date', '=', current_date),
                                     ('status', 'not in', ['swapped']),
                                 ], order='id asc', limit=1))

                current_beat = switches[-1].switched_beat_id if switches else starting_beat

                switch_lines = [(0, 0, {
                    'sequence': idx,
                    'switch_time': sw.switch_time,
                    'from_beat_id': sw.start_beat_id.id,
                    'to_beat_id': sw.switched_beat_id.id,
                    'reason': sw.reason or '',
                }) for idx, sw in enumerate(switches, 1)]

                Report.create([{
                    'employee_id': employee.id,
                    'date': current_date,
                    'check_in': attendance.check_in,
                    'check_out': attendance.check_out,
                    'assigned_beat_id': starting_beat.id if starting_beat else False,
                    'current_beat_id': current_beat.id if current_beat else False,
                    'switch_count': len(switches),
                    'switch_ids': switch_lines,
                }])

            current_date += timedelta(days=1)

        action = self.env.ref(
            'employee_dashboard_v19.action_executive_beat_report_list').read()[0]
        action['domain'] = [
            ('date', '>=', self.date_from), ('date', '<=', self.date_to)]
        if self.employee_id:
            action['domain'].append(('employee_id', '=', self.employee_id.id))
        return action


class ExecutiveBeatReport(models.Model):
    _name = 'executive.beat.report'
    _description = 'Executive Beat Report'
    _order = 'date desc, employee_id asc'
    _rec_name = 'display_name'

    employee_id = fields.Many2one(
        'hr.employee', string='Executive', required=True, index=True, readonly=True)
    date = fields.Date(string='Date', required=True, index=True, readonly=True)
    check_in = fields.Datetime(string='Check In', readonly=True)
    check_out = fields.Datetime(string='Check Out', readonly=True)
    worked_hours = fields.Float(
        string='Worked Hours', compute='_compute_worked_hours', store=True)
    assigned_beat_id = fields.Many2one('beat.module', string='Assigned Beat', readonly=True)
    assigned_beat_number = fields.Char(
        related='assigned_beat_id.beat_number', string='Assigned Beat No.', store=True)
    current_beat_id = fields.Many2one('beat.module', string='Current / Last Beat', readonly=True)
    current_beat_number = fields.Char(
        related='current_beat_id.beat_number', string='Current Beat No.', store=True)
    switch_count = fields.Integer(string='No. of Switches', readonly=True, default=0)
    switch_ids = fields.One2many(
        'executive.beat.report.switch', 'report_id', string='Switch Details', readonly=True)
    department_id = fields.Many2one(
        related='employee_id.department_id', string='Department', store=True, readonly=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)

    _sql_constraints = [
        ('unique_employee_date', 'UNIQUE(employee_id, date)',
         'Only one report per executive per day is allowed.'),
    ]

    @api.depends('check_in', 'check_out')
    def _compute_worked_hours(self):
        for rec in self:
            if rec.check_in and rec.check_out:
                rec.worked_hours = (rec.check_out - rec.check_in).total_seconds() / 3600.0
            else:
                rec.worked_hours = 0.0

    @api.depends('employee_id', 'date')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.employee_id.name or ''} – {rec.date or ''}"


class ExecutiveBeatReportSwitch(models.Model):
    _name = 'executive.beat.report.switch'
    _description = 'Executive Beat Report Switch Detail'
    _order = 'sequence, switch_time asc'

    report_id = fields.Many2one(
        'executive.beat.report', string='Report', required=True, ondelete='cascade', index=True)
    sequence = fields.Integer(string='#', default=10)
    switch_time = fields.Datetime(string='Switch Time', readonly=True)
    from_beat_id = fields.Many2one('beat.module', string='From Beat', readonly=True)
    from_beat_number = fields.Char(related='from_beat_id.beat_number', store=True)
    from_beat_name = fields.Char(related='from_beat_id.name', store=True)
    to_beat_id = fields.Many2one('beat.module', string='To Beat', readonly=True)
    to_beat_number = fields.Char(related='to_beat_id.beat_number', store=True)
    to_beat_name = fields.Char(related='to_beat_id.name', store=True)
    reason = fields.Text(string='Reason', readonly=True)
