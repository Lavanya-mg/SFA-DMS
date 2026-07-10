from odoo import models, fields


class NewAccountWizard(models.TransientModel):
    _name        = 'new.account.wizard'
    _description = 'New Account — Select Record Type'

    account_record_type = fields.Selection([
        ('retailer',      'Retailer'),
        ('distributor',   'Distributor'),
        ('modern_trade',  'Modern Trade'),
        ('super_stockist','Super Stockist'),
    ], string='Account Record Type', default='retailer', required=True)

    def action_next(self):
        type_label = dict(self._fields['account_record_type'].selection)[self.account_record_type]
        return {
            'type': 'ir.actions.act_window',
            'name': f'New {type_label} Account',
            'res_model': 'fmcg.account',
            'view_mode': 'form',
            'view_id': self.env.ref('employee_dashboard_v19.view_fmcg_account_form').id,
            'target': 'current',
            'context': {'default_account_record_type': self.account_record_type},
        }
