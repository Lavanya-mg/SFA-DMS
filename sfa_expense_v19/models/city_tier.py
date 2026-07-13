# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


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

    # ── RPC API for the "City Tiers" tab of the Expense Policy Manager ──────────
    @api.model
    def get_city_tier_data(self):
        return {
            'rows': [{
                'id': c.id, 'city': c.city_name, 'state': c.state_id.name or '',
                'tier_id': c.tier_id.id or False, 'tier': c.tier_id.name or '',
                'active': c.active,
            } for c in self.with_context(active_test=False).search([])],
            'configs': [{'id': cf.id, 'name': cf.name}
                        for cf in self.env['sfa.city.tier.config'].search([('active', '=', True)])],
        }

    @api.model
    def save_city_tier(self, vals, tier_id=None):
        if not vals.get('city') or not vals.get('tier_id'):
            raise UserError(_("City Name and Tier are required."))
        writable = {
            'city_name': vals['city'],
            'tier_id': int(vals['tier_id']),
            'active': bool(vals.get('active', True)),
        }
        if tier_id:
            rec = self.browse(int(tier_id))
            rec.write(writable)
        else:
            rec = self.create(writable)
        return rec.id

    @api.model
    def delete_city_tier(self, tier_id):
        self.with_context(active_test=False).browse(int(tier_id)).unlink()
        return True
