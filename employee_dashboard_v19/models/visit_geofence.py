# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — Geo-fence Configuration
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import math

_logger = logging.getLogger(__name__)


class GeoFenceConfig(models.Model):
    _name = 'geo.fence.config'
    _description = 'Geo-fence Configuration'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one(
        'res.partner', string='Customer', required=True, index=True, ondelete='cascade')
    latitude = fields.Float(string='Store Latitude', digits=(10, 7))
    longitude = fields.Float(string='Store Longitude', digits=(10, 7))
    radius_meters = fields.Float(string='Allowed Radius (m)', default=100.0)
    active = fields.Boolean(string='Active', default=True)
    notes = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_partner', 'UNIQUE(partner_id)', 'Each customer can have only one geo-fence config!')
    ]

    @api.constrains('radius_meters')
    def _check_radius(self):
        for rec in self:
            if rec.radius_meters < 10:
                raise ValidationError(_("Radius must be at least 10 meters."))

    @api.model
    def validate_checkin(self, partner_id, user_lat, user_lng):
        """Check if user coordinates are within the partner's geo-fence."""
        config = self.sudo().search([
            ('partner_id', '=', partner_id), ('active', '=', True)], limit=1)
        if not config or not config.latitude or not config.longitude:
            return {'valid': True, 'distance': 0, 'message': 'No geo-fence configured'}

        distance = self._haversine(
            user_lat, user_lng, config.latitude, config.longitude)
        valid = distance <= config.radius_meters
        return {
            'valid': valid,
            'distance': round(distance, 1),
            'radius': config.radius_meters,
            'message': (
                f'Within geo-fence ({distance:.0f}m)'
                if valid else
                f'Outside geo-fence ({distance:.0f}m, limit: {config.radius_meters:.0f}m)'
            ),
        }

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        R = 6371000  # Earth radius in metres
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = (math.sin(dphi / 2) ** 2
             + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
