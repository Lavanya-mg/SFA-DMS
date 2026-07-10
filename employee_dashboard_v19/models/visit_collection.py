# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — Visit Collection
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class VisitCollection(models.Model):
    _name = 'visit.collection'
    _description = 'Visit Collection'
    _order = 'date desc, id'
    _rec_name = 'name'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True, default='New')
    visit_id = fields.Many2one(
        'visit.model', string='Visit', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        related='visit_id.partner_id', string='Customer', store=True, readonly=True)
    employee_id = fields.Many2one(
        related='visit_id.employee_id', string='Employee', store=True, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.today, required=True)
    amount = fields.Monetary(
        string='Amount', required=True, currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    payment_mode = fields.Selection([
        ('Cash', 'Cash'),
        ('UPI', 'UPI'),
        ('Cheque', 'Cheque'),
        ('NEFT', 'NEFT/RTGS'),
    ], string='Payment Mode', required=True, default='Cash')
    reference = fields.Char(string='Reference / Cheque No.')
    remarks = fields.Text(string='Remarks')

    # Invoice Allocation
    invoice_id = fields.Many2one(
        'account.move', string='Invoice',
        domain="[('partner_id','=',partner_id),('move_type','=','out_invoice'),('payment_state','not in',('paid','reversed')),('state','=','posted')]")
    receipt_number = fields.Char(string='Receipt Number')
    is_on_account = fields.Boolean(string='Is On Account', default=False)
    allocation_type = fields.Selection([
        ('against_invoice', 'Against Invoice'),
        ('on_account', 'On Account'),
    ], string='Allocation Type', default='against_invoice')

    # Payment Details
    cheque_number = fields.Char(string='Cheque Number')
    cheque_date = fields.Date(string='Cheque Date')
    upi_reference = fields.Char(string='UPI Reference')
    transaction_reference = fields.Char(string='Transaction Reference')
    bank_name = fields.Char(string='Bank Name')

    # Assignment
    salesperson_id = fields.Many2one(
        'res.users', string='Salesperson',
        default=lambda self: self.env.user)
    collected_by_id = fields.Many2one(
        'res.users', string='Collected By',
        default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', required=True)
    payment_id = fields.Many2one('account.payment', string='Payment', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('visit.collection') or 'New'
        return super().create(vals_list)

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_("Collection amount must be greater than zero."))

    def action_confirm(self):
        env_nt = self.env(context=dict(self.env.context, lang=False))
        for rec in self:
            if rec.state != 'draft':
                continue
            try:
                partner_id = rec.visit_id.partner_id.id if rec.visit_id else False
                if not partner_id:
                    raise UserError(_("Customer is required to confirm collection."))

                journal = self._get_payment_journal(rec.payment_mode)
                if not journal:
                    rec.write({'state': 'confirmed'})
                    continue

                currency_id = (rec.currency_id.id if rec.currency_id
                               else env_nt['res.currency'].sudo().search(
                                   [('name', '=', 'INR')], limit=1).id or 1)

                ref_value = rec.reference or rec.name
                payment_vals = {
                    'partner_id': partner_id,
                    'partner_type': 'customer',
                    'payment_type': 'inbound',
                    'amount': rec.amount,
                    'currency_id': currency_id,
                    'journal_id': journal.id,
                    'date': rec.date,
                }
                # Odoo 17+ uses 'memo'; older versions use 'ref'
                # Use _fields (in-memory field registry) — more reliable than fields_get()
                payment_model_cls = env_nt['account.payment'].sudo()
                if 'memo' in payment_model_cls._fields:
                    payment_vals['memo'] = ref_value
                else:
                    payment_vals['ref'] = ref_value
                if (hasattr(journal, 'inbound_payment_method_line_ids')
                        and journal.inbound_payment_method_line_ids):
                    payment_vals['payment_method_line_id'] = (
                        journal.inbound_payment_method_line_ids[0].id)

                try:
                    payment = env_nt['account.payment'].sudo().create([payment_vals])
                except Exception:
                    # Flip memo↔ref and retry once
                    if 'memo' in payment_vals:
                        payment_vals['ref'] = payment_vals.pop('memo')
                    elif 'ref' in payment_vals:
                        payment_vals['memo'] = payment_vals.pop('ref')
                    payment = env_nt['account.payment'].sudo().create([payment_vals])
                payment.sudo().action_post()
                rec.write({'state': 'confirmed', 'payment_id': payment.id})
            except Exception as e:
                _logger.error("Error confirming collection %s: %s", rec.id, e, exc_info=True)
                raise UserError(_("Failed to confirm collection: %s") % str(e))

    def action_cancel(self):
        for rec in self:
            if rec.payment_id and rec.payment_id.state == 'posted':
                try:
                    rec.payment_id.action_cancel()
                except Exception:
                    pass
            rec.write({'state': 'cancelled'})

    def _get_payment_journal(self, payment_mode):
        mode_map = {'Cash': 'cash', 'UPI': 'bank', 'Cheque': 'bank', 'NEFT': 'bank'}
        return self.env['account.journal'].sudo().search([
            ('type', '=', mode_map.get(payment_mode, 'bank')),
            ('company_id', '=', self.env.company.id),
        ], limit=1)

    @api.model
    def get_customer_outstanding(self, partner_id):
        env_nt = self.env(context=dict(self.env.context, lang=False))
        partner = env_nt['res.partner'].sudo().browse(partner_id)
        if not partner.exists():
            return {'total': 0, 'credit_limit': 0, 'overdue': 0, 'last_payment': None}

        from datetime import date as d_date
        invoices = env_nt['account.move'].sudo().search([
            ('partner_id', '=', partner_id),
            ('move_type', '=', 'out_invoice'),
            ('payment_state', 'not in', ('paid', 'reversed')),
            ('state', '=', 'posted'),
        ])
        total_outstanding = sum(invoices.mapped('amount_residual'))
        today = d_date.today()
        overdue = sum(
            inv.amount_residual for inv in invoices
            if inv.invoice_date_due and inv.invoice_date_due < today
        )
        credit_limit = partner.credit_limit if hasattr(partner, 'credit_limit') else 0.0
        last_payment = env_nt['account.payment'].sudo().search([
            ('partner_id', '=', partner_id),
            ('partner_type', '=', 'customer'),
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
        ], order='date desc', limit=1)
        return {
            'total': round(total_outstanding, 2),
            'credit_limit': round(credit_limit, 2),
            'overdue': round(overdue, 2),
            'last_payment': str(last_payment.date) if last_payment else None,
            'last_payment_amount': round(last_payment.amount, 2) if last_payment else 0,
        }
