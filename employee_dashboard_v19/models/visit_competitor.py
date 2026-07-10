# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — Visit Competitor Tracking
from odoo import models, fields, api


class CompetitorMaster(models.Model):
    _name = 'competitor.master'
    _description = 'Competitor Master'
    _order = 'name'

    name = fields.Char(string='Competitor Brand', required=True)
    code = fields.Char(string='Code')
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')


class VisitCompetitor(models.Model):
    _name = 'visit.competitor'
    _description = 'Visit Competitor Tracking'
    _order = 'visit_id desc, id'

    visit_id = fields.Many2one(
        'visit.model', string='Visit', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        related='visit_id.partner_id', string='Customer', store=True, readonly=True)
    employee_id = fields.Many2one(
        related='visit_id.employee_id', string='Employee', store=True, readonly=True)
    date = fields.Datetime(
        related='visit_id.actual_start_time', string='Date', store=True, readonly=True)
    competitor_id = fields.Many2one('competitor.master', string='Competitor Brand')
    brand_name = fields.Char(string='Brand Name (Manual)')
    product_name = fields.Char(string='Product / SKU')
    price = fields.Float(string='Competitor Price', digits=(12, 2))
    shelf_share_pct = fields.Float(string='Shelf Share %', digits=(5, 2))
    scheme_details = fields.Text(string='Scheme / Offer Details')
    remarks = fields.Text(string='Remarks')
    photo = fields.Binary(string='Photo', attachment=True)
    photo_filename = fields.Char(string='Photo Filename')

    @api.onchange('competitor_id')
    def _onchange_competitor_id(self):
        if self.competitor_id and not self.brand_name:
            self.brand_name = self.competitor_id.name
