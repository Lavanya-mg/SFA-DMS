# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — HR Attendance extension
from odoo import api, models, fields, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    checkin_latitude = fields.Float(string='Check-in Latitude', digits=(10, 7))
    checkin_longitude = fields.Float(string='Check-in Longitude', digits=(10, 7))
    checkin_accuracy = fields.Float(string='Check-in Accuracy (m)', digits=(10, 2))
    checkin_full_address = fields.Char(string='Check-in Address')
    checkin_city = fields.Char(string='Check-in City')
    checkin_state = fields.Char(string='Check-in State')
    checkin_country = fields.Char(string='Check-in Country')

    checkout_latitude = fields.Float(string='Check-out Latitude', digits=(10, 7))
    checkout_longitude = fields.Float(string='Check-out Longitude', digits=(10, 7))
    checkout_accuracy = fields.Float(string='Check-out Accuracy (m)', digits=(10, 2))
    checkout_full_address = fields.Char(string='Check-out Address')
    checkout_city = fields.Char(string='Check-out City')
    checkout_state = fields.Char(string='Check-out State')
    checkout_country = fields.Char(string='Check-out Country')

    def action_view_checkin_location(self):
        """View check-in location on Google Maps"""
        self.ensure_one()
        if not self.checkin_latitude or not self.checkin_longitude:
            raise UserError(_('No check-in location available'))
        url = f'https://www.google.com/maps?q={self.checkin_latitude},{self.checkin_longitude}&z=18'
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_view_checkout_location(self):
        """View check-out location on Google Maps"""
        self.ensure_one()
        if not self.checkout_latitude or not self.checkout_longitude:
            raise UserError(_('No check-out location available'))
        url = f'https://www.google.com/maps?q={self.checkout_latitude},{self.checkout_longitude}&z=18'
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    @api.model
    def reverse_geocode_location(self, latitude, longitude):
        """Reverse geocode coordinates to address. geopy is optional —
        if not installed, geocoding is skipped gracefully."""
        try:
            from geopy.geocoders import Nominatim
        except ImportError:
            _logger.warning("geopy not installed — skipping reverse geocoding")
            return None
        try:
            geolocator = Nominatim(
                user_agent=f"odoo_attendance_{self.env.cr.dbname}",
                timeout=20
            )
            location = geolocator.reverse(
                f"{latitude},{longitude}",
                language='en',
                addressdetails=True,
                zoom=18
            )
            if not location:
                return None
            address = location.raw.get('address', {})
            city = (address.get('city') or
                    address.get('town') or
                    address.get('village') or
                    address.get('municipality') or '')
            state = address.get('state', '')
            country = address.get('country', '')
            address_parts = []
            if address.get('house_number'):
                address_parts.append(address.get('house_number'))
            if address.get('road'):
                address_parts.append(address.get('road'))
            if address.get('suburb'):
                address_parts.append(address.get('suburb'))
            if city:
                address_parts.append(city)
            if state:
                address_parts.append(state)
            if address.get('postcode'):
                address_parts.append(address.get('postcode'))
            if country:
                address_parts.append(country)
            full_address = ', '.join(filter(None, address_parts))
            return {
                'full_address': full_address or location.raw.get('display_name', ''),
                'city': city,
                'state': state,
                'country': country,
            }
        except Exception as e:
            _logger.error(f"Geocoding error: {str(e)}")
            return None

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to prevent automatic checkout"""
        if self.env.context.get('no_auto_checkout'):
            for vals in vals_list:
                if 'check_out' in vals:
                    del vals['check_out']
        return super(HrAttendance, self).create(vals_list)

    def write(self, vals):
        """Override write - allow manual checkout"""
        if 'check_out' in vals:
            if not (self.env.context.get('manual_checkout') or
                    self.env.context.get('force_write') or
                    self.env.context.get('tracking_disable')):
                _logger.warning(f"Blocked automatic checkout for attendance {self.ids}")
                vals = {k: v for k, v in vals.items() if k != 'check_out'}
        return super(HrAttendance, self).write(vals)

    @api.constrains('check_in', 'check_out')
    def _check_validity(self):
        """Override to allow manual checkouts"""
        if self.env.context.get('manual_checkout') or self.env.context.get('force_write'):
            return True
        return super(HrAttendance, self)._check_validity()
