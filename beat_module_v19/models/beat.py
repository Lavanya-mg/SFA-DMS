# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class BeatSwitchHistory(models.Model):
    _name = 'beat.switch.history'
    _description = 'Beat Switch History'
    _order = 'switch_time desc'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Executive', required=True, index=True)
    switch_date = fields.Date(string='Switch Date', required=True)
    switch_time = fields.Datetime(string='Switch Time', required=True)
    start_beat_id = fields.Many2one('beat.module', string='Start Beat', required=True)
    switched_beat_id = fields.Many2one('beat.module', string='Switched To Beat', required=True)
    reason = fields.Text(string='Reason for Switch', required=True)

    @api.model
    def get_history_for_employee(self, employee_id, date=None):
        """Return beat switch history for an employee on a given date (default: today)."""
        if not date:
            date = fields.Date.today()
        records = self.search([
            ('employee_id', '=', employee_id),
            ('switch_date', '=', date),
        ], order='switch_time desc')
        result = []
        for r in records:
            result.append({
                'id': r.id,
                'employee_name': r.employee_id.name,
                'switch_date': str(r.switch_date),
                'switch_time': str(r.switch_time),
                'start_beat_number': r.start_beat_id.beat_number,
                'start_beat_name': r.start_beat_id.name,
                'switched_beat_number': r.switched_beat_id.beat_number,
                'switched_beat_name': r.switched_beat_id.name,
                'reason': r.reason,
            })
        return result


