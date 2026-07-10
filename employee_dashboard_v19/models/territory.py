from odoo import api, models, fields


class FmcgTerritory(models.Model):
    _name        = 'fmcg.territory'
    _description = 'Territory'
    _rec_name    = 'name'
    _order       = 'name asc'

    name   = fields.Char(string='Territory Name', required=True, index=True)
    code   = fields.Char(string='Territory Code', required=True, index=True)
    region = fields.Char(string='Region')
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    # Computed stats
    account_count = fields.Integer(
        string='Accounts', compute='_compute_account_count')
    beat_count = fields.Integer(
        string='Beats', compute='_compute_beat_count')
    employee_count = fields.Integer(
        string='Employees', compute='_compute_employee_count')

    _sql_constraints = [
        ('unique_code', 'unique(code)', 'Territory code must be unique!'),
    ]

    def _compute_account_count(self):
        for rec in self:
            try:
                rec.account_count = self.env['fmcg.account'].search_count(
                    [('territory_id', '=', rec.id)])
            except Exception:
                rec.account_count = 0

    def _compute_beat_count(self):
        for rec in self:
            try:
                rec.beat_count = self.env['beat.module'].search_count(
                    [('territory_id', '=', rec.id)])
            except Exception:
                rec.beat_count = 0

    def _compute_employee_count(self):
        for rec in self:
            try:
                rec.employee_count = self.env['hr.employee'].search_count(
                    [('territory_id', '=', rec.id)])
            except Exception:
                rec.employee_count = 0
