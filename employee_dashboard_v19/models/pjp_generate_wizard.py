# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)


class PjpGenerateWizard(models.TransientModel):
    _name = 'pjp.generate.wizard'
    _description = 'Generate / Regenerate PJP'

    name = fields.Char(string='Name', default='New PJP Generation')
    
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True,
        default=lambda self: self._default_employee())
    date_from = fields.Date(
        string='From Date', required=True,
        default=lambda self: date.today().replace(day=1))
    date_to = fields.Date(
        string='To Date', required=True,
        default=lambda self: self._last_day_of_month())
    exclude_weekoffs = fields.Boolean(
        string='Exclude Weekoff Days', default=True,
        help="Skip days that are configured as weekoff for this employee")
    exclude_holidays = fields.Boolean(
        string='Exclude Public Holidays', default=True,
        help="Skip public holidays (requires HR Holidays module)")
    exclude_leaves = fields.Boolean(
        string='Exclude Employee Leaves', default=True,
        help="Skip approved leave dates for this employee")
    is_regenerate = fields.Boolean(
        string='Regenerate (delete existing items in range)', default=False)
    pjp_id = fields.Many2one(
        'pjp.model', string='Target PJP',
        help="Leave empty to create a new PJP, or select existing to add items to it")

    # Summary info (computed)
    existing_pjp_count = fields.Integer(
        string='Existing PJPs', compute='_compute_info')
    beat_count_in_range = fields.Integer(
        string='Beats in Range', compute='_compute_info')

    def _default_employee(self):
        ctx = self.env.context
        if ctx.get('default_employee_id'):
            return ctx['default_employee_id']
        emp = self.env['hr.employee'].search(
            [('user_id', '=', self.env.uid)], limit=1)
        return emp.id if emp else False

    def _last_day_of_month(self):
        today = date.today()
        next_month = today.replace(day=28) + timedelta(days=4)
        return next_month - timedelta(days=next_month.day)

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_info(self):
        for rec in self:
            if rec.employee_id and rec.date_from and rec.date_to:
                rec.existing_pjp_count = self.env['pjp.model'].search_count([
                    ('employee_id', '=', rec.employee_id.id),
                    ('start_date', '<=', rec.date_to),
                    ('end_date', '>=', rec.date_from),
                ])
                rec.beat_count_in_range = self.env['beat.module'].search_count([
                    ('employee_id', '=', rec.employee_id.id),
                    ('beat_date', '>=', rec.date_from),
                    ('beat_date', '<=', rec.date_to),
                ])
            else:
                rec.existing_pjp_count = 0
                rec.beat_count_in_range = 0

    def _get_excluded_dates(self):
        """Return a set of dates to skip."""
        self.ensure_one()
        excluded = set()
        emp = self.employee_id

        # Weekoff days
        if self.exclude_weekoffs:
            weekoff_days = emp.get_weekoff_day_numbers()
            cursor = self.date_from
            while cursor <= self.date_to:
                if cursor.weekday() in weekoff_days:
                    excluded.add(cursor)
                cursor += timedelta(days=1)

        # Public holidays
        if self.exclude_holidays:
            try:
                holidays = self.env['hr.leave.public.line'].search([
                    ('date', '>=', self.date_from),
                    ('date', '<=', self.date_to),
                ])
                for h in holidays:
                    excluded.add(h.date)
            except Exception:
                # hr.leave.public not installed — skip silently
                pass

        # Employee approved leaves
        if self.exclude_leaves:
            try:
                leaves = self.env['hr.leave'].search([
                    ('employee_id', '=', emp.id),
                    ('state', '=', 'validate'),
                    ('date_from', '<=', fields.Datetime.to_datetime(str(self.date_to) + ' 23:59:59')),
                    ('date_to', '>=', fields.Datetime.to_datetime(str(self.date_from) + ' 00:00:00')),
                ])
                for leave in leaves:
                    d = leave.date_from.date()
                    end_d = leave.date_to.date()
                    while d <= end_d:
                        if self.date_from <= d <= self.date_to:
                            excluded.add(d)
                        d += timedelta(days=1)
            except Exception:
                pass

        return excluded

    def action_generate(self):
        self.ensure_one()
        if not self.date_from or not self.date_to or self.date_from > self.date_to:
            raise UserError("Please set a valid date range.")

        emp = self.employee_id
        excluded_dates = self._get_excluded_dates()

        # Find beats in range for this employee
        beats = self.env['beat.module'].search([
            ('employee_id', '=', emp.id),
            ('beat_date', '>=', self.date_from),
            ('beat_date', '<=', self.date_to),
        ], order='beat_date asc')

        if not beats:
            raise UserError(
                f"No beats found for {emp.name} between "
                f"{self.date_from} and {self.date_to}.\n"
                "Please create beat assignments for the date range first."
            )

        # Get or create PJP
        pjp = self.pjp_id
        if not pjp:
            existing = self.env['pjp.model'].search([
                ('employee_id', '=', emp.id),
                ('start_date', '<=', self.date_to),
                ('end_date', '>=', self.date_from),
                ('state', 'not in', ['completed', 'cancelled']),
            ], limit=1)
            if existing:
                pjp = existing
            else:
                pjp = self.env['pjp.model'].create({
                    'employee_id': emp.id,
                    'start_date': self.date_from,
                    'end_date': self.date_to,
                    'state': 'draft',
                })

        # Widen PJP date range if needed
        if pjp.start_date > self.date_from:
            pjp.start_date = self.date_from
        if pjp.end_date < self.date_to:
            pjp.end_date = self.date_to

        # Delete existing items in range if regenerating
        if self.is_regenerate:
            existing_items = self.env['pjp.item'].search([
                ('pjp_id', '=', pjp.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
                ('status', 'in', ['draft', 'approved']),
            ])
            existing_items.unlink()

        # Dates already covered
        covered_dates = set(
            self.env['pjp.item'].search([
                ('pjp_id', '=', pjp.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
            ]).mapped('date')
        )

        # Create PJP items for each beat not excluded
        items_created = 0
        items_to_create = []
        for beat in beats:
            beat_date = beat.beat_date
            if beat_date in excluded_dates:
                continue
            if beat_date in covered_dates:
                continue
            items_to_create.append({
                'pjp_id': pjp.id,
                'assigned_beat_id': beat.id,
                'date': beat_date,
                'status': 'draft',
            })
            covered_dates.add(beat_date)
            items_created += 1

        all_beat_templates = self.env['beat.module'].search([
            ('employee_id', '=', emp.id),
            ('active', '=', True)
        ])
        
        if not all_beat_templates:
            raise UserError("No active beats configured for this employee.")

        items_to_create = []
        cursor = self.date_from
        beat_list = list(all_beat_templates) # Convert to list for indexing
        beat_index = 0 # Round-robin counter
        
        while cursor <= self.date_to:
            # 2. Skip Sundays (index 6) - Mandatory Requirement
            if cursor.weekday() == 6:
                cursor += timedelta(days=1)
                continue
                
            # Skip excluded dates (weekoffs, leaves)
            if cursor in excluded_dates:
                cursor += timedelta(days=1)
                continue
                
            # Skip if date already has a beat assigned
            if self.env['pjp.item'].search_count([('pjp_id', '=', pjp.id), ('date', '=', cursor)]) > 0:
                cursor += timedelta(days=1)
                continue

            # 3. Round-Robin Assignment
            current_beat = beat_list[beat_index % len(beat_list)]
            
            items_to_create.append({
                'pjp_id': pjp.id,
                'assigned_beat_id': current_beat.id,
                'date': cursor,
                'status': 'draft',
            })
            
            # Increment counter to pick next beat tomorrow
            beat_index += 1
            items_created += 1
            
            cursor += timedelta(days=1)

        if items_to_create:
            self.env['pjp.item'].create(items_to_create)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Journey Plan',
            'res_model': 'pjp.model',
            'res_id': pjp.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_employee_id': emp.id,
                'generated_items': items_created,
            },
        }
