# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — Visit Model
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class VisitModel(models.Model):
    _name = 'visit.model'
    _description = 'Customer Visit'
    _order = 'actual_start_time desc'
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Visit ID', required=True, copy=False, readonly=True, default='New')
    employee_id = fields.Many2one(
        'hr.employee', string='Employee', required=True, ondelete='cascade', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    beat_id = fields.Many2one('beat.module', string='Beat')
    beat_line_id = fields.Many2one('beat.line', string='Beat Line')

    planned_start_time = fields.Datetime(string='Planned Start Time')
    actual_start_time = fields.Datetime(string='Actual Start Time')
    planned_end_time = fields.Datetime(string='Planned End Time')
    actual_end_time = fields.Datetime(string='Actual End Time')

    visit_for = fields.Selection([
        ('Primary Customer', 'Primary Customer'),
        ('Secondary Customer', 'Secondary Customer'),
        ('Prospect', 'Prospect'),
    ], string='Visit For', default='Secondary Customer')

    today_work_plan = fields.Selection([
        ('Customer Visit', 'Customer Visit'),
        ('Conference', 'Conference'),
        ('Training', 'Training'),
        ('Seminar', 'Seminar'),
        ('Enter Odometer Reading', 'Enter Odometer Reading'),
    ], string="Today's Work Plan")

    travel_type = fields.Selection([
        ('Headquarters', 'Headquarters'),
        ('Up country', 'Up country'),
        ('Other', 'Other'),
    ], string='Travel Type')

    vehicle_used = fields.Selection([
        ('Personal/own', 'Personal/own'),
        ('Office', 'Office'),
        ('Public transport', 'Public transport'),
    ], string='Vehicle Used')

    status = fields.Selection([
        ('planned', 'Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='planned', required=True, tracking=True)

    is_productive = fields.Boolean(string='Is Productive', default=True)
    productivity_reason = fields.Text(string='Non-Productive Reason')
    visit_comments = fields.Text(string='Visit Comments')
    store_image = fields.Binary(string='Store Image', attachment=True)
    store_image_filename = fields.Char(string='Store Image Filename')

    duration = fields.Float(
        string='Duration (Hours)', compute='_compute_duration', store=True)
    duration_display = fields.Char(
        string='Duration', compute='_compute_duration_display')

    order_ids = fields.One2many('sale.order', 'visit_id', string='Orders')
    order_line_ids = fields.One2many('sale.order.line', 'visit_id', string='Order Lines')
    order_count = fields.Integer(
        string='Order Count', compute='_compute_order_count', store=True)
    total_order_amount = fields.Monetary(
        string='Total Order Amount', compute='_compute_total_order_amount',
        store=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)

    stock_ledger_ids = fields.One2many('visit.stock.ledger', 'visit_id', string='Stock Updates')
    collection_ids = fields.One2many('visit.collection', 'visit_id', string='Collections')
    ticket_ids = fields.One2many('visit.ticket', 'visit_id', string='Tickets')
    competitor_ids = fields.One2many('visit.competitor', 'visit_id', string='Competitor Info')
    checklist_ids = fields.One2many('visit.checklist', 'visit_id', string='Checklist')

    geofence_valid = fields.Boolean(string='Geo-fence Validated', default=False)
    geofence_distance = fields.Float(string='Distance from Store (m)', digits=(10, 1))

    checkin_latitude = fields.Float(string='Check-in Latitude', digits=(10, 7))
    checkin_longitude = fields.Float(string='Check-in Longitude', digits=(10, 7))
    checkin_accuracy = fields.Float(string='Check-in Accuracy (m)', digits=(10, 2))
    checkout_latitude = fields.Float(string='Check-out Latitude', digits=(10, 7))
    checkout_longitude = fields.Float(string='Check-out Longitude', digits=(10, 7))

    total_collected = fields.Monetary(
        string='Total Collected', compute='_compute_totals', store=True,
        currency_field='currency_id')
    stock_lines_count = fields.Integer(
        string='Stock Lines', compute='_compute_totals', store=True)
    checklist_done = fields.Integer(
        string='Checklist Done', compute='_compute_totals', store=True)
    checklist_total = fields.Integer(
        string='Checklist Total', compute='_compute_totals', store=True)

    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)

    @api.depends(
        'collection_ids', 'collection_ids.amount', 'collection_ids.state',
        'stock_ledger_ids', 'checklist_ids', 'checklist_ids.answer')
    def _compute_totals(self):
        for rec in self:
            confirmed = rec.collection_ids.filtered(lambda c: c.state == 'confirmed')
            rec.total_collected = sum(confirmed.mapped('amount'))
            rec.stock_lines_count = len(rec.stock_ledger_ids)
            rec.checklist_done = len(rec.checklist_ids.filtered(lambda c: c.answer))
            rec.checklist_total = len(rec.checklist_ids)

    @api.constrains('employee_id', 'actual_start_time', 'actual_end_time', 'status')
    def _check_no_multiple_open_visits(self):
        for rec in self:
            if rec.status == 'in_progress':
                open_visits = self.search([
                    ('id', '!=', rec.id),
                    ('employee_id', '=', rec.employee_id.id),
                    ('status', '=', 'in_progress'),
                    ('actual_end_time', '=', False),
                ])
                if open_visits:
                    raise ValidationError(
                        _('Employee %s already has an open visit (%s). '
                          'Please close it before starting a new one.')
                        % (rec.employee_id.name, open_visits[0].name)
                    )

    @api.constrains('status', 'store_image')
    def _check_store_image_required(self):
        # Skip check if context flag is set (mobile flow)
        if self.env.context.get('skip_store_image_check'):
            return
        for record in self:
            if record.status == 'completed' and not record.store_image:
                raise ValidationError(
                    _('A Store Image is required to mark a visit as Completed.')
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('visit.model') or 'New'
        records = super().create(vals_list)
        for record in records:
            if record.status == 'completed':
                record._trigger_kpi_recompute()
        return records

    def write(self, vals):
        result = super().write(vals)
        if vals.get('status') == 'completed':
            self._trigger_kpi_recompute()
        return result

    def _trigger_kpi_recompute(self):
        """Invalidate stored KPI actuals so they get recomputed."""
        if 'kpi.target' not in self.env:
            return
        for record in self:
            if not record.employee_id:
                continue
            kpi_targets = self.env['kpi.target'].sudo().search([
                ('employee_id', '=', record.employee_id.id),
            ])
            if kpi_targets:
                kpi_targets._compute_actuals()
                kpi_targets._compute_achievements()

    @api.depends('actual_start_time', 'actual_end_time')
    def _compute_duration(self):
        for record in self:
            if record.actual_start_time and record.actual_end_time:
                delta = record.actual_end_time - record.actual_start_time
                record.duration = delta.total_seconds() / 3600.0
            else:
                record.duration = 0.0

    @api.depends('duration')
    def _compute_duration_display(self):
        for record in self:
            if record.duration:
                hours = int(record.duration)
                minutes = int((record.duration - hours) * 60)
                record.duration_display = f"{hours}h {minutes}m"
            else:
                record.duration_display = "0h 0m"

    @api.depends('order_ids')
    def _compute_order_count(self):
        for record in self:
            record.order_count = len(record.order_ids)

    @api.depends('order_ids', 'order_ids.amount_total', 'order_ids.state')
    def _compute_total_order_amount(self):
        for record in self:
            confirmed = record.order_ids.filtered(lambda o: o.state in ('sale', 'done'))
            record.total_order_amount = sum(confirmed.mapped('amount_total'))

    def action_view_orders(self):
        self.ensure_one()
        return {
            'name': _('Visit Orders'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'domain': [('visit_id', '=', self.id)],
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_visit_id': self.id,
                'default_user_id': self.employee_id.user_id.id,
            },
        }

    def action_create_order(self):
        self.ensure_one()
        return {
            'name': _('Create Order'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.partner_id.id,
                'default_visit_id': self.id,
                'default_user_id': self.employee_id.user_id.id,
            },
        }
