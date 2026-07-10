# -*- coding: utf-8 -*-
import calendar as cal
from odoo import models, fields, api


class SfaIncentiveRecord(models.Model):
    _name = 'sfa.incentive.record'
    _description = 'Incentive Calculation Record'
    _order = 'period_year desc, period_month desc, employee_id'

    employee_id = fields.Many2one('hr.employee', 'Salesperson', required=True, ondelete='cascade')
    period_month = fields.Integer('Month', required=True,
                                  default=lambda self: fields.Date.today().month)
    period_year = fields.Integer('Year', required=True,
                                 default=lambda self: fields.Date.today().year)
    period_display = fields.Char('Period', compute='_compute_period_display', store=True)

    criteria_id = fields.Many2one('sfa.target.criteria', 'Criteria')
    territory_id = fields.Many2one('fmcg.territory', 'Territory')
    profile_id = fields.Many2one('sfa.incentive.profile', 'Profile')

    target_value = fields.Float('Target Value', digits=(16, 2))
    actual_value = fields.Float('Actual Value', digits=(16, 2))
    achievement_percent = fields.Float('Achievement %', digits=(16, 2))

    slab_id = fields.Many2one('sfa.incentive.slab', 'Matched Slab')
    calculated_amount = fields.Float('Calculated Amount', digits=(16, 2))
    final_amount = fields.Float('Final Amount', digits=(16, 2))

    status = fields.Selection([
        ('calculated', 'Calculated'),
        ('pending_approval', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('paid', 'Paid'),
    ], string='Status', default='calculated', required=True)

    rejection_reason = fields.Text('Rejection Reason')
    payment_date = fields.Date('Payment Date')
    approved_by = fields.Many2one('res.users', 'Approved By', readonly=True)
    approved_date = fields.Date('Approval Date', readonly=True)

    @api.depends('period_month', 'period_year')
    def _compute_period_display(self):
        for rec in self:
            if rec.period_month and rec.period_year:
                rec.period_display = '%s %s' % (cal.month_abbr[rec.period_month], rec.period_year)
            else:
                rec.period_display = ''

    def action_submit_approval(self):
        self.write({'status': 'pending_approval'})

    def action_approve(self):
        self.write({
            'status': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Date.today(),
            'final_amount': self.calculated_amount,
        })

    def action_reject(self):
        self.write({'status': 'rejected'})

    def action_mark_paid(self):
        self.write({'status': 'paid', 'payment_date': fields.Date.today()})
