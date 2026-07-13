# -*- coding: utf-8 -*-
from odoo import models, fields


class SfaHrExpense(models.Model):
    """Extend hr.expense with SFA-specific fields."""
    _inherit = 'hr.expense'

    eligible_amount = fields.Float('Eligible Amount', digits=(16, 2))
    daily_km = fields.Float('Daily KM', digits=(16, 2))
    system_km = fields.Float('System KM', digits=(16, 2), readonly=True)
    km_deviation_reason = fields.Char('KM Deviation Reason',
        help="Required when Daily KM differs from the system-computed KM.")
    hours = fields.Float('Hours', digits=(16, 2))
    duty_type_id = fields.Many2one('sfa.duty.type', string='Duty Type')
    travel_mode_id = fields.Many2one('sfa.travel.mode', string='Travel Mode')
    from_location = fields.Char('From')
    to_location = fields.Char('To')
    city_tier_id = fields.Many2one('sfa.city.tier', string='City',
        help="City selected on a Lodging expense line; its tier drives the eligible cap.")
    sfa_month = fields.Char('SFA Month', help="MM of the expense manager this belongs to")
    sfa_year = fields.Integer('SFA Year', help="Year of the expense manager this belongs to")
