# -*- coding: utf-8 -*-
from odoo import models, fields


class SfaCityTierConfig(models.Model):
    """Configurable tier labels — client defines Metro/Tier1/Category A etc."""
    _name = 'sfa.city.tier.config'
    _description = 'City Tier Configuration'
    _order = 'sequence, name'
    _sql_constraints = [('unique_name', 'UNIQUE(name)', 'Tier label must be unique.')]

    name = fields.Char('Tier Label', required=True, help='e.g. Metro, Tier 1, Category A')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)


class SfaCityTier(models.Model):
    _name = 'sfa.city.tier'
    _description = 'City / Place Tier Master'
    _order = 'city_name'
    _rec_name = 'city_name'
    _sql_constraints = [('unique_city_state', 'UNIQUE(city_name, state_id)', 'City already exists for this state.')]

    city_name = fields.Char('City Name', required=True)
    state_id = fields.Many2one('res.country.state', string='State')
    tier_id = fields.Many2one('sfa.city.tier.config', string='Tier', required=True, ondelete='restrict')
    active = fields.Boolean(default=True)
