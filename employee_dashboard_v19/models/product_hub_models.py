# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProductBatch(models.Model):
    _name = 'product.batch'
    _description = 'Batch Master'
    _order = 'batch_number desc'

    batch_number = fields.Char(string='Batch #', required=True, copy=False, default='New')
    product_id = fields.Many2one('product.template', string='Product', required=True, index=True)
    mfg_date = fields.Date(string='MFG Date', required=True)
    expiry_date = fields.Date(string='Expiry Date', required=True)
    qty_manufactured = fields.Float(string='Qty Manufactured', default=0.0)
    shelf_life = fields.Integer(string='Shelf Life (Days)', compute='_compute_shelf_life', store=True)
    status = fields.Selection([
        ('active', 'Active'),
        ('near_expiry', 'Near Expiry'),
        ('expired', 'Expired'),
    ], string='Status', compute='_compute_status', store=True)
    near_expiry = fields.Boolean(string='Near Expiry', compute='_compute_status', store=True)
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    @api.depends('mfg_date', 'expiry_date')
    def _compute_shelf_life(self):
        for rec in self:
            if rec.mfg_date and rec.expiry_date:
                rec.shelf_life = (rec.expiry_date - rec.mfg_date).days
            else:
                rec.shelf_life = 0

    @api.depends('expiry_date')
    def _compute_status(self):
        today = fields.Date.today()
        for rec in self:
            if not rec.expiry_date:
                rec.status = 'active'
                rec.near_expiry = False
                continue
            days_left = (rec.expiry_date - today).days
            if days_left < 0:
                rec.status = 'expired'
                rec.near_expiry = False
            elif days_left <= 30:
                rec.status = 'near_expiry'
                rec.near_expiry = True
            else:
                rec.status = 'active'
                rec.near_expiry = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('batch_number', 'New') == 'New':
                vals['batch_number'] = self.env['ir.sequence'].next_by_code('product.batch') or 'New'
        return super().create(vals_list)

    @api.constrains('mfg_date', 'expiry_date')
    def _check_dates(self):
        for rec in self:
            if rec.mfg_date and rec.expiry_date and rec.mfg_date >= rec.expiry_date:
                raise ValidationError("Expiry Date must be after MFG Date.")


class PrioritySellConfig(models.Model):
    _name = 'priority.sell.config'
    _description = 'Priority Sell Configuration'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    product_id = fields.Many2one('product.template', string='Product', required=True, index=True)
    default_code = fields.Char(string='SKU', related='product_id.default_code', store=True)
    classification = fields.Selection([
        ('must_sell', 'Must Sell'),
        ('focused_sell', 'Focused Sell'),
    ], string='Classification', required=True, default='must_sell')
    channel = fields.Selection([
        ('all', 'All Channels'),
        ('general_trade', 'General Trade'),
        ('modern_trade', 'Modern Trade'),
        ('ecommerce', 'E-commerce'),
        ('horeca', 'HoReCa'),
    ], string='Channel', default='all')
    customer_type = fields.Char(string='Customer Type')
    territory = fields.Char(string='Territory')
    date_from = fields.Date(string='Start Date')
    date_to = fields.Date(string='End Date')
    min_qty = fields.Float(string='Min Qty', default=1.0)
    active = fields.Boolean(default=True)
    notes = fields.Text(string='Notes')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError("End Date must be after Start Date.")
            
    @api.model
    def get_must_sell_products(self):
        today = fields.Date.today()
        # Ensure this matches your model name for Priority Sell Config
        configs = self.env['priority.sell.config'].search([
            ('classification', '=', 'must_sell'),
            ('active', '=', True),
            '|', ('date_from', '=', False), ('date_from', '<=', today),
            '|', ('date_to', '=', False), ('date_to', '>=', today)
        ])
        
        return [{
            'id': c.id,
            # Find the specific product variant (product.product) for this template
            'product_id': self.env['product.product'].search([('product_tmpl_id', '=', c.product_id.id)], limit=1).id,
            'product_name': c.product_id.name,
            'min_qty': c.min_qty,
            'notes': c.notes or ''
        } for c in configs]
    
    @api.model
    def get_priority_sell_products(self, classification):
        today = fields.Date.today()
        configs = self.env['priority.sell.config'].search([
            ('classification', '=', classification),
            ('active', '=', True),
            '|', ('date_from', '=', False), ('date_from', '<=', today),
            '|', ('date_to', '=', False), ('date_to', '>=', today)
        ])
        
        return [{
            'id': c.id,
            'product_id': self.env['product.product'].search([('product_tmpl_id', '=', c.product_id.id)], limit=1).id,
            'product_name': c.product_id.name,
            'min_qty': c.min_qty,
            'notes': c.notes or ''
        } for c in configs]


