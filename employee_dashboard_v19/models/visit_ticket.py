# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — Visit Ticket
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class VisitTicket(models.Model):
    _name = 'visit.ticket'
    _description = 'Visit Support Ticket'
    _order = 'date desc, id'
    _rec_name = 'name'

    name = fields.Char(
        string='Ticket ID', required=True, copy=False, readonly=True, default='New')
    visit_id = fields.Many2one(
        'visit.model', string='Visit', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        related='visit_id.partner_id', string='Customer', store=True, readonly=True)
    employee_id = fields.Many2one(
        related='visit_id.employee_id', string='Employee', store=True, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.today, required=True)
    subject = fields.Char(string='Subject', required=True)
    category = fields.Selection([
        ('Product Quality', 'Product Quality'),
        ('Delivery Issue', 'Delivery Issue'),
        ('Payment Issue', 'Payment Issue'),
        ('Scheme Issue', 'Scheme Issue'),
        ('Returns / Damage', 'Returns / Damage'),
        ('Other', 'Other'),
    ], string='Category', required=True, default='Product Quality')
    priority = fields.Selection([
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
        ('Critical', 'Critical'),
    ], string='Priority', required=True, default='Low')
    description = fields.Text(string='Description')
    image = fields.Binary(string='Attachment Image', attachment=True)
    image_filename = fields.Char(string='Image Filename')
    state = fields.Selection([
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ], string='Status', default='open', required=True)
    resolution_notes = fields.Text(string='Resolution Notes')
    resolved_date = fields.Date(string='Resolved Date')
    resolved_by = fields.Many2one('hr.employee', string='Resolved By')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('visit.ticket') or 'New'
        return super().create(vals_list)

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_resolve(self):
        self.write({
            'state': 'resolved',
            'resolved_date': fields.Date.today(),
            'resolved_by': (self.env.user.employee_id.id
                            if self.env.user.employee_id else False),
        })

    def action_close(self):
        self.write({'state': 'closed'})

    def action_reopen(self):
        self.write({'state': 'open'})
