# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — Asset Management
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AssetMaster(models.Model):
    _name = 'asset.master'
    _description = 'Asset Master'
    _order = 'name'

    name = fields.Char(string='Asset Name', required=True)
    asset_type = fields.Selection([
        ('freezer', 'Freezer / Visi-Cooler'),
        ('hoarding', 'Hoarding / Billboard'),
        ('vehicle', 'Vehicle / Transport'),
        ('display_stand', 'Display Stand'),
        ('posm', 'POSM / Signage'),
        ('other', 'Other'),
    ], string='Asset Type', required=True, default='other')
    code = fields.Char(string='Asset Code')
    description = fields.Text(string='Description')
    image = fields.Binary(string='Asset Image', attachment=True)
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')
    customer_count = fields.Integer(
        string='Assigned (Active)', compute='_compute_customer_count')

    def _compute_customer_count(self):
        for rec in self:
            rec.customer_count = self.env['customer.asset'].sudo().search_count([
                ('asset_master_id', '=', rec.id), ('state', '=', 'assigned')])

    def action_view_assigned(self):
        self.ensure_one()
        return {
            'name': _('Assigned: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'customer.asset',
            'view_mode': 'list,form',
            'domain': [('asset_master_id', '=', self.id), ('state', '=', 'assigned')],
            'context': {'default_asset_master_id': self.id},
        }


class CustomerAsset(models.Model):
    _name = 'customer.asset'
    _description = 'Customer Asset'
    _order = 'installation_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Asset ID', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True, index=True)
    asset_master_id = fields.Many2one('asset.master', string='Asset Type', required=True)
    asset_type = fields.Selection(
        related='asset_master_id.asset_type', string='Type', store=True)
    serial_number = fields.Char(string='Serial / Tag No.')
    installation_date = fields.Date(
        string='Installation Date', default=fields.Date.today, required=True)
    return_date = fields.Date(string='Return / Recovery Date')
    employee_id = fields.Many2one('hr.employee', string='Assigned By')
    visit_id = fields.Many2one('visit.model', string='Visit Reference', index=True)
    state = fields.Selection([
        ('assigned', 'Assigned'),
        ('returned', 'Returned'),
        ('damaged', 'Damaged'),
        ('lost', 'Lost'),
    ], string='Status', default='assigned', required=True)
    issue_ids = fields.One2many('asset.issue', 'customer_asset_id', string='Issues')
    issue_count = fields.Integer(
        string='Total Issues', compute='_compute_issue_count', store=True)
    open_issue_count = fields.Integer(
        string='Open Issues', compute='_compute_issue_count', store=True)
    notes = fields.Text(string='Notes')
    image = fields.Binary(string='Asset Photo', attachment=True)
    image_filename = fields.Char(string='Photo Filename')
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)

    @api.depends('issue_ids', 'issue_ids.state')
    def _compute_issue_count(self):
        for rec in self:
            rec.issue_count = len(rec.issue_ids)
            rec.open_issue_count = len(
                rec.issue_ids.filtered(lambda i: i.state in ('open', 'in_progress')))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('customer.asset') or 'New'
        return super().create(vals_list)

    def action_return(self):
        self.write({'state': 'returned', 'return_date': fields.Date.today()})

    def action_mark_damaged(self):
        self.write({'state': 'damaged'})

    def action_mark_lost(self):
        self.write({'state': 'lost'})

    def action_reassign(self):
        self.write({'state': 'assigned', 'return_date': False})

    def action_view_issues(self):
        self.ensure_one()
        return {
            'name': _('Asset Issues — %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'asset.issue',
            'view_mode': 'list,form',
            'domain': [('customer_asset_id', '=', self.id)],
            'context': {'default_customer_asset_id': self.id},
        }

    @api.model
    def get_assets_for_partner(self, partner_id):
        assets = self.sudo().search_read(
            [('partner_id', '=', partner_id)],
            ['id', 'name', 'asset_master_id', 'asset_type', 'serial_number',
             'installation_date', 'state', 'issue_count', 'open_issue_count', 'notes'],
            order='installation_date desc',
        )
        for asset in assets:
            if asset['asset_master_id']:
                asset['asset_master_name'] = asset['asset_master_id'][1]
                asset['asset_master_id'] = asset['asset_master_id'][0]
            asset['open_issues'] = self.env['asset.issue'].sudo().search_read(
                [('customer_asset_id', '=', asset['id']),
                 ('state', 'in', ['open', 'in_progress'])],
                ['id', 'name', 'subject', 'case_type', 'priority', 'state', 'date'],
                limit=10,
            )
        return assets

    def get_asset_masters(self):
        """Return all active asset types (used from JS frontend)."""
        return self.env['asset.master'].sudo().search_read(
            [('active', '=', True)],
            ['id', 'name', 'asset_type'],
            order='name asc',
        )


class AssetIssue(models.Model):
    _name = 'asset.issue'
    _description = 'Asset Issue'
    _order = 'date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Issue ID', required=True, copy=False, readonly=True, default='New')
    customer_asset_id = fields.Many2one(
        'customer.asset', string='Customer Asset', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        related='customer_asset_id.partner_id', string='Customer', store=True, readonly=True)
    asset_master_id = fields.Many2one(
        related='customer_asset_id.asset_master_id', string='Asset Type', store=True, readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Reported By')
    visit_id = fields.Many2one('visit.model', string='Visit Reference', index=True)
    date = fields.Date(string='Date', default=fields.Date.today, required=True)
    subject = fields.Char(string='Subject', required=True)
    case_type = fields.Selection([
        ('maintenance', 'Maintenance Required'),
        ('damage', 'Damage Reported'),
        ('missing', 'Asset Missing'),
        ('relocation', 'Relocation Request'),
        ('upgrade', 'Upgrade Request'),
        ('complaint', 'Customer Complaint'),
        ('other', 'Other'),
    ], string='Case Type', required=True, default='maintenance')
    priority = fields.Selection([
        ('Low', 'Low'), ('Medium', 'Medium'), ('High', 'High'), ('Critical', 'Critical'),
    ], string='Priority', required=True, default='Medium')
    description = fields.Text(string='Description')
    image = fields.Binary(string='Attachment Image', attachment=True)
    image_filename = fields.Char(string='Image Filename')
    state = fields.Selection([
        ('open', 'Open'), ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'), ('closed', 'Closed'),
    ], string='Status', default='open', required=True)
    resolution_notes = fields.Text(string='Resolution Notes')
    resolved_date = fields.Date(string='Resolved Date')
    resolved_by = fields.Many2one('hr.employee', string='Resolved By')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('asset.issue') or 'New'
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