class PriceChangeLog(models.Model):
    _name = 'price.change.log'
    _description = 'Price Change Log'
    _order = 'change_date desc'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.template', string='Product', required=True, index=True)
    default_code = fields.Char(string='SKU', related='product_id.default_code', store=True)
    price_book_id = fields.Many2one('price.book', string='Price Book Entry', ondelete='set null')
    price_type = fields.Selection([
        ('base', 'Base Price'),
        ('customer', 'Customer-wise'),
        ('category', 'Category-wise'),
        ('territory', 'Territory-wise'),
        ('channel', 'Channel-wise'),
        ('combination', 'Combination'),
    ], string='Price Type')
    old_price = fields.Float(string='Old Price', digits=(16, 4))
    new_price = fields.Float(string='New Price', digits=(16, 4))
    change_date = fields.Datetime(string='Changed On', default=fields.Datetime.now)
    changed_by = fields.Many2one('res.users', string='Changed By', default=lambda self: self.env.user)
    reason = fields.Char(string='Reason')
    customer_id = fields.Many2one('res.partner', string='Customer')
    territory = fields.Char(string='Territory')
    channel = fields.Selection([
        ('general_trade', 'General Trade'),
        ('modern_trade', 'Modern Trade'),
        ('ecommerce', 'E-commerce'),
        ('horeca', 'HoReCa'),
        ('institution', 'Institution'),
    ], string='Channel')


class EmployeeCategoryMapping(models.Model):
    _name = 'employee.category.mapping'
    _description = 'Employee Category Mapping'
    _order = 'employee_id, category_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    category_id = fields.Many2one('product.category', string='Category', required=True, index=True)
    level = fields.Selection([
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('tertiary', 'Tertiary'),
    ], string='Level', default='primary')
    responsibility = fields.Selection([
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
    ], string='Responsibility', default='primary')
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')
    active = fields.Boolean(default=True)
    assigned_by = fields.Many2one('res.users', string='Assigned By', default=lambda self: self.env.user)

    _sql_constraints = [
        ('unique_emp_cat', 'unique(employee_id, category_id)', 'An employee can only be mapped to each category once.'),
    ]


class CustomerCategoryMapping(models.Model):
    _name = 'customer.category.mapping'
    _description = 'Customer Category Mapping'
    _order = 'partner_id, category_id'

    partner_id = fields.Many2one('res.partner', string='Customer', required=True, index=True,
                                  domain="[('customer_rank', '>=', 1)]")
    category_id = fields.Many2one('product.category', string='Category', required=True, index=True)
    level = fields.Selection([
        ('primary', 'Primary'),
        ('secondary', 'Secondary'),
        ('tertiary', 'Tertiary'),
    ], string='Level', default='primary')
    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')
    active = fields.Boolean(default=True)
    assigned_by = fields.Many2one('res.users', string='Assigned By', default=lambda self: self.env.user)

    _sql_constraints = [
        ('unique_partner_cat', 'unique(partner_id, category_id)', 'A customer can only be mapped to each category once.'),
    ]


class PriceBookPriority(models.Model):
    _inherit = 'price.book.priority'

    has_customer = fields.Boolean(string='Customer', default=False,
                                   help="This priority rule uses customer dimension")
    has_category = fields.Boolean(string='Category', default=False,
                                   help="This priority rule uses category dimension")
    has_territory = fields.Boolean(string='Territory', default=False,
                                   help="This priority rule uses territory dimension")
    has_channel = fields.Boolean(string='Channel', default=False,
                                  help="This priority rule uses channel dimension")
    dimensions_display = fields.Char(string='Dimensions', compute='_compute_dimensions', store=True)

    @api.depends('has_customer', 'has_category', 'has_territory', 'has_channel', 'price_type')
    def _compute_dimensions(self):
        for rec in self:
            dims = []
            if rec.has_customer: dims.append('Customer')
            if rec.has_category: dims.append('Category')
            if rec.has_territory: dims.append('Territory')
            if rec.has_channel: dims.append('Channel')
            if dims:
                rec.dimensions_display = ' + '.join(dims)
            else:
                labels = dict(rec._fields['price_type'].selection)
                rec.dimensions_display = labels.get(rec.price_type, rec.price_type)
