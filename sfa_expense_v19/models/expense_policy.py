# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class SfaExpensePolicyRule(models.Model):
    """Eligibility rule: per band × expense-type × duty-type combination."""
    _name = 'sfa.expense.policy.rule'
    _description = 'Expense Policy Rule'
    _order = 'band_id, sequence, id'

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ── Parent policy (for compatibility with employee_dashboard_v19) ──────────
    # policy_id = fields.Many2one('sfa.expense.policy', string='Policy', ondelete='cascade')

    # ── Rule identity ──────────────────────────────────────────────────────────
    band_id = fields.Many2one('sfa.expense.band', string='Band', required=True, ondelete='cascade')
    expense_type_id = fields.Many2one('sfa.expense.type', string='Expense Type', required=True, ondelete='cascade')
    duty_type_id = fields.Many2one('sfa.duty.type', string='Duty Type',
                                   help="Leave empty to apply to all duty types")
    category = fields.Char('Category', help="e.g. Travel, Accommodation, Food")

    # ── Rate configuration ─────────────────────────────────────────────────────
    rate_type = fields.Selection([
        ('actual', 'Actual'),
        ('per_day', 'Per Day'),
        ('per_km', 'Per KM'),
        ('flat_monthly', 'Flat Monthly'),
        ('per_hour', 'Per Hour'),
    ], required=True, default='actual')
    rate = fields.Float('Rate', digits=(16, 2))

    # ── City tier limits ───────────────────────────────────────────────────────
    tier1_limit = fields.Float('Tier 1 Limit', digits=(16, 2))
    tier2_limit = fields.Float('Tier 2 Limit', digits=(16, 2))
    tier3_limit = fields.Float('Tier 3 Limit', digits=(16, 2))

    # ── Receipt settings ───────────────────────────────────────────────────────
    receipt_required = fields.Boolean('Receipt Required', default=False)
    receipt_threshold = fields.Float('Receipt Threshold', digits=(16, 2),
                                     help="Receipt required only above this amount (0 = always)")
    remarks_required = fields.Boolean('Remarks Required', default=False)

    # ── Travel modes (Travelling Allowance) ────────────────────────────────────
    travel_mode_ids = fields.Many2many('sfa.travel.mode', string='Travel Modes')
    travel_mode_count = fields.Integer('# Modes', compute='_compute_travel_mode_count', store=True)
    mode_rate_ids = fields.One2many('sfa.expense.policy.mode.rate', 'rule_id',
                                    string='Mode-wise Rates')
    min_distance = fields.Float('Min Distance (KM)', digits=(16, 2))
    max_distance = fields.Float('Max Distance (KM)', digits=(16, 2))

    # ── Options ────────────────────────────────────────────────────────────────
    auto_create = fields.Boolean('Auto Create', default=False,
                                 help="Auto-create this expense line for eligible days.")

    # Convenience for dynamic form visibility (Lodging / TA / Mobile ...)
    type_code = fields.Char(related='expense_type_id.code', store=True, readonly=True)
    type_nature = fields.Selection(related='expense_type_id.nature', store=True, readonly=True,
                                   string='Type Nature')

    @api.onchange('expense_type_id')
    def _onchange_expense_type_id(self):
        """Default the rate type from the chosen expense type so the form's
        rate-driven sections update as soon as the type is picked."""
        if self.expense_type_id and self.expense_type_id.rate_type:
            self.rate_type = self.expense_type_id.rate_type
            self.receipt_required = self.expense_type_id.receipt_required
            self.remarks_required = self.expense_type_id.remarks_required

    # ── Policy dates ───────────────────────────────────────────────────────────
    date_from = fields.Date('Valid From')
    date_to = fields.Date('Valid To')

    @api.depends('travel_mode_ids')
    def _compute_travel_mode_count(self):
        for rec in self:
            rec.travel_mode_count = len(rec.travel_mode_ids)

    def name_get(self):
        result = []
        for r in self:
            band = r.band_id.code or ''
            etype = r.expense_type_id.name or ''
            duty = r.duty_type_id.name if r.duty_type_id else 'ALL'
            result.append((r.id, f"{band} / {etype} / {duty}"))
        return result

    # ══════════════════════════════════════════════════════════════════════════
    #  Eligibility engine (Task 22): resolve the matching rule for a
    #  (band, expense type, duty type) and compute the eligible amount.
    # ══════════════════════════════════════════════════════════════════════════
    def _tier_limit_for(self, city_tier):
        """Map a city's tier onto this rule's Tier 1/2/3 limit (by tier-config order)."""
        self.ensure_one()
        if not city_tier or not city_tier.tier_id:
            return 0.0
        configs = self.env['sfa.city.tier.config'].search([('active', '=', True)], order='sequence, id')
        limits = [self.tier1_limit, self.tier2_limit, self.tier3_limit]
        try:
            idx = list(configs).index(city_tier.tier_id)
        except ValueError:
            return 0.0
        return limits[idx] if 0 <= idx < 3 else 0.0

    def _rate_for_mode(self, travel_mode_id):
        """Per-mode rate override (bike/car/auto …) falling back to the rule rate."""
        self.ensure_one()
        if travel_mode_id:
            mr = self.mode_rate_ids.filtered(lambda m: m.travel_mode_id.id == travel_mode_id)
            if mr:
                return mr[0].rate
        return self.rate

    def _mode_eligible(self, travel_mode_id, qty, actual_amount):
        """Per-KM eligibility for the chosen travel mode, honouring the mode's
        own rate type (Per KM vs Actual) and Max Amount cap."""
        self.ensure_one()
        mr = self.mode_rate_ids.filtered(
            lambda m: m.travel_mode_id.id == travel_mode_id)[:1] if travel_mode_id else False
        if mr and mr.rate_type == 'actual':
            elig = actual_amount
        else:
            rate = mr.rate if mr else self.rate
            elig = rate * (qty or 0.0)
        if mr and mr.max_amount and elig > mr.max_amount:
            elig = mr.max_amount
        return elig

    def compute_eligible_amount(self, qty=0.0, actual_amount=0.0,
                                city_tier_id=False, travel_mode_id=False):
        """Eligible amount for this rule.
        qty = days (per_day), km (per_km) or hours (per_hour)."""
        self.ensure_one()
        qty = qty or 0.0
        rt = self.rate_type
        if rt == 'actual':          # Fuel / Food / Misc-actual → no cap
            return actual_amount
        if rt == 'flat_monthly':    # Mobile → fixed monthly amount
            return self.rate
        if rt == 'per_hour':
            return self.rate * qty
        if rt == 'per_km':          # Travelling Allowance / Mileage
            return self._mode_eligible(travel_mode_id, qty, actual_amount)
        if rt == 'per_day':         # Daily Allowance / Lodging (tier-capped)
            per_day = self.rate
            if city_tier_id:
                tier = self.env['sfa.city.tier'].browse(city_tier_id)
                tier_amt = self._tier_limit_for(tier)
                if tier_amt:
                    per_day = tier_amt
            eligible = per_day * (qty or 1.0)
            # Lodging: reimburse actual up to the eligible cap.
            return min(actual_amount, eligible) if actual_amount else eligible
        return actual_amount

    @api.model
    def _resolve_rule(self, band_id, expense_type_id, duty_type_id=False, date=False):
        """Best-matching active rule: duty-specific wins over duty=ALL; date-valid."""
        if not band_id or not expense_type_id:
            return self.browse()
        date = date or fields.Date.today()
        rules = self.search([
            ('active', '=', True),
            ('band_id', '=', band_id),
            ('expense_type_id', '=', expense_type_id),
            '|', ('date_from', '=', False), ('date_from', '<=', date),
            '|', ('date_to', '=', False), ('date_to', '>=', date),
        ], order='sequence, id')
        if duty_type_id:
            specific = rules.filtered(lambda r: r.duty_type_id.id == duty_type_id)
            if specific:
                return specific[0]
        universal = rules.filtered(lambda r: not r.duty_type_id)
        if universal:
            return universal[0]
        return rules[0] if rules else self.browse()

    @api.model
    def get_eligible_amount(self, band_id, expense_type_id, duty_type_id=False,
                            qty=0.0, actual_amount=0.0, city_tier_id=False,
                            travel_mode_id=False, date=False):
        """RPC entry point (Task 22). Returns the eligible amount + the policy
        flags (receipt/remarks) resolved from the matching rule."""
        rule = self._resolve_rule(band_id, expense_type_id, duty_type_id, date)
        if not rule:
            # No rule → fall back to actual, no policy constraints.
            return {
                'eligible': actual_amount, 'rule_id': False, 'rate_type': 'actual',
                'rate': 0.0, 'receipt_required': False, 'receipt_threshold': 0.0,
                'remarks_required': False,
            }
        eligible = rule.compute_eligible_amount(
            qty=qty, actual_amount=actual_amount,
            city_tier_id=city_tier_id, travel_mode_id=travel_mode_id)
        return {
            'eligible': eligible,
            'rule_id': rule.id,
            'rate_type': rule.rate_type,
            'rate': rule.rate,
            'receipt_required': rule.receipt_required,
            'receipt_threshold': rule.receipt_threshold,
            'remarks_required': rule.remarks_required,
        }

    # ══════════════════════════════════════════════════════════════════════════
    #  RPC API for the Expense Policy Manager (OWL client action)
    # ══════════════════════════════════════════════════════════════════════════
    @api.model
    def get_policy_manager_data(self, band_id=None, type_id=None, duty_id=None):
        domain = []
        if band_id:
            domain.append(('band_id', '=', int(band_id)))
        if type_id:
            domain.append(('expense_type_id', '=', int(type_id)))
        if duty_id:
            domain.append(('duty_type_id', '=', int(duty_id)))
        rules = self.with_context(active_test=False).search(domain)
        rate_labels = dict(self._fields['rate_type'].selection)
        rows = [{
            'id': r.id,
            'band': r.band_id.code or r.band_id.name or '',
            'type': r.expense_type_id.name or '',
            'duty': (r.duty_type_id.code or r.duty_type_id.name) if r.duty_type_id else 'ALL',
            'rate_type_label': rate_labels.get(r.rate_type, ''),
            'rate': r.rate,
            'modes': r.travel_mode_count,
            'active': r.active,
        } for r in rules]
        return {
            'rows': rows,
            'bands': [{'id': b.id, 'name': b.code or b.name} for b in self.env['sfa.expense.band'].search([])],
            'types': [{'id': t.id, 'name': t.name} for t in self.env['sfa.expense.type'].search([])],
            'duty_types': [{'id': d.id, 'name': d.name} for d in self.env['sfa.duty.type'].search([])],
        }

    @api.model
    def get_rule_form_options(self):
        Mode = self.env['sfa.travel.mode']
        modes = Mode.search([('active', '=', True)])
        grouped = {}
        for m in modes:
            grouped.setdefault(m.mode_group or 'other', []).append({'id': m.id, 'name': m.name})
        group_labels = dict(Mode._fields['mode_group'].selection)
        return {
            'bands': [{'id': b.id, 'name': b.code or b.name} for b in self.env['sfa.expense.band'].search([])],
            'types': [{'id': t.id, 'name': t.name, 'nature': t._effective_nature(), 'rate_type': t.rate_type,
                       'receipt_required': t.receipt_required, 'remarks_required': t.remarks_required}
                      for t in self.env['sfa.expense.type'].search([])],
            'duty_types': [{'id': d.id, 'name': d.name} for d in self.env['sfa.duty.type'].search([])],
            'rate_types': [{'value': v, 'label': l} for v, l in self._fields['rate_type'].selection],
            'mode_groups': [{'key': g, 'label': group_labels.get(g, g), 'modes': grouped[g]}
                            for g in ('distance', 'bus', 'train', 'flight', 'other') if grouped.get(g)],
        }

    @api.model
    def get_rule_detail(self, rule_id):
        r = self.with_context(active_test=False).browse(int(rule_id))
        r.ensure_one()
        return {
            'id': r.id, 'band_id': r.band_id.id or False,
            'expense_type_id': r.expense_type_id.id or False, 'type_nature': r.type_nature or '',
            'duty_type_id': r.duty_type_id.id or False, 'category': r.category or '',
            'rate_type': r.rate_type or 'actual', 'rate': r.rate,
            'travel_mode_ids': r.travel_mode_ids.ids,
            'mode_rates': [{
                'travel_mode_id': mr.travel_mode_id.id,
                'rate_type': mr.rate_type or 'per_km',
                'rate': mr.rate, 'max_amount': mr.max_amount,
            } for mr in r.mode_rate_ids],
            'min_distance': r.min_distance, 'max_distance': r.max_distance,
            'tier1_limit': r.tier1_limit, 'tier2_limit': r.tier2_limit, 'tier3_limit': r.tier3_limit,
            'receipt_required': r.receipt_required, 'receipt_threshold': r.receipt_threshold,
            'remarks_required': r.remarks_required, 'auto_create': r.auto_create,
            'date_from': str(r.date_from) if r.date_from else '',
            'date_to': str(r.date_to) if r.date_to else '',
            'active': r.active, 'sequence': r.sequence,
        }

    @api.model
    def save_rule(self, vals, rule_id=None):
        if not vals.get('band_id') or not vals.get('expense_type_id'):
            raise UserError(_("Band and Expense Type are required."))
        writable = {
            'band_id': int(vals['band_id']),
            'expense_type_id': int(vals['expense_type_id']),
            'duty_type_id': int(vals['duty_type_id']) if vals.get('duty_type_id') else False,
            'category': vals.get('category') or False,
            'rate_type': vals.get('rate_type') or 'actual',
            'rate': float(vals.get('rate') or 0),
            'travel_mode_ids': [(6, 0, [int(m) for m in vals.get('travel_mode_ids', [])])],
            'min_distance': float(vals.get('min_distance') or 0),
            'max_distance': float(vals.get('max_distance') or 0),
            'tier1_limit': float(vals.get('tier1_limit') or 0),
            'tier2_limit': float(vals.get('tier2_limit') or 0),
            'tier3_limit': float(vals.get('tier3_limit') or 0),
            'receipt_required': bool(vals.get('receipt_required')),
            'receipt_threshold': float(vals.get('receipt_threshold') or 0),
            'remarks_required': bool(vals.get('remarks_required')),
            'auto_create': bool(vals.get('auto_create')),
            'date_from': vals.get('date_from') or False,
            'date_to': vals.get('date_to') or False,
            'active': bool(vals.get('active', True)),
            'sequence': int(vals.get('sequence') or 10),
        }
        # Per-mode rate rows — only for the modes that are actually allowed.
        allowed = set(int(m) for m in vals.get('travel_mode_ids', []))
        mode_cmds = [(5, 0, 0)]
        for mr in vals.get('mode_rates', []) or []:
            mode_id = int(mr.get('travel_mode_id') or 0)
            if not mode_id or mode_id not in allowed:
                continue
            mode_cmds.append((0, 0, {
                'travel_mode_id': mode_id,
                'rate_type': mr.get('rate_type') or 'per_km',
                'rate': float(mr.get('rate') or 0),
                'max_amount': float(mr.get('max_amount') or 0),
            }))
        writable['mode_rate_ids'] = mode_cmds
        if rule_id:
            rec = self.browse(int(rule_id))
            rec.write(writable)
        else:
            rec = self.create(writable)
        return rec.id

    @api.model
    def toggle_rule_active(self, rule_id):
        r = self.with_context(active_test=False).browse(int(rule_id))
        r.active = not r.active
        return r.active

    @api.model
    def delete_rule(self, rule_id):
        self.with_context(active_test=False).browse(int(rule_id)).unlink()
        return True


class SfaExpensePolicyModeRate(models.Model):
    """Per-travel-mode rate for a Travelling Allowance rule (bike/car/auto …).
    Distance-based modes use Per-KM (rate × km, optionally capped); bus/train/
    flight use Actual (reimburse actual, optionally capped at max_amount)."""
    _name = 'sfa.expense.policy.mode.rate'
    _description = 'Expense Policy Mode Rate'
    _order = 'sequence, id'

    rule_id = fields.Many2one('sfa.expense.policy.rule', string='Rule',
                              required=True, ondelete='cascade')
    travel_mode_id = fields.Many2one('sfa.travel.mode', string='Travel Mode',
                                     required=True, ondelete='cascade')
    rate_type = fields.Selection([
        ('per_km', 'Per KM'),
        ('actual', 'Actual'),
    ], default='per_km', required=True)
    rate = fields.Float('Rate per KM', digits=(16, 2))
    max_amount = fields.Float('Max Amount', digits=(16, 2))
    sequence = fields.Integer(default=10)
