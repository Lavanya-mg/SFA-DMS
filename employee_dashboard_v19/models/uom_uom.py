# -*- coding: utf-8 -*-# -*- coding: utf-8 -*-
from odoo import models, fields, api

class UomUom(models.Model):
    _inherit = 'uom.uom'

    # The actual field in the database
    x_uom_type = fields.Selection([
        ('count', 'Count'),
        ('weight', 'Weight'),
        ('volume', 'Volume'),
        ('length', 'Length'),
        ('packaging', 'Packaging'),
    ], string='UOM Type', default='count')
    
    # THE FIX: Create a computed field named 'uom_type' 
    # to stop the KeyError and redirect requests to x_uom_type
    uom_type = fields.Selection(
        selection=[
            ('count', 'Count'),
            ('weight', 'Weight'),
            ('volume', 'Volume'),
            ('length', 'Length'),
            ('packaging', 'Packaging'),
        ],
        string='Legacy UOM Type',
        compute='_compute_uom_type',
        inverse='_inverse_uom_type',
        store=False
    )
    

    @api.depends('x_uom_type')
    def _compute_uom_type(self):
        for rec in self:
            rec.uom_type = rec.x_uom_type

    def _inverse_uom_type(self):
        for rec in self:
            rec.x_uom_type = rec.uom_type