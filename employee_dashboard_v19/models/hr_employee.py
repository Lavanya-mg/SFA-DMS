# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — HR Employee extensions
from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from collections import OrderedDict
import pytz
import logging

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'
    
    joining_date   = fields.Date(string='Joining Date')
    relieving_date = fields.Date(string='Relieving Date')
    pan_number     = fields.Char(string='PAN Number')
    aadhar_number  = fields.Char(string='Aadhar Number')
    employee_code  = fields.Char(string='Employee Code')
    territory_id   = fields.Many2many(
        'fmcg.territory', 'hr_employee_territory_rel',
        'employee_id', 'territory_id',
        string='Territories', index=True,
        help="Territories assigned to this field executive")

    # ── Weekoff days ──────────────────────────────────────────────────
    weekoff_monday    = fields.Boolean(string='Monday')
    weekoff_tuesday   = fields.Boolean(string='Tuesday')
    weekoff_wednesday = fields.Boolean(string='Wednesday')
    weekoff_thursday  = fields.Boolean(string='Thursday')
    weekoff_friday    = fields.Boolean(string='Friday')
    weekoff_saturday  = fields.Boolean(string='Saturday', default=False)
    weekoff_sunday    = fields.Boolean(string='Sunday', default=True)

    def get_weekoff_day_numbers(self):
        self.ensure_one()
        mapping = {
            0: self.weekoff_monday,    1: self.weekoff_tuesday,
            2: self.weekoff_wednesday, 3: self.weekoff_thursday,
            4: self.weekoff_friday,    5: self.weekoff_saturday,
            6: self.weekoff_sunday,
        }
        return [d for d, off in mapping.items() if off]

    def _get_user_timezone(self):
        return self.env.user.tz or 'UTC'

    @api.model
    def create_attendance_checkin(self, employee_id, work_plan, travel_type,
                                  vehicle_used, location_data=None):
        """Create attendance check-in with location."""
        try:
            import pytz
            employee = self.browse(employee_id)
            if not employee.exists():
                return {'success': False, 'error': 'Employee not found'}

            HrAttendance = self.env['hr.attendance'].sudo()
            existing = HrAttendance.search([
                ('employee_id', '=', employee_id),
                ('check_out', '=', False),
            ], limit=1, order='check_in desc')

            user_tz_name = self._get_user_timezone()
            user_tz = pytz.timezone(user_tz_name)

            if existing:
                check_in_utc = pytz.UTC.localize(existing.check_in)
                check_in_local = check_in_utc.astimezone(user_tz)
                now_local = datetime.now(user_tz)
                if check_in_local.date() == now_local.date():
                    return {
                        'success': True,
                        'attendance_id': existing.id,
                        'message': f'Day already started at {check_in_local.strftime("%I:%M %p")}',
                        'check_in': check_in_local.strftime('%Y-%m-%d %H:%M:%S'),
                    }
                else:
                    # Auto-close stale open attendance
                    old_checkout = check_in_local.replace(
                        hour=23, minute=59, second=59)
                    old_checkout_utc = old_checkout.astimezone(
                        pytz.UTC).replace(tzinfo=None)
                    worked = (old_checkout_utc - existing.check_in).total_seconds() / 3600.0
                    self.env.cr.execute(
                        "UPDATE hr_attendance SET check_out=%s, worked_hours=%s,"
                        " write_date=NOW(), write_uid=%s WHERE id=%s",
                        (old_checkout_utc, worked, self.env.uid, existing.id)
                    )
                    _logger.info("Auto-closed stale attendance %s", existing.id)

            current_utc = datetime.utcnow()
            vals = {'employee_id': employee_id, 'check_in': current_utc}
            if location_data:
                vals.update({
                    'checkin_latitude': location_data.get('latitude'),
                    'checkin_longitude': location_data.get('longitude'),
                    'checkin_accuracy': location_data.get('accuracy'),
                    'checkin_full_address': location_data.get('full_address'),
                    'checkin_city': location_data.get('city'),
                    'checkin_state': location_data.get('state'),
                    'checkin_country': location_data.get('country'),
                })
            attendance = HrAttendance.create([vals])
            check_in_local = pytz.UTC.localize(
                attendance.check_in).astimezone(user_tz)
            return {
                'success': True,
                'attendance_id': attendance.id,
                'check_in': check_in_local.strftime('%Y-%m-%d %H:%M:%S'),
                'message': f'Day started at {check_in_local.strftime("%I:%M %p")}',
            }
        except Exception as e:
            _logger.error("Error in check-in: %s", e, exc_info=True)
            return {'success': False, 'error': str(e)}

    @api.model
    def create_attendance_checkout(self, employee_id, attendance_id, location_data=None):
        """Create attendance check-out with location."""
        try:
            import pytz
            HrAttendance = self.env['hr.attendance'].sudo()
            attendance = None
            if attendance_id:
                attendance = HrAttendance.browse(attendance_id)
                if not attendance.exists():
                    return {'success': False, 'error': f'Attendance {attendance_id} not found'}
                if attendance.employee_id.id != employee_id:
                    return {'success': False, 'error': 'Attendance does not belong to this employee'}
            else:
                user_tz = pytz.timezone(self._get_user_timezone())
                now_local = datetime.now(user_tz)
                today_start = now_local.replace(
                    hour=0, minute=0, second=0, microsecond=0)
                today_start_utc = today_start.astimezone(pytz.UTC).replace(tzinfo=None)
                today_end_utc = (today_start + timedelta(days=1)).astimezone(
                    pytz.UTC).replace(tzinfo=None)
                attendance = HrAttendance.search([
                    ('employee_id', '=', employee_id),
                    ('check_in', '>=', today_start_utc),
                    ('check_in', '<', today_end_utc),
                    ('check_out', '=', False),
                ], limit=1, order='check_in desc')

            if not attendance:
                return {'success': False, 'error': 'No open attendance. Please start your day first.'}
            if attendance.check_out:
                return {'success': True, 'message': 'Attendance already closed.'}

            current_utc = datetime.utcnow()
            update_vals = {'check_out': current_utc}
            if location_data:
                update_vals.update({
                    'checkout_latitude': location_data.get('latitude'),
                    'checkout_longitude': location_data.get('longitude'),
                    'checkout_accuracy': location_data.get('accuracy'),
                    'checkout_full_address': location_data.get('full_address'),
                    'checkout_city': location_data.get('city'),
                    'checkout_state': location_data.get('state'),
                    'checkout_country': location_data.get('country'),
                })
            attendance.write(update_vals)
            user_tz = pytz.timezone(self._get_user_timezone())
            checkout_local = pytz.UTC.localize(current_utc).astimezone(user_tz)
            return {
                'success': True,
                'attendance_id': attendance.id,
                'check_out': checkout_local.strftime('%Y-%m-%d %H:%M:%S'),
                'worked_hours': round(attendance.worked_hours, 2),
                'message': f'Day ended at {checkout_local.strftime("%I:%M %p")}',
            }
        except Exception as e:
            _logger.error("Error in check-out: %s", e, exc_info=True)
            return {'success': False, 'error': str(e)}

    def rotate_beats_in_month(self, month, year, rotation_frequency):
        """Rotate beats within a month based on rotation frequency."""
        first_day = datetime(year, month, 1).date()
        if month == 12:
            last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
        else:
            last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)

        today = fields.Date.today()
        if first_day < today <= last_day:
            start_date = today
        elif first_day >= today:
            start_date = first_day
        else:
            return {'success': False,
                    'message': 'Cannot rotate beats in past months.'}

        beats_with_dates = self.env['beat.module'].search([
            ('employee_id', '=', self.id),
            ('beat_date', '>=', first_day),
            ('beat_date', '<=', last_day),
            ('beat_date', '!=', False),
        ], order='beat_date asc')

        if not beats_with_dates:
            return {'success': False,
                    'message': f'No beats assigned in {first_day.strftime("%B %Y")}.'}

        beats = list(OrderedDict(
            (beat.id, beat) for beat in beats_with_dates).values())
        total_beats = len(beats)

        if rotation_frequency < total_beats:
            return {
                'success': False,
                'message': (f'Rotation frequency ({rotation_frequency}) must be at least '
                            f'equal to number of beats ({total_beats}).'),
            }

        self.env['beat.module'].search([
            ('employee_id', '=', self.id),
            ('beat_date', '>=', start_date),
            ('beat_date', '<=', last_day),
        ]).write({'beat_date': False})

        current_date = start_date
        assignments_made = 0
        new_beats_created = 0
        rotation_cycles = 0

        while current_date <= last_day:
            day_in_cycle = assignments_made % rotation_frequency
            if day_in_cycle < total_beats:
                beat_index = day_in_cycle
                original_beat = beats[beat_index]
                if rotation_cycles == 0:
                    original_beat.write({'beat_date': current_date})
                else:
                    beat_lines = self.env['beat.line'].search([
                        ('beat_id', '=', original_beat.id)])
                    new_beat = self.env['beat.module'].create([{
                        'name': f"{original_beat.name} (Rotation {rotation_cycles + 1})",
                        'employee_id': self.id,
                        'beat_date': current_date,
                        'beat_number': original_beat.beat_number,
                    }])
                    for line in beat_lines:
                        self.env['beat.line'].create([{
                            'beat_id': new_beat.id,
                            'partner_id': line.partner_id.id,
                            'sequence': line.sequence,
                            'notes': line.notes,
                        }])
                    new_beats_created += 1

            current_date += timedelta(days=1)
            assignments_made += 1
            if assignments_made % rotation_frequency == 0:
                rotation_cycles += 1

        return {
            'success': True,
            'message': (f'Rotation completed: {total_beats} beats, frequency {rotation_frequency}.'
                        f' Created {new_beats_created} new beats.'),
        }

    def create_pjp_from_calendar(self, start_date, end_date):
        # """Create ONE PJP with multiple items from calendar beats."""
        # if isinstance(start_date, str):
        #     start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        # if isinstance(end_date, str):
        #     end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # today = fields.Date.today()
        # if start_date < today:
        #     return {'success': False,
        #             'message': f'Start date cannot be in the past. Use {today} or later.'}
        # if end_date < start_date:
        #     return {'success': False, 'message': 'End date must be on or after start date.'}

        # beats = self.env['beat.module'].search([
        #     ('employee_id', '=', self.id),
        #     ('beat_date', '!=', False),
        #     ('beat_date', '>=', start_date),
        #     ('beat_date', '<=', end_date),
        #     ('beat_date', '>=', today),
        # ], order='beat_date asc')

        # if not beats:
        #     return {
        #         'success': False,
        #         'message': (f'No beats with future dates between {start_date} and {end_date}. '
        #                     'Assign beats to dates in calendar view first.'),
        #     }

        # pjp = self.env['pjp.model'].create([{
        #     'name': f'PJP - {self.name} - {start_date} to {end_date}',
        #     'employee_id': self.id,
        #     'start_date': start_date,
        #     'end_date': end_date,
        #     'state': 'draft',
        # }])

        # pjp_items = []
        # sequence = 10
        # dates_processed = set()
        # for beat in beats:
        #     if beat.beat_date in dates_processed:
        #         continue
        #     dates_processed.add(beat.beat_date)
        #     pjp_items.append({
        #         'pjp_id': pjp.id,
        #         'employee_id': self.id,
        #         'assigned_beat_id': beat.id,
        #         'date': beat.beat_date,
        #         'sequence': sequence,
        #         'status': 'draft',
        #     })
        #     sequence += 10

        # if pjp_items:
        #     self.env['pjp.item'].create(pjp_items)

        # return {
        #     'success': True,
        #     'pjp_id': pjp.id,
        #     'pjp_items_count': len(pjp_items),
        #     'message': f'PJP created with {len(pjp_items)} items.',
        # }
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()

        # 1. Fetch active beat templates
        beat_list = self.env['beat.module'].search([
            ('employee_id', '=', self.id),
            ('active', '=', True)
        ])
        
        if not beat_list:
            return {'success': False, 'message': 'No active beats configured for this employee.'}
        
        existing_pjp = self.env['pjp.model'].search([
            ('employee_id', '=', self.id),
            ('state', 'in', ['draft', 'approved', 'active']),
            ('start_date', '<=', end_date),
            ('end_date', '>=', start_date)
        ], limit=1)

        if existing_pjp:
            return {
                'success': False, 
                'message': f'A PJP already exists for this employee between {existing_pjp.start_date} and {existing_pjp.end_date}.'
            }

        # 2. Create the PJP Header
        pjp = self.env['pjp.model'].create({
            'name': f'PJP - {self.name} - {start_date} to {end_date}',
            'employee_id': self.id,
            'start_date': start_date,
            'end_date': end_date,
            'state': 'draft',
        })

        # 3. Round-Robin Loop
        pjp_items = []
        beat_index = 0
        cursor = start_date
        sequence = 10
        
        while cursor <= end_date:
            # Skip Sundays (weekday 6)
            if cursor.weekday() == 6:
                cursor += timedelta(days=1)
                continue
                
            # Assign beat from round-robin list
            current_beat = beat_list[beat_index % len(beat_list)]
            
            pjp_items.append({
                'pjp_id': pjp.id,
                'employee_id': self.id,
                'assigned_beat_id': current_beat.id,
                'date': cursor,
                'sequence': sequence,
                'status': 'draft',
            })
            
            # Increment for next round
            beat_index += 1
            sequence += 10
            cursor += timedelta(days=1)

        # 4. Create Items
        if pjp_items:
            self.env['pjp.item'].create(pjp_items)

        return {
            'success': True,
            'pjp_id': pjp.id,
            'message': f'PJP created with {len(pjp_items)} beats in round-robin format.',
        }

    @api.model
    def get_today_attendance(self, employee_id):
        """Get today's attendance record for employee"""
        try:
            if 'hr.attendance' not in self.env:
                return {'success': False, 'error': 'Attendance module not installed'}

            user_tz = self._get_user_timezone()
            user_timezone = pytz.timezone(user_tz)

            now_user = datetime.now(user_timezone)
            today_start_local = now_user.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end_local = today_start_local + timedelta(days=1)

            today_start_utc = today_start_local.astimezone(pytz.UTC).replace(tzinfo=None)
            today_end_utc = today_end_local.astimezone(pytz.UTC).replace(tzinfo=None)

            HrAttendance = self.env['hr.attendance'].sudo()

            attendance = HrAttendance.search([
                ('employee_id', '=', employee_id),
                ('check_in', '>=', today_start_utc),
                ('check_in', '<', today_end_utc),
            ], limit=1, order='check_in desc')

            if attendance:
                check_in_utc = pytz.UTC.localize(attendance.check_in)
                check_in_local = check_in_utc.astimezone(user_timezone)

                result = {
                    'success': True,
                    'attendance_id': attendance.id,
                    'check_in': check_in_local.strftime('%Y-%m-%d %H:%M:%S'),
                    'worked_hours': attendance.worked_hours or 0.0,
                    'is_checked_in': not attendance.check_out
                }

                if attendance.check_out:
                    check_out_utc = pytz.UTC.localize(attendance.check_out)
                    check_out_local = check_out_utc.astimezone(user_timezone)
                    result['check_out'] = check_out_local.strftime('%Y-%m-%d %H:%M:%S')
                else:
                    result['check_out'] = None

                return result
            else:
                return {'success': True, 'attendance_id': None, 'is_checked_in': False}

        except Exception as e:
            _logger.error(f"Error in get_today_attendance: {e}", exc_info=True)
            return {'success': False, 'error': str(e)}


