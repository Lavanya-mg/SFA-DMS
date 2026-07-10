from odoo import models, fields, api

class FmcgHoliday(models.Model):
    _name = 'fmcg.holiday'
    _description = 'Holiday Calendar'
    _order = 'date asc'

    name = fields.Char(string='Holiday Name', required=True)
    date = fields.Date(string='Date', required=True)
    holiday_type = fields.Selection([
        ('national', 'National Holiday'),
        ('regional', 'Regional Holiday'),
        ('optional', 'Optional Holiday'),
        ('restricted', 'Restricted Holiday'),
        ('company', 'Company Holiday')
    ], string='Type', required=True)
    territory_id = fields.Many2one('fmcg.territory', string='Territory', help="Leave empty for all territories")
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    
