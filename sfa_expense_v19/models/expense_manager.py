# -*- coding: utf-8 -*-
import calendar as cal
import logging
import math
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

    # ── Phase 2 helpers: eligibility engine, system-KM, duty days ───────────────
    def _employee_band(self, employee):
        """Resolve the employee's expense band (if the field is present)."""
        if employee and 'band_id' in employee._fields and employee.band_id:
            return employee.band_id
        return self.env['sfa.expense.band']

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2):
        R = 6371.0  # km
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _day_bounds(self, day):
        ds = fields.Date.to_string(day)
        return ds + ' 00:00:00', ds + ' 23:59:59'

    def _compute_system_km(self, employee, day):
        """Sum of distances between the day's visit GPS points (Task 16)."""
        if not employee or not day or 'visit.model' not in self.env:
            return 0.0
        lo, hi = self._day_bounds(day)
        visits = self.env['visit.model'].search([
            ('employee_id', '=', employee.id),
            ('actual_start_time', '>=', lo), ('actual_start_time', '<=', hi),
        ], order='actual_start_time')
        pts = []
        for v in visits:
            if v.checkin_latitude and v.checkin_longitude:
                pts.append((v.checkin_latitude, v.checkin_longitude))
            if v.checkout_latitude and v.checkout_longitude:
                pts.append((v.checkout_latitude, v.checkout_longitude))
        total = sum(self._haversine_km(*pts[i - 1], *pts[i]) for i in range(1, len(pts)))
        return round(total, 2)

    @staticmethod
    def _map_travel_type(travel_type):
        """Map a visit's travel type to a duty tag (HQ / OS / EX-HQ)."""
        return {
            'Headquarters': ('HQ', 'Headquarters'),
            'Up country': ('OS', 'Outstation'),
            'Other': ('EX-HQ', 'Ex-HQ'),
        }.get(travel_type, ('', ''))

    @api.model
    def get_eligible_days(self, month, year, employee_id=False):
        """Days in the month that have a visit or attendance, with the duty tag
        from that day's visit (Task 21). The expense-line date picker uses this."""
        employee = self._get_employee(employee_id)
        if not employee:
            return []
        df, dt = self._month_range(int(month), year)
        lo = fields.Date.to_string(df) + ' 00:00:00'
        hi = fields.Date.to_string(dt) + ' 23:59:59'
        days = {}
        if 'visit.model' in self.env:
            for v in self.env['visit.model'].search([
                ('employee_id', '=', employee.id),
                ('actual_start_time', '>=', lo), ('actual_start_time', '<=', hi),
            ], order='actual_start_time'):
                if not v.actual_start_time:
                    continue
                d = fields.Datetime.context_timestamp(v, v.actual_start_time).date()
                ds = fields.Date.to_string(d)
                code, name = self._map_travel_type(v.travel_type)
                days.setdefault(ds, {'date': ds, 'duty_code': code, 'duty_name': name})
        for a in self.env['hr.attendance'].search([
            ('employee_id', '=', employee.id),
            ('check_in', '>=', lo), ('check_in', '<=', hi),
        ]):
            if not a.check_in:
                continue
            d = fields.Datetime.context_timestamp(a, a.check_in).date()
            ds = fields.Date.to_string(d)
            days.setdefault(ds, {'date': ds, 'duty_code': '', 'duty_name': ''})
        return sorted(days.values(), key=lambda x: x['date'])

    def _worked_hours_by_day(self, employee, month, year):
        """Sum of attendance worked-hours per day for the month (drives the day
        header hours and the Daily Allowance line's Hours field)."""
        if not employee:
            return {}
        df, dt = self._month_range(int(month), year)
        lo = fields.Date.to_string(df) + ' 00:00:00'
        hi = fields.Date.to_string(dt) + ' 23:59:59'
        res = {}
        for a in self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', lo), ('check_in', '<=', hi)]):
            if not a.check_in:
                continue
            d = fields.Datetime.context_timestamp(a, a.check_in).date()
            ds = fields.Date.to_string(d)
            res[ds] = res.get(ds, 0.0) + (a.worked_hours or 0.0)
        return res

    def _apply_policy(self, exp, vals):
        """Set system-KM + KM-deviation guard, then recompute the eligible amount
        from the matching policy rule so it is server-authoritative (Tasks 16 & 22)."""
        etype = self.env['sfa.expense.type'].search(
            [('product_id', '=', exp.product_id.id)], limit=1) if exp.product_id else False
        if not etype:
            return

        if 'km_deviation_reason' in vals:
            exp.km_deviation_reason = vals.get('km_deviation_reason') or False

        # System KM + deviation guard for distance-based expenses (Task 16).
        # System KM is stored for any Per-KM line; the reason is only *enforced*
        # for types with system_km_enabled (Mileage), so other lines aren't blocked
        # before the entry UI exposes a deviation-reason input.
        if etype.rate_type == 'per_km':
            sys_km = self._compute_system_km(exp.employee_id, exp.date)
            if sys_km:
                exp.system_km = sys_km
                if (etype.system_km_enabled
                        and abs((exp.daily_km or 0.0) - sys_km) > 0.01
                        and not exp.km_deviation_reason):
                    raise UserError(_(
                        "Daily KM (%(d).2f) differs from the system KM (%(s).2f). "
                        "Please enter a KM deviation reason.",
                        d=exp.daily_km or 0.0, s=sys_km))

        # Eligible amount from the policy rule (Task 22); override only when a rule matches
        band = self._employee_band(exp.employee_id)
        if not band:
            return
        rt = etype.rate_type
        qty = (exp.daily_km if rt == 'per_km'
               else exp.hours if rt == 'per_hour'
               else 1.0 if rt == 'per_day' else 0.0) or 0.0
        actual_amt = (exp.price_unit or 0.0) * (exp.quantity or 1)
        try:
            res = self.env['sfa.expense.policy.rule'].get_eligible_amount(
                band_id=band.id, expense_type_id=etype.id,
                duty_type_id=exp.duty_type_id.id or False,
                qty=qty, actual_amount=actual_amt,
                travel_mode_id=exp.travel_mode_id.id or False,
                date=exp.date)
            if res.get('rule_id'):
                exp.eligible_amount = res['eligible']
        except UserError:
            raise
        except Exception as e:
            _logger.warning('Eligibility recompute skipped for expense %s: %s', exp.id, e)

    # ── Auto-create expense lines from policy rules ─────────────────────────────
    def _ensure_type_product(self, etype):
        """Every expense line is an hr.expense, which needs a product. Link (or
        create) an expense product for each sfa.expense.type so the type/rule
        engine and the product-based hr.expense stay bridged."""
        if etype.product_id:
            return etype.product_id
        Product = self.env['product.product'].sudo()
        # Reuse an existing expense product with the same code/name (links the
        # Expense Manager to the Policy Manager type and avoids duplicates).
        product = Product.search([
            ('can_be_expensed', '=', True),
            '|', ('default_code', '=', etype.code), ('name', '=', etype.name),
        ], limit=1)
        if not product:
            try:
                product = Product.create({
                    'name': etype.name,
                    'default_code': etype.code,
                    'can_be_expensed': True,
                    'type': 'service',
                    'list_price': 0.0,
                })
            except Exception as e:
                _logger.warning('Could not create expense product for type %s: %s', etype.name, e)
                return self.env['product.product']
        etype.sudo().product_id = product.id
        return product

    def _autocreate_lines(self, employee, month, year):
        """For each eligible day, create the expense lines defined by the band's
        auto_create policy rules (idempotent — one line per day+type), with the
        eligible amount + receipt/remarks flags mapped from the rule."""
        band = self._employee_band(employee)
        if not band:
            return
        Rule = self.env['sfa.expense.policy.rule']
        auto_rules = Rule.search([
            ('active', '=', True), ('auto_create', '=', True), ('band_id', '=', band.id)])
        if not auto_rules:
            return
        Duty = self.env['sfa.duty.type']
        HrExpense = self.env['hr.expense']
        # product id -> expense-type id, to detect an existing line *by type*
        product_to_type = {
            t.product_id.id: t.id
            for t in self.env['sfa.expense.type'].with_context(active_test=False).search(
                [('product_id', '!=', False)])
        }
        for ed in self.get_eligible_days(month, year, employee.id):
            day = fields.Date.to_date(ed['date'])
            duty = Duty.search([('code', '=', ed['duty_code'])], limit=1) if ed.get('duty_code') else Duty
            # types that already have a line on this day (mapped via product or name)
            day_exps = HrExpense.search([('employee_id', '=', employee.id), ('date', '=', day)])
            existing_type_ids = {product_to_type.get(e.product_id.id) for e in day_exps if e.product_id}
            existing_names = {(e.product_id.name or e.name) for e in day_exps}
            for rule in auto_rules:
                if rule.duty_type_id and duty and rule.duty_type_id.id != duty.id:
                    continue
                etype = rule.expense_type_id
                if etype.id in existing_type_ids or etype.name in existing_names:
                    continue  # a line of this type already exists for the day
                product = self._ensure_type_product(etype)
                if not product:
                    continue
                system_km = self._compute_system_km(employee, day) if etype.system_km_enabled else 0.0
                qty = (1.0 if rule.rate_type == 'per_day'
                       else system_km if rule.rate_type == 'per_km' else 0.0)
                eligible = rule.compute_eligible_amount(qty=qty)
                HrExpense.create({
                    'name': etype.name,
                    'product_id': product.id,
                    'date': day,
                    'employee_id': employee.id,
                    'price_unit': 0.0, 'quantity': 1,
                    'eligible_amount': eligible,
                    'system_km': system_km,
                    'duty_type_id': duty.id if duty else False,
                })
                existing_type_ids.add(etype.id)
                existing_names.add(etype.name)

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

        # Auto-create lines from auto_create policy rules for each eligible day
        # (draft sheets only; idempotent).
        if header_rec.state == 'draft':
            try:
                self._autocreate_lines(employee, month, year)
            except Exception as e:
                _logger.warning('Auto-create expense lines skipped: %s', e)

        # Read hr.expense records for this employee + month
        expenses = self._get_expenses(employee.id, month, year)

        # Map each expense product back to its sfa.expense.type + policy rule so
        # rate_type / receipt / remarks / eligible reflect the configured policy.
        band = self._employee_band(employee)
        type_by_product = {
            t.product_id.id: t
            for t in self.env['sfa.expense.type'].with_context(active_test=False).search(
                [('product_id', '!=', False)])
        }
        Rule = self.env['sfa.expense.policy.rule']

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

        # Batch receipt-attachment counts (one query for the whole month)
        att_by_expense = {}
        if expenses:
            for a in self.env['ir.attachment'].search([
                ('res_model', '=', 'hr.expense'), ('res_id', 'in', expenses.ids)]):
                att_by_expense[a.res_id] = att_by_expense.get(a.res_id, 0) + 1

        # Attendance worked-hours per day (for the day header + Daily Allowance)
        hours_by_day = self._worked_hours_by_day(employee, month, year)

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
                    'hours': hours_by_day.get(date_str, 0.0),
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
            etype = type_by_product.get(exp.product_id.id) if exp.product_id else False
            rule = Rule._resolve_rule(band.id, etype.id, exp.duty_type_id.id or False, exp.date) \
                if (band and etype) else False
            # nature drives the card layout (basic / daily / travelling / lodging)
            if etype:
                nature = etype._effective_nature() if hasattr(etype, '_effective_nature') else (etype.nature or 'misc')
            else:
                nature = 'misc'
            city = exp.city_tier_id if 'city_tier_id' in exp._fields else self.env['sfa.city.tier']
            entry['lines'].append({
                'id': exp.id,
                'expense_type_id': exp.product_id.id if exp.product_id else False,
                'expense_type_name': (etype.name if etype else (exp.product_id.name if exp.product_id else exp.name)) or '',
                'rate_type': etype.rate_type if etype else 'actual',
                'nature': nature,
                'receipt_required': rule.receipt_required if rule else (etype.receipt_required if etype else False),
                'remarks_required': rule.remarks_required if rule else (etype.remarks_required if etype else False),
                'has_receipt': att_by_expense.get(exp.id, 0) > 0,
                'amount': amount,
                'eligible_amount': exp.eligible_amount or 0,
                'approved_amount': 0,
                'remarks': exp.name or '',
                'daily_km': exp.daily_km or 0,
                'system_km': exp.system_km or 0,
                'from_location': exp.from_location or '',
                'to_location': exp.to_location or '',
                'travel_mode_id': exp.travel_mode_id.id or False,
                'allowed_modes': [{'id': m.id, 'name': m.name} for m in rule.travel_mode_ids] if rule else [],
                'city_tier_id': city.id or False,
                'city_name': city.city_name or '' if city else '',
                'city_tier_label': (city.tier_id.name or '') if city and city.tier_id else '',
                'hours': exp.hours or hours_by_day.get(date_str, 0.0),
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

        # Expense types — ONLY the types that have an active policy rule. Restrict
        # to the employee's band when set; otherwise show every rule-defined type
        # (so the dropdown isn't empty before a band is assigned).
        rule_domain = [('active', '=', True)]
        if band:
            rule_domain.append(('band_id', '=', band.id))
        allowed_type_ids = set(Rule.search(rule_domain).mapped('expense_type_id').ids)
        expense_types = []
        for t in self.env['sfa.expense.type'].search(
                [('active', '=', True), ('id', 'in', list(allowed_type_ids) or [0])],
                order='sequence, name'):
            product = self._ensure_type_product(t)
            if not product:
                continue
            expense_types.append({
                'id': product.id,
                'name': t.name,
                'code': t.code or '',
                'rate_type': t.rate_type,
                'receipt_required': t.receipt_required,
                'remarks_required': t.remarks_required,
                'system_km_enabled': t.system_km_enabled,
            })

        duty_types = [{'id': d.id, 'name': d.name, 'code': d.code or ''} for d in self.env['sfa.duty.type'].search([])]
        travel_modes = [{'id': t.id, 'name': t.name, 'code': t.code or ''} for t in self.env['sfa.travel.mode'].search([])]
        cities = [{
            'id': c.id, 'name': c.city_name,
            'tier': c.tier_id.name or '',
        } for c in self.env['sfa.city.tier'].search([], order='city_name')]

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
            'cities': cities,
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
            if 'from_location' in vals:
                update['from_location'] = vals['from_location'] or False
            if 'to_location' in vals:
                update['to_location'] = vals['to_location'] or False
            if 'travel_mode_id' in vals:
                update['travel_mode_id'] = vals['travel_mode_id'] or False
            if 'city_tier_id' in vals:
                update['city_tier_id'] = vals['city_tier_id'] or False
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

            # Policy guard: only expense types with a rule for the band are allowed.
            emp = self.env.user.employee_id
            band = self._employee_band(emp)
            etype = self.env['sfa.expense.type'].search(
                [('product_id', '=', product.id)], limit=1) if product else False
            if band and etype and not self.env['sfa.expense.policy.rule'].search([
                    ('active', '=', True), ('band_id', '=', band.id),
                    ('expense_type_id', '=', etype.id)], limit=1):
                raise UserError(_(
                    "'%(t)s' is not allowed by the expense policy for band %(b)s.",
                    t=etype.name, b=band.code or band.name))

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

        # Server-side eligibility + system-KM (Tasks 16 & 22)
        self._apply_policy(exp, vals)

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
            'km_deviation_reason': exp.km_deviation_reason or '',
            'hours': exp.hours or 0,
        }

    @api.model
    def upload_receipt(self, line_id, filename, datas):
        """Attach a receipt file (base64) to an expense line."""
        exp = self.env['hr.expense'].browse(line_id)
        if not exp.exists():
            raise UserError(_('Expense record not found.'))
        if exp.state not in ('draft',):
            raise UserError(_('Cannot attach a receipt to a submitted expense.'))
        self.env['ir.attachment'].create({
            'name': filename or 'receipt',
            'datas': datas,
            'res_model': 'hr.expense',
            'res_id': exp.id,
        })
        return True

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
