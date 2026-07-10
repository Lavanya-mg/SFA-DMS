# -*- coding: utf-8 -*-
import calendar as cal
import logging
from datetime import date as date_cls
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SfaExpenseManager(models.Model):
    """Lightweight monthly header — actual lines live in hr.expense."""
    _name = 'sfa.expense.manager'
    _description = 'SFA Expense Manager Header'
    _order = 'year desc, month desc'
    _rec_name = 'name'

    name = fields.Char('Reference', default='New', copy=False, readonly=True)
    employee_id = fields.Many2one('hr.employee', required=True,
        default=lambda self: self.env.user.employee_id)
    month = fields.Selection(
        [(str(i), cal.month_name[i]) for i in range(1, 13)],
        required=True,
        default=lambda s: str(fields.Date.today().month)
    )
    year = fields.Integer(required=True, default=lambda s: fields.Date.today().year)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='draft', copy=False)
    band_id = fields.Many2one('sfa.expense.band', string='Band')
    company_id = fields.Many2one('res.company', default=lambda s: s.env.company)

    total_eligible = fields.Float('Eligible', compute='_compute_totals')
    total_claimed = fields.Float('Claimed', compute='_compute_totals')
    total_approved = fields.Float('Approved', compute='_compute_totals')

    def _compute_totals(self):
        for rec in self:
            if not rec.month or not rec.year:
                rec.total_eligible = rec.total_claimed = rec.total_approved = 0
                continue
            df, dt = rec._month_range(int(rec.month), rec.year)
            expenses = self.env['hr.expense'].search([
                ('employee_id', '=', rec.employee_id.id),
                ('date', '>=', df),
                ('date', '<=', dt),
            ])
            rec.total_eligible = sum(e.eligible_amount or 0 for e in expenses)
            rec.total_claimed = sum(e.price_unit * (e.quantity or 1) for e in expenses)
            rec.total_approved = 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sfa.expense.manager') or 'New'
        return super().create(vals_list)

    # ── helpers ────────────────────────────────────────────────────────────────

    def _month_range(self, month, year):
        last_day = cal.monthrange(year, month)[1]
        return date_cls(year, month, 1), date_cls(year, month, last_day)

    def _get_employee(self, employee_id):
        if employee_id:
            return self.env['hr.employee'].browse(employee_id)
        return self.env.user.employee_id

    def _hr_expense_state(self, hr_state):
        """Map hr.expense state to our state."""
        return {
            'draft': 'draft',
            'reported': 'submitted',
            'approved': 'approved',
            'done': 'approved',
            'refused': 'rejected',
        }.get(hr_state, 'draft')

    def _get_expenses(self, employee_id, month, year):
        df, dt = self._month_range(month, year)
        return self.env['hr.expense'].search([
            ('employee_id', '=', employee_id),
            ('date', '>=', df),
            ('date', '<=', dt),
        ], order='date, id')

    # ── main UI method ─────────────────────────────────────────────────────────

    @api.model
    def get_expense_data(self, month, year, employee_id=False):
        employee = self._get_employee(employee_id)

        # Find or auto-create the header record
        header_rec = self.search([
            ('employee_id', '=', employee.id),
            ('month', '=', str(month)),
            ('year', '=', year),
        ], limit=1)
        if not header_rec:
            band = employee.band_id if hasattr(employee, 'band_id') and employee.band_id else False
            header_rec = self.create({
                'employee_id': employee.id,
                'month': str(month),
                'year': year,
                'band_id': band.id if band else False,
            })

        # Read hr.expense records for this employee + month
        expenses = self._get_expenses(employee.id, month, year)

        # Sync state from hr.expense if all submitted/approved
        if expenses and header_rec.state == 'draft':
            states = set(expenses.mapped('state'))
            if all(s in ('approved', 'done') for s in states):
                header_rec.state = 'approved'
            elif all(s in ('reported', 'approved', 'done') for s in states):
                header_rec.state = 'submitted'

        header = {
            'id': header_rec.id,
            'name': header_rec.name,
            'state': header_rec.state,
            'employee_name': employee.name or '',
            'band_code': header_rec.band_id.code if header_rec.band_id else '',
            'month': str(month),
            'year': year,
        }

        # Group expenses by date
        lines_by_date = {}
        for exp in expenses:
            if not exp.date:
                continue  # skip expenses without a date
            date_str = str(exp.date)
            if date_str not in lines_by_date:
                lines_by_date[date_str] = {
                    'date': date_str,
                    'date_display': exp.date.strftime('%a, %d/%m/%Y'),
                    'duty_type_code': exp.duty_type_id.code if exp.duty_type_id else '',
                    'location': '',
                    'hours': 0.0,
                    'total': 0.0,
                    'eligible': 0.0,
                    'lines': [],
                }
            entry = lines_by_date[date_str]
            # Use total_amount if available (it's the user-entered amount in Odoo 19)
            _total = getattr(exp, 'total_amount', 0) or 0
            amount = _total if _total else exp.price_unit * (exp.quantity or 1)
            entry['total'] += amount
            entry['eligible'] += exp.eligible_amount or 0
            entry['hours'] = max(entry['hours'], exp.hours or 0)
            editable = exp.state == 'draft'
            entry['lines'].append({
                'id': exp.id,
                'expense_type_id': exp.product_id.id if exp.product_id else False,
                'expense_type_name': exp.product_id.name if exp.product_id else (exp.name or ''),
                'rate_type': 'actual',
                'receipt_required': False,
                'remarks_required': False,
                'amount': amount,
                'eligible_amount': exp.eligible_amount or 0,
                'approved_amount': 0,
                'remarks': exp.name or '',
                'daily_km': exp.daily_km or 0,
                'system_km': exp.system_km or 0,
                'hours': exp.hours or 0,
                'hr_state': exp.state,
                'editable': editable,
            })

        # Stats
        def _amt(e):
            t = getattr(e, 'total_amount', 0) or 0
            return t if t else e.price_unit * (e.quantity or 1)
        stats = {
            'eligible': sum(exp.eligible_amount or 0 for exp in expenses),
            'claimed': sum(_amt(e) for e in expenses),
            'approved': 0,
            'days': len(lines_by_date),
            'distance': sum(exp.daily_km or 0 for exp in expenses),
        }

        # Expense types — standard Odoo Expense Categories
        expense_types = [{
            'id': p.id,
            'name': p.name,
            'code': p.default_code or '',
            'rate_type': 'actual',
            'receipt_required': False,
            'remarks_required': False,
            'system_km_enabled': False,
        } for p in self.env['product.product'].search([
            ('can_be_expensed', '=', True), ('active', '=', True)
        ])]

        duty_types = [{'id': d.id, 'name': d.name, 'code': d.code or ''} for d in self.env['sfa.duty.type'].search([])]
        travel_modes = [{'id': t.id, 'name': t.name, 'code': t.code or ''} for t in self.env['sfa.travel.mode'].search([])]

        # Overview — 12 months
        all_headers = self.search([('employee_id', '=', employee.id), ('year', '=', year)])
        hdr_by_month = {h.month: h for h in all_headers}
        overview = []
        for i in range(1, 13):
            h = hdr_by_month.get(str(i))
            df, dt = self._month_range(i, year)
            exps = self.env['hr.expense'].search([
                ('employee_id', '=', employee.id), ('date', '>=', df), ('date', '<=', dt),
            ])
            overview.append({
                'month_num': i,
                'month_name': cal.month_name[i],
                'state': h.state if h else ('draft' if exps else False),
                'claimed': sum(e.price_unit * e.quantity for e in exps),
                'approved': 0,
            })

        # Team
        team = []
        if employee.parent_id:
            subs = self.env['hr.employee'].search([('parent_id', '=', employee.parent_id.id)])
        else:
            subs = self.env['hr.employee'].search([('parent_id', '=', employee.id)])
        for sub in subs:
            sub_h = self.search([('employee_id', '=', sub.id), ('month', '=', str(month)), ('year', '=', year)], limit=1)
            sub_exps = self._get_expenses(sub.id, month, year)
            team.append({
                'employee_id': sub.id,
                'employee_name': sub.name,
                'band_code': sub_h.band_id.code if sub_h and sub_h.band_id else '',
                'state': sub_h.state if sub_h else ('draft' if sub_exps else False),
                'claimed': sum(e.price_unit * e.quantity for e in sub_exps),
                'approved': 0,
            })

        # Summary by type
        type_summary = {}
        for exp in expenses:
            key = exp.product_id.id if exp.product_id else 0
            if key not in type_summary:
                type_summary[key] = {
                    'type': key,
                    'type_name': exp.product_id.name if exp.product_id else 'Unknown',
                    'count': 0, 'eligible': 0, 'claimed': 0, 'approved': 0,
                }
            type_summary[key]['count'] += 1
            type_summary[key]['eligible'] += exp.eligible_amount or 0
            type_summary[key]['claimed'] += exp.price_unit * exp.quantity

        return {
            'header': header,
            'stats': stats,
            'expense_types': expense_types,
            'duty_types': duty_types,
            'travel_modes': travel_modes,
            'lines_by_date': lines_by_date,
            'overview': overview,
            'team': team,
            'summary_by_type': list(type_summary.values()),
            'period_label': f"{cal.month_name[month]} {year}",
        }

    @api.model
    def save_expense_line(self, vals):
        """Create or update an hr.expense record."""
        line_id = vals.pop('line_id', False)
        expense_type_id = vals.pop('expense_type_id', False)
        vals.pop('manager_id', False)

        HrExpense = self.env['hr.expense']

        if line_id:
            exp = HrExpense.browse(line_id)
            if not exp.exists():
                raise UserError(_('Expense record not found.'))
            if exp.state not in ('draft',):
                raise UserError(_('Cannot edit an expense that is in state "%s". Only draft expenses can be edited.') % exp.state)
            # Only write fields that were actually passed — never clear product/date
            update = {}
            if 'amount' in vals:
                amount_to_write = vals['amount']
                # In Odoo 19, total_amount is the user-facing stored field; price_unit may be computed
                # Try total_amount first; fall back to price_unit+quantity
                exp_fields = HrExpense._fields
                total_amount_field = exp_fields.get('total_amount')
                if total_amount_field and not total_amount_field.related:
                    update['total_amount'] = amount_to_write
                else:
                    update['price_unit'] = amount_to_write
                    update['quantity'] = 1
            if 'remarks' in vals:
                update['name'] = vals['remarks'] or exp.name
            if 'eligible_amount' in vals:
                update['eligible_amount'] = vals['eligible_amount']
            if 'daily_km' in vals:
                update['daily_km'] = vals['daily_km']
            if 'hours' in vals:
                update['hours'] = vals['hours']
            if expense_type_id:
                update['product_id'] = expense_type_id
            if update:
                _logger.info('SFA save_expense_line update id=%s: %s', exp.id, update)
                try:
                    exp.write(update)
                except Exception as e:
                    _logger.error('SFA save_expense_line write failed: %s', e)
                    raise UserError(_('Failed to save expense: %s') % str(e))
                _logger.info('SFA after write: price_unit=%s total_amount=%s', exp.price_unit, getattr(exp, 'total_amount', 'n/a'))
        else:
            date_val = vals.get('date')
            amount = vals.get('amount', 0)
            remarks = vals.get('remarks', '')
            product = self.env['product.product'].browse(expense_type_id) if expense_type_id else False
            exp_name = remarks or (product.name if product else 'Expense')
            exp = HrExpense.create({
                'name': exp_name,
                'product_id': expense_type_id or False,
                'date': date_val,
                'employee_id': self.env.user.employee_id.id,
                'price_unit': amount,
                'quantity': 1,
                'eligible_amount': vals.get('eligible_amount', 0),
                'daily_km': vals.get('daily_km', 0),
                'hours': vals.get('hours', 0),
            })

        # Read back the authoritative amount — prefer total_amount if available and non-zero
        exp.invalidate_recordset(['price_unit', 'total_amount', 'quantity'])
        total_amt = getattr(exp, 'total_amount', 0) or 0
        price_amt = exp.price_unit * (exp.quantity or 1)
        amount_out = total_amt if total_amt else price_amt
        return {
            'id': exp.id,
            'expense_type_id': exp.product_id.id if exp.product_id else False,
            'expense_type_name': exp.product_id.name if exp.product_id else exp.name,
            'amount': amount_out,
            'eligible_amount': exp.eligible_amount or 0,
            'remarks': exp.name or '',
            'daily_km': exp.daily_km or 0,
            'system_km': exp.system_km or 0,
            'hours': exp.hours or 0,
        }

    @api.model
    def delete_expense_line(self, line_id):
        exp = self.env['hr.expense'].browse(line_id)
        if exp.state not in ('draft',):
            raise UserError(_('Cannot delete an expense that has been submitted.'))
        exp.unlink()
        return True

    @api.model
    def action_submit(self, month, year):
        """Mark the monthly expense header as submitted."""
        employee = self.env.user.employee_id
        if not employee:
            raise UserError(_('No employee linked to the current user. Please contact HR.'))

        df, dt = self._month_range(month, year)
        expenses = self.env['hr.expense'].search([
            ('employee_id', '=', employee.id),
            ('date', '>=', df),
            ('date', '<=', dt),
        ])
        if not expenses:
            raise UserError(_('No expenses found for this period.'))

        header = self.search([
            ('employee_id', '=', employee.id),
            ('month', '=', str(month)),
            ('year', '=', year),
        ], limit=1)
        if header:
            header.write({'state': 'submitted'})

        return {'state': 'submitted'}
