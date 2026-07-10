from odoo import models, fields

class ChannelMaster(models.Model):
    _name = 'channel.master'
    _description = 'Channel Master'
    name = fields.Char(string='Channel Name', required=True)

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    employee_code = fields.Char(string='Employee Code')
    # territory_id = fields.Many2one('territory.master', string='Territory')
    channel_ids = fields.Many2many('channel.master', 'hr_employee_channel_rel', 'employee_id', 'channel_id', string='Channels')

    work_days = fields.Many2many('day.master', 'emp_work_days_rel', 'emp_id', 'day_id', string="Working Days")
    week_off_days = fields.Many2many('day.master', 'emp_weekoff_days_rel', 'emp_id', 'day_id', string="Week Off Days")

# You also need a simple master model for the days
class DayMaster(models.Model):
    _name = 'day.master'
    _description = 'Day Master'
    name = fields.Char(string="Day")