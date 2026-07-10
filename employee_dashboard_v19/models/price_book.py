# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class PriceBook(models.Model):
    _name = 'price.book'
    _description = 'Price Book'
    _order = 'sequence, id'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    price_type = fields.Selection([
        ('base', 'Base Price'),
        ('customer', 'Customer-wise'),
        ('category', 'Category-wise'),
        ('territory', 'Territory-wise'),
        ('channel', 'Channel-wise'),
        ('combination', 'Combination'),
    ], string='Price Type', required=True, default='base')

    product_id = fields.Many2one('product.product', string='Product')
    product_tmpl_id = fields.Many2one('product.template', string='Product Template')
    customer_id = fields.Many2one('res.partner', string='Customer',
                                   domain=[('customer_rank', '>=', 1)])
    category_id = fields.Many2one('product.category', string='Product Category')
    territory = fields.Char(string='Territory')
    channel = fields.Selection([
        ('general_trade', 'General Trade'),
        ('modern_trade', 'Modern Trade'),
        ('ecommerce', 'E-commerce'),
        ('horeca', 'HoReCa'),
        ('institution', 'Institution'),
    ], string='Channel')

    unit_price = fields.Float(string='Unit Price', digits=(16, 4), required=True)
    min_qty = fields.Float(string='Minimum Quantity', default=1.0)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')

    date_from = fields.Date(string='Effective From')
    date_to = fields.Date(string='Effective To')

    currency_id = fields.Many2one('res.currency', string='Currency',
                                   default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string='Company',
                                  default=lambda self: self.env.company)

    notes = fields.Text(string='Notes')

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError("Effective From date must be before Effective To date.")

    @api.constrains('price_type', 'customer_id', 'category_id', 'territory', 'channel')
    def _check_type_fields(self):
        for rec in self:
            if rec.price_type == 'customer' and not rec.customer_id:
                raise ValidationError("Customer-wise price requires a Customer.")
            if rec.price_type == 'category' and not rec.category_id:
                raise ValidationError("Category-wise price requires a Product Category.")
            if rec.price_type == 'territory' and not rec.territory:
                raise ValidationError("Territory-wise price requires a Territory.")
            if rec.price_type == 'channel' and not rec.channel:
                raise ValidationError("Channel-wise price requires a Channel.")


class PriceBookPriority(models.Model):
    _name = 'price.book.priority'
    _description = 'Price Book Priority Configuration'
    _order = 'sequence'

    sequence = fields.Integer(string='Priority', default=10)
    price_type = fields.Selection([
        ('customer', 'Customer-wise'),
        ('category', 'Category-wise'),
        ('territory', 'Territory-wise'),
        ('channel', 'Channel-wise'),
        ('combination', 'Combination'),
        ('base', 'Base Price'),
    ], string='Price Type', required=True)
    description = fields.Char(string='Description', compute='_compute_description', store=True)
    active = fields.Boolean(string='Active', default=True)

    @api.depends('price_type')
    def _compute_description(self):
        labels = dict(self._fields['price_type'].selection)
        for rec in self:
            rec.description = labels.get(rec.price_type, '')

    _sql_constraints = [
        ('unique_price_type', 'UNIQUE(price_type)', 'Each price type can only appear once in the priority list.'),
    ]
