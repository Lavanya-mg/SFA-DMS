# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — PJP Model
from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError


class PJPModel(models.Model):
    _name = 'pjp.model'
    _description = 'Permanent Journey Plan'
    _order = 'start_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='PJP Name', required=True,
        compute='_compute_name', store=True, readonly=False)
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, index=True, tracking=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    pjp_item_ids = fields.One2many('pjp.item', 'pjp_id', string='PJP Items')
    pjp_item_count = fields.Integer(
        string='Total Items', compute='_compute_pjp_item_count')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True, tracking=True)
    notes = fields.Text(string='Notes')

    @api.depends('employee_id')
    def _compute_name(self):
        for record in self:
            if record.employee_id:
                record.name = f"PJP - {record.employee_id.name}"
            else:
                record.name = 'New PJP'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') and vals.get('employee_id'):
                emp = self.env['hr.employee'].browse(vals['employee_id'])
                vals['name'] = f"PJP - {emp.name}"
        return super().create(vals_list)

    @api.depends('pjp_item_ids')
    def _compute_pjp_item_count(self):
        for record in self:
            record.pjp_item_count = len(record.pjp_item_ids)

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_activate(self):
        self.write({'state': 'active'})

    def action_complete(self):
        self.write({'state': 'completed'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_open_beat_calendar(self):
        try:
            action = self.env.ref('employee_dashboard_v19.action_employee_component').sudo().read()[0]
        except ValueError:
            raise UserError("Employee 360 dashboard action not found. Please reinstall the employee_dashboard_v19 module.")
        action['context'] = {
            'default_employee_id': self.employee_id.id,
            'active_tab': 'pjp',
        }
        return action
    
    @api.constrains('employee_id', 'start_date', 'end_date', 'state')
    def _check_overlapping_pjps(self):
        for pjp in self:
            # We only care about active plans (draft, approved, active)
            # Completed/Cancelled plans can overlap as they are no longer in effect
            if pjp.state in ['completed', 'cancelled']:
                continue

            # Check for overlapping records
            overlapping = self.search([
                ('id', '!=', pjp.id),
                ('employee_id', '=', pjp.employee_id.id),
                ('state', 'not in', ['completed', 'cancelled']),
                ('start_date', '<=', pjp.end_date),
                ('end_date', '>=', pjp.start_date),
            ])
            
            if overlapping:
                raise ValidationError(
                    f"Overlapping PJP found for {pjp.employee_id.name}. "
                    f"Please ensure plans do not overlap between {pjp.start_date} and {pjp.end_date}."
                )


class PJPItem(models.Model):
    _name = 'pjp.item'
    _description = 'PJP Item'
    _order = 'date asc, sequence asc'

    name = fields.Char(
        string='PJP Item Name', compute='_compute_name', store=True, readonly=False)
    pjp_id = fields.Many2one(
        'pjp.model', string='PJP', required=True, ondelete='cascade', index=True)
    employee_id = fields.Many2one(
        related='pjp_id.employee_id', string='Employee', store=True, readonly=True)
    assigned_beat_id = fields.Many2one('beat.module', string='Assigned Beat', required=True)
    approved_beat_id = fields.Many2one('beat.module', string='Approved Beat')
    date = fields.Date(string='Date', required=True, index=True)
    sequence = fields.Integer(string='Sequence', default=10)
    status = fields.Selection([
        ('draft', 'Draft'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True)
    notes = fields.Text(string='Notes')
    created_date = fields.Datetime(
        string='Created Date', default=fields.Datetime.now, readonly=True)

    @api.depends('assigned_beat_id', 'date')
    def _compute_name(self):
        for record in self:
            record.name = record.assigned_beat_id.name if record.assigned_beat_id else 'New PJP Item'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') and vals.get('assigned_beat_id'):
                beat = self.env['beat.module'].browse(vals['assigned_beat_id'])
                vals['name'] = beat.name
        return super().create(vals_list)

    def action_approve(self):
        self.write({'status': 'approved', 'approved_beat_id': self.assigned_beat_id.id})

    def action_complete(self):
        self.write({'status': 'completed'})

    def action_cancel(self):
        self.write({'status': 'cancelled'})