class BeatModule(models.Model):
    _name = 'beat.module'
    _description = 'Beat Module'
    _order = 'beat_number'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    beat_number = fields.Char(
        string='Beat Number',
        required=True,
        copy=False,
        readonly=True,
        default='New',
    )
    name = fields.Char(string='Name', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, tracking=True)
    beat_date = fields.Date(string='Assigned Date')
    beat_line_ids = fields.One2many('beat.line', 'beat_id', string='Beat Lines')
    customer_count = fields.Integer(
        string='Customer Count',
        compute='_compute_customer_count',
        store=True,
    )
    status = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('swapped', 'Swapped'),
    ], string='Status', default='pending', tracking=True)

    swap_reason = fields.Text(string='Swap Reason')
    swapped_date = fields.Datetime(string='Swapped Date')
    swapped_to_beat_id = fields.Many2one('beat.module', string='Swapped To Beat')
    swapped_from_beat_id = fields.Many2one('beat.module', string='Swapped From Beat')
    swap_history = fields.Text(
        string='Swap History',
        compute='_compute_swap_history',
        store=False,
    )

    active = fields.Boolean(string='Active', default=True)
    allowed_days = fields.Selection([
        ('0', 'Monday'), ('1', 'Tuesday'), ('2', 'Wednesday'),
        ('3', 'Thursday'), ('4', 'Friday'), ('5', 'Saturday'), ('6', 'Sunday')
    ], string='Allowed Day', help="The specific weekday this beat is intended for")

    @api.depends('beat_line_ids')
    def _compute_customer_count(self):
        for record in self:
            record.customer_count = len(record.beat_line_ids)

    @api.depends('swap_reason', 'swapped_date', 'swapped_to_beat_id', 'swapped_from_beat_id')
    def _compute_swap_history(self):
        for record in self:
            if record.status == 'swapped' and record.swap_reason:
                history = f"Swapped on {record.swapped_date}\n"
                history += f"Reason: {record.swap_reason}\n"
                if record.swapped_to_beat_id:
                    history += (
                        f"Swapped to: {record.swapped_to_beat_id.beat_number}"
                        f" - {record.swapped_to_beat_id.name}"
                    )
                record.swap_history = history
            elif record.swapped_from_beat_id:
                record.swap_history = (
                    f"Swapped from: {record.swapped_from_beat_id.beat_number}"
                )
            else:
                record.swap_history = ""

    # Odoo 19: use display_name (auto-computed from name field via _rec_name)
    # name_get() removed — _rec_name defaults to 'name', so display_name renders
    # as "[beat_number] name" via the override below.
    def _compute_display_name(self):
        for record in self:
            record.display_name = f"[{record.beat_number}] {record.name}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('beat_number') or vals.get('beat_number') == 'New':
                vals['beat_number'] = (
                    self.env['ir.sequence'].next_by_code('beat.module.sequence') or 'New'
                )
        records = super().create(vals_list)
        for record in records:
            record._check_one_beat_per_day()
        return records

    def write(self, vals):
        result = super().write(vals)
        if 'beat_date' in vals or 'employee_id' in vals:
            self._check_one_beat_per_day()
        return result

    @api.constrains('beat_date', 'employee_id')
    def _check_one_beat_per_day(self):
        """Enforce ONE DAY ONE BEAT rule — one beat per employee per day."""
        for record in self:
            if record.status == 'swapped':
                continue
            if record.beat_date and record.employee_id:
                existing_beats = self.search([
                    ('id', '!=', record.id),
                    ('employee_id', '=', record.employee_id.id),
                    ('beat_date', '=', record.beat_date),
                    ('status', '!=', 'swapped'),
                ])
                if existing_beats:
                    raise ValidationError(
                        f"Only one beat can be assigned per day!\n\n"
                        f"Employee '{record.employee_id.name}' already has "
                        f"beat '{existing_beats[0].beat_number}' assigned on {record.beat_date}.\n\n"
                        f"Please choose a different date or remove the existing beat first."
                    )

    def action_start_beat(self):
        self.ensure_one()
        if self.status in ['pending', 'draft']:
            self.status = 'in_progress'
            _logger.info("Beat %s started", self.beat_number)
            return True
        return False

    def action_complete_beat(self):
        self.ensure_one()
        if self.status == 'in_progress':
            self.status = 'completed'
            _logger.info("Beat %s completed", self.beat_number)
            return True
        return False

    def copy_to_date(self, target_date):
        """Create a new beat by copying this beat to a different date.

        Used by drag-and-drop in the PJP calendar so dragging creates a new beat
        instead of moving the existing one.
        """
        self.ensure_one()
        beat_lines = [(0, 0, {
            'partner_id': line.partner_id.id,
            'sequence': line.sequence,
            'notes': line.notes,
        }) for line in self.beat_line_ids]

        new_beat = self.env['beat.module'].create([{
            'name': self.name,
            'employee_id': self.employee_id.id,
            'beat_date': target_date,
            'status': 'pending',
            'beat_line_ids': beat_lines,
        }])
        return {
            'id': new_beat.id,
            'beat_number': new_beat.beat_number,
            'name': new_beat.name,
            'customer_count': new_beat.customer_count,
        }

    def action_swap_beat(self, new_beat_id, reason):
        self.ensure_one()
        if not new_beat_id or not reason:
            return {'success': False, 'error': 'New beat ID and reason are required'}

        new_beat = self.env['beat.module'].browse(new_beat_id)
        if not new_beat.exists():
            return {'success': False, 'error': 'Selected beat does not exist'}
        if new_beat.status == 'in_progress':
            return {'success': False, 'error': 'Selected beat is already in progress'}

        today_date = self.beat_date or fields.Date.today()

        self.write({
            'status': 'swapped',
            'swap_reason': reason,
            'swapped_date': fields.Datetime.now(),
            'swapped_to_beat_id': new_beat.id,
        })
        new_beat.write({
            'status': 'in_progress',
            'swapped_from_beat_id': self.id,
            'beat_date': today_date,
        })
        self.env['beat.switch.history'].create([{
            'employee_id': self.employee_id.id,
            'switch_date': fields.Date.today(),
            'switch_time': fields.Datetime.now(),
            'start_beat_id': self.id,
            'switched_beat_id': new_beat.id,
            'reason': reason,
        }])
        return {
            'success': True,
            'message': f'Beat successfully swapped and started: {new_beat.beat_number}',
            'new_beat_id': new_beat.id,
            'new_beat_name': new_beat.name,
            'new_beat_number': new_beat.beat_number,
        }


class BeatLine(models.Model):
    _name = 'beat.line'
    _description = 'Beat Line'
    _order = 'sequence, id'

    beat_id = fields.Many2one('beat.module', string='Beat', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    partner_phone = fields.Char(string='Phone', related='partner_id.phone', readonly=True, store=True)
    partner_email = fields.Char(string='Email', related='partner_id.email', readonly=True, store=True)
    partner_street = fields.Char(string='Address', related='partner_id.street', readonly=True, store=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_partner_beat', 'unique(beat_id, partner_id)',
         'This customer is already assigned to this beat!')
    ]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    beat_line_ids = fields.One2many('beat.line', 'partner_id', string='Beat Assignments')
    beat_count = fields.Integer(string='Beat Count', compute='_compute_beat_count')

    def _compute_beat_count(self):
        for record in self:
            record.beat_count = len(record.beat_line_ids)