class EmployeeDashboard(models.Model):
    _name = 'employee.dashboard'
    _description = 'Employee Dashboard Helper'

    @api.model
    def get_user_access_info(self):
        """Get current user's access information"""
        user = self.env.user
        is_manager = user.has_group('employee_dashboard_v19.group_employee_dashboard_manager')
        employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
        return {
            'is_manager': is_manager,
            'employee_id': employee.id if employee else False,
            'user_id': user.id,
        }

    @api.model
    def get_accessible_employees(self):
        """Get list of employees accessible to current user"""
        user = self.env.user
        is_manager = user.has_group('employee_dashboard_v19.group_employee_dashboard_manager')
        domain = []
        if not is_manager:
            employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)
            if employee:
                domain = [('id', '=', employee.id)]
            else:
                domain = [('id', '=', False)]
        employees = self.env['hr.employee'].search_read(
            domain,
            ['name', 'work_email', 'work_phone', 'user_id']
        )
        return employees

    @api.model
    def get_employee_order_stats(self, employee_id, today_start, today_end, period_from=None, period_to=None):
        """Return today's and period order counts and total amounts for an employee."""
        employee = self.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists():
            return {'orders_today': 0, 'orders_period': 0, 'amount_today': 0.0, 'amount_period': 0.0}

        SaleOrder = self.env['sale.order'].sudo()

        def _build_domain(date_start, date_end):
            base = [
                ('date_order', '>=', date_start),
                ('date_order', '<=', date_end),
                ('state', 'in', ['sale', 'done']),
            ]
            if employee.user_id:
                return [
                    '|',
                    ('user_id', '=', employee.user_id.id),
                    ('visit_id.employee_id', '=', employee.id),
                ] + base
            return [('visit_id.employee_id', '=', employee.id)] + base

        today_orders = SaleOrder.search(_build_domain(today_start, today_end))
        orders_today = len(today_orders)
        amount_today = sum(today_orders.mapped('amount_total'))

        orders_period = 0
        amount_period = 0.0
        if period_from and period_to:
            period_orders = SaleOrder.search(_build_domain(period_from, period_to))
            orders_period = len(period_orders)
            amount_period = sum(period_orders.mapped('amount_total'))

        return {
            'orders_today': orders_today,
            'orders_period': orders_period,
            'amount_today': amount_today,
            'amount_period': amount_period,
        }
