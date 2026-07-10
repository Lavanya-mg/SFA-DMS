# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)

SCHEME_TYPES = [
    ('each_product',            'Each Product'),
    ('each_product_qty',        'Each Product Quantity'),
    ('each_product_value',      'Each Product Value'),
    ('assorted_product',        'Assorted Product'),
    ('assorted_product_qty',    'Assorted Product Quantity'),
    ('assorted_product_value',  'Assorted Product Value'),
    ('invoice_value',           'Invoice Value'),
    ('slab_invoice_value',      'Slab Invoice Value'),
]

BENEFIT_TYPES = [
    ('free_product',      'A. Free Products'),
    ('percent_discount',  'B. % Discounts'),
    ('price_discount',    'C. Price Discount'),
    ('points',            'D. Points'),
]

# ─────────────────────────────────────────────────────────────────────────────
# Scheme header
# ─────────────────────────────────────────────────────────────────────────────
class SchemePromotion(models.Model):
    _name = 'scheme.promotion'
    _description = 'Scheme / Promotion'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, name'
    _rec_name = 'name'

    name = fields.Char(string='Scheme Name', required=True, tracking=True)
    scheme_code = fields.Char(
        string='Scheme Code', copy=False, readonly=True, default='New')

    scheme_type = fields.Selection(
        SCHEME_TYPES, string='Scheme Type', required=True, tracking=True)
    benefit_type = fields.Selection(
        BENEFIT_TYPES, string='Benefit Type', required=True, tracking=True)

    date_from  = fields.Date(string='Valid From', required=True)
    date_to    = fields.Date(string='Valid To',   required=True)
    active     = fields.Boolean(default=True)
    state = fields.Selection([
        ('draft',     'Draft'),
        ('active',    'Active'),
        ('expired',   'Expired'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True, string='Status')

    company_id  = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True)

    # ── Applicable to (optional filters) ────────────────────────────────────
    customer_ids = fields.Many2many(
        'res.partner', string='Applicable Customers',
        help="Leave empty to apply to all customers")
    channel_ids  = fields.Many2many(
        'product.category', string='Applicable Channels',
        help="Leave empty to apply to all channels")

    # ── Invoice-level condition (types 7 & 8) ───────────────────────────────
    min_invoice_value = fields.Float(string='Min Invoice Value (₹)')

    # ── Invoice-level benefit (type 7 — single threshold) ───────────────────
    inv_free_product_id = fields.Many2one('product.product', string='Free Product')
    inv_free_qty        = fields.Float(string='Free Qty', default=1.0)
    inv_discount_pct    = fields.Float(string='Discount %', digits=(5, 2))
    inv_discount_amount = fields.Float(string='Discount Amount (₹)')
    inv_reward_points   = fields.Float(string='Reward Points')

    # ── Product lines (types 1–6) ────────────────────────────────────────────
    line_ids = fields.One2many(
        'scheme.promotion.line', 'scheme_id', string='Product Lines')

    # ── Invoice slabs (type 8) ───────────────────────────────────────────────
    slab_ids = fields.One2many(
        'scheme.promotion.invoice.slab', 'scheme_id', string='Invoice Slabs')

    notes = fields.Text(string='Terms & Conditions')

    # ── UI helper flags (not stored — recomputed on-the-fly) ─────────────────
    is_per_product   = fields.Boolean(compute='_compute_ui_flags')
    is_assorted      = fields.Boolean(compute='_compute_ui_flags')
    is_invoice       = fields.Boolean(compute='_compute_ui_flags')
    is_slab_invoice  = fields.Boolean(compute='_compute_ui_flags')
    has_qty_cond     = fields.Boolean(compute='_compute_ui_flags')
    has_value_cond   = fields.Boolean(compute='_compute_ui_flags')

    @api.depends('scheme_type')
    def _compute_ui_flags(self):
        per_product_types = {'each_product', 'each_product_qty', 'each_product_value'}
        assorted_types    = {'assorted_product', 'assorted_product_qty', 'assorted_product_value'}
        qty_types         = {'each_product_qty', 'assorted_product_qty'}
        value_types       = {'each_product_value', 'assorted_product_value'}
        for rec in self:
            rec.is_per_product  = rec.scheme_type in per_product_types
            rec.is_assorted     = rec.scheme_type in assorted_types
            rec.is_invoice      = rec.scheme_type == 'invoice_value'
            rec.is_slab_invoice = rec.scheme_type == 'slab_invoice_value'
            rec.has_qty_cond    = rec.scheme_type in qty_types
            rec.has_value_cond  = rec.scheme_type in value_types

    # ── Sequence ─────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('scheme_code') or vals['scheme_code'] == 'New':
                vals['scheme_code'] = (
                    self.env['ir.sequence'].next_by_code('scheme.promotion') or 'New')
        return super().create(vals_list)

    # ── Status actions ────────────────────────────────────────────────────────
    def action_activate(self):
        self.write({'state': 'active'})

    def action_expire(self):
        self.write({'state': 'expired'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    # ── Validations ───────────────────────────────────────────────────────────
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError("'Valid From' must be before 'Valid To'.")

    @api.constrains('scheme_type', 'benefit_type', 'line_ids', 'slab_ids')
    def _check_lines_required(self):
        for rec in self:
            if rec.scheme_type in (
                'each_product', 'each_product_qty', 'each_product_value',
                'assorted_product', 'assorted_product_qty', 'assorted_product_value',
            ) and not rec.line_ids:
                raise ValidationError(
                    f"Scheme type '{dict(SCHEME_TYPES)[rec.scheme_type]}' requires at least one product line.")
            if rec.scheme_type == 'slab_invoice_value' and not rec.slab_ids:
                raise ValidationError("Slab Invoice Value scheme requires at least one slab.")

    # ── Scheme evaluation helpers ─────────────────────────────────────────────
    def is_valid_today(self):
        from odoo.fields import Date
        today = Date.today()
        return (
            self.state == 'active'
            and self.date_from <= today <= self.date_to
        )

    def evaluate_for_order(self, order):
        """
        Returns a dict describing the benefit to apply on a sale.order.
        Called from sale order application logic.
        Returns: list of dicts [{type, product_id, qty, discount_pct, amount, points, description}]
        """
        self.ensure_one()
        if not self.is_valid_today():
            return []

        results = []
        order_lines = order.order_line.filtered(lambda l: not l.is_scheme_line)

        if self.scheme_type in ('each_product', 'each_product_qty', 'each_product_value'):
            results = self._eval_per_product(order_lines)

        elif self.scheme_type in ('assorted_product', 'assorted_product_qty', 'assorted_product_value'):
            results = self._eval_assorted(order_lines)

        elif self.scheme_type == 'invoice_value':
            results = self._eval_invoice_value(order_lines)

        elif self.scheme_type == 'slab_invoice_value':
            results = self._eval_slab_invoice(order_lines)

        return results

    def _eval_per_product(self, order_lines):
        results = []
        for line_def in self.line_ids:
            matching = order_lines.filtered(
                lambda l: l.product_id.id == line_def.product_id.id)
            if not matching:
                continue
            ordered_qty   = sum(matching.mapped('product_uom_qty'))
            ordered_value = sum(l.price_subtotal for l in matching)

            if self.scheme_type == 'each_product':
                # Benefit triggers per each unit bought
                multiplier = ordered_qty
                results += self._build_benefit(line_def, multiplier, ordered_value)

            elif self.scheme_type == 'each_product_qty':
                # Use slabs if defined, else direct min_qty on line
                if line_def.slab_ids:
                    slab = line_def._get_applicable_slab_by_qty(ordered_qty)
                    if slab:
                        results += self._build_benefit_from_slab(slab, 1)
                elif line_def.min_qty and ordered_qty >= line_def.min_qty:
                    results += self._build_benefit(line_def, 1, ordered_value)

            elif self.scheme_type == 'each_product_value':
                if line_def.slab_ids:
                    slab = line_def._get_applicable_slab_by_value(ordered_value)
                    if slab:
                        results += self._build_benefit_from_slab(slab, 1)
                elif line_def.min_value and ordered_value >= line_def.min_value:
                    results += self._build_benefit(line_def, 1, ordered_value)
        return results

    def _eval_assorted(self, order_lines):
        """Assorted: check if ALL defined products are present in the order."""
        results = []
        scheme_product_ids = set(self.line_ids.mapped('product_id').ids)
        ordered_product_ids = set(order_lines.mapped('product_id').ids)

        if not scheme_product_ids.issubset(ordered_product_ids):
            return []  # Not all assorted products present

        if self.scheme_type == 'assorted_product':
            for line_def in self.line_ids:
                if line_def.has_benefit:
                    results += self._build_benefit(line_def, 1, 0)

        elif self.scheme_type == 'assorted_product_qty':
            # Each product in assorted must meet its own qty threshold
            all_met = True
            for line_def in self.line_ids:
                if not line_def.min_qty:
                    continue
                ol = order_lines.filtered(lambda l: l.product_id.id == line_def.product_id.id)
                if not ol or sum(ol.mapped('product_uom_qty')) < line_def.min_qty:
                    all_met = False
                    break
            if all_met:
                for line_def in self.line_ids:
                    if line_def.has_benefit:
                        results += self._build_benefit(line_def, 1, 0)

        elif self.scheme_type == 'assorted_product_value':
            all_met = True
            for line_def in self.line_ids:
                if not line_def.min_value:
                    continue
                ol = order_lines.filtered(lambda l: l.product_id.id == line_def.product_id.id)
                if not ol or sum(l.price_subtotal for l in ol) < line_def.min_value:
                    all_met = False
                    break
            if all_met:
                for line_def in self.line_ids:
                    if line_def.has_benefit:
                        results += self._build_benefit(line_def, 1, 0)

        return results

    def _eval_invoice_value(self, order_lines):
        invoice_total = sum(l.price_subtotal for l in order_lines)
        if not self.min_invoice_value or invoice_total < self.min_invoice_value:
            return []
        return self._build_invoice_benefit(1, invoice_total)

    def _eval_slab_invoice(self, order_lines):
        invoice_total = sum(l.price_subtotal for l in order_lines)
        applicable_slab = None
        for slab in self.slab_ids.sorted('min_invoice_value', reverse=True):
            if invoice_total >= slab.min_invoice_value:
                applicable_slab = slab
                break
        if not applicable_slab:
            return []
        return self._build_benefit_from_invoice_slab(applicable_slab, invoice_total)

    def _build_benefit(self, line_def, multiplier, order_value):
        bt = self.benefit_type
        desc = f"[{self.scheme_code}] {self.name}"
        results = []
        if bt == 'free_product' and line_def.free_product_id:
            results.append({
                'type': 'free_product',
                'product_id': line_def.free_product_id.id,
                'qty': line_def.free_qty * multiplier,
                'discount_pct': 0,
                'amount': 0,
                'points': 0,
                'description': desc,
            })
        elif bt == 'percent_discount' and line_def.discount_pct:
            results.append({
                'type': 'percent_discount',
                'product_id': line_def.product_id.id,
                'qty': 0,
                'discount_pct': line_def.discount_pct,
                'amount': 0,
                'points': 0,
                'description': desc,
            })
        elif bt == 'price_discount' and line_def.discount_amount:
            results.append({
                'type': 'price_discount',
                'product_id': line_def.product_id.id,
                'qty': 0,
                'discount_pct': 0,
                'amount': line_def.discount_amount * multiplier,
                'points': 0,
                'description': desc,
            })
        elif bt == 'points' and line_def.reward_points:
            results.append({
                'type': 'points',
                'product_id': False,
                'qty': 0,
                'discount_pct': 0,
                'amount': 0,
                'points': line_def.reward_points * multiplier,
                'description': desc,
            })
        return results

    def _build_benefit_from_slab(self, slab, multiplier):
        bt = self.benefit_type
        desc = f"[{self.scheme_code}] {self.name}"
        results = []
        if bt == 'free_product' and slab.free_product_id:
            results.append({
                'type': 'free_product',
                'product_id': slab.free_product_id.id,
                'qty': slab.free_qty * multiplier,
                'discount_pct': 0, 'amount': 0, 'points': 0,
                'description': desc,
            })
        elif bt == 'percent_discount' and slab.discount_pct:
            results.append({
                'type': 'percent_discount',
                'product_id': False,
                'qty': 0, 'discount_pct': slab.discount_pct, 'amount': 0, 'points': 0,
                'description': desc,
            })
        elif bt == 'price_discount' and slab.discount_amount:
            results.append({
                'type': 'price_discount',
                'product_id': False,
                'qty': 0, 'discount_pct': 0, 'amount': slab.discount_amount, 'points': 0,
                'description': desc,
            })
        elif bt == 'points' and slab.reward_points:
            results.append({
                'type': 'points',
                'product_id': False,
                'qty': 0, 'discount_pct': 0, 'amount': 0, 'points': slab.reward_points,
                'description': desc,
            })
        return results

    def _build_invoice_benefit(self, multiplier, invoice_total):
        bt = self.benefit_type
        desc = f"[{self.scheme_code}] {self.name}"
        results = []
        if bt == 'free_product' and self.inv_free_product_id:
            results.append({
                'type': 'free_product',
                'product_id': self.inv_free_product_id.id,
                'qty': self.inv_free_qty * multiplier,
                'discount_pct': 0, 'amount': 0, 'points': 0,
                'description': desc,
            })
        elif bt == 'percent_discount' and self.inv_discount_pct:
            results.append({
                'type': 'percent_discount',
                'product_id': False,
                'qty': 0, 'discount_pct': self.inv_discount_pct, 'amount': 0, 'points': 0,
                'description': desc,
            })
        elif bt == 'price_discount' and self.inv_discount_amount:
            results.append({
                'type': 'price_discount',
                'product_id': False,
                'qty': 0, 'discount_pct': 0, 'amount': self.inv_discount_amount, 'points': 0,
                'description': desc,
            })
        elif bt == 'points' and self.inv_reward_points:
            results.append({
                'type': 'points',
                'product_id': False,
                'qty': 0, 'discount_pct': 0, 'amount': 0, 'points': self.inv_reward_points,
                'description': desc,
            })
        return results

    def _build_benefit_from_invoice_slab(self, slab, invoice_total):
        bt = self.benefit_type
        desc = f"[{self.scheme_code}] {self.name} (Slab ≥ ₹{slab.min_invoice_value:,.0f})"
        results = []
        if bt == 'free_product' and slab.free_product_id:
            results.append({
                'type': 'free_product',
                'product_id': slab.free_product_id.id,
                'qty': slab.free_qty,
                'discount_pct': 0, 'amount': 0, 'points': 0,
                'description': desc,
            })
        elif bt == 'percent_discount' and slab.discount_pct:
            results.append({
                'type': 'percent_discount',
                'product_id': False,
                'qty': 0, 'discount_pct': slab.discount_pct, 'amount': 0, 'points': 0,
                'description': desc,
            })
        elif bt == 'price_discount' and slab.discount_amount:
            results.append({
                'type': 'price_discount',
                'product_id': False,
                'qty': 0, 'discount_pct': 0, 'amount': slab.discount_amount, 'points': 0,
                'description': desc,
            })
        elif bt == 'points' and slab.reward_points:
            results.append({
                'type': 'points',
                'product_id': False,
                'qty': 0, 'discount_pct': 0, 'amount': 0, 'points': slab.reward_points,
                'description': desc,
            })
        return results

    # ── Smart search ──────────────────────────────────────────────────────────
    @api.model
    def get_active_schemes_for_order(self, order):
        """Return all applicable active schemes for a sale order."""
        from odoo.fields import Date
        today = Date.today()
        domain = [
            ('state', '=', 'active'),
            ('date_from', '<=', today),
            ('date_to', '>=', today),
            ('active', '=', True),
        ]
        if order.partner_id:
            domain += [
                '|',
                ('customer_ids', '=', False),
                ('customer_ids', 'in', [order.partner_id.id]),
            ]
        return self.search(domain)

    @api.model
    def get_dashboard_data(self, status='all', benefit='all', scheme_type='all',
                           channel_id=False, search='', sort='create_date', limit=100):
        """Return schemes + stats for the OWL Scheme Manager dashboard."""
        domain = [('active', '=', True)]
        if status and status != 'all':
            domain.append(('state', '=', status))
        if benefit and benefit != 'all':
            domain.append(('benefit_type', '=', benefit))
        if scheme_type and scheme_type != 'all':
            domain.append(('scheme_type', '=', scheme_type))
        if channel_id:
            domain.append(('channel_ids', 'in', [channel_id]))

        order_map = {
            'create_date': 'create_date desc',
            'date_from':   'date_from desc',
            'name':        'name asc',
            'state':       'state asc',
        }
        order = order_map.get(sort, 'create_date desc')
        schemes = self.sudo().search(domain, order=order, limit=limit)

        if search:
            sl = search.lower()
            schemes = schemes.filtered(
                lambda s: sl in (s.name or '').lower() or sl in (s.scheme_code or '').lower()
            )

        all_s = self.sudo().search([('active', '=', True)])

        def _benefit_summary(s):
            if s.benefit_type == 'free_product':
                if s.inv_free_product_id:
                    return u'Get %s %s free' % (int(s.inv_free_qty or 1), s.inv_free_product_id.name)
                elif s.line_ids and s.line_ids[0].free_product_id:
                    l = s.line_ids[0]
                    return u'Get %s %s free' % (int(l.free_qty or 1), l.free_product_id.name)
            elif s.benefit_type == 'percent_discount':
                pct = s.inv_discount_pct or (s.line_ids[0].discount_pct if s.line_ids else 0)
                return u'%s%% discount' % pct
            elif s.benefit_type == 'price_discount':
                amt = s.inv_discount_amount or (s.line_ids[0].discount_amount if s.line_ids else 0)
                return u'₹%s off' % int(amt)
            elif s.benefit_type == 'points':
                pts = s.inv_reward_points or (s.line_ids[0].reward_points if s.line_ids else 0)
                return u'%s reward points' % int(pts)
            return ''

        def _trigger_summary(s):
            parts = []
            if s.min_invoice_value:
                parts.append(u'Inv val ₹%s' % int(s.min_invoice_value))
            if s.line_ids and s.line_ids[0].min_qty:
                parts.append(u'Min %s qty' % int(s.line_ids[0].min_qty))
            if s.line_ids and s.line_ids[0].min_value:
                parts.append(u'MOV ₹%s' % int(s.line_ids[0].min_value))
            return u' · '.join(parts)

        avatar_map = {
            'free_product':     'FP',
            'percent_discount': '%',
            'price_discount':   'Rs',
            'points':           'RP',
        }

        result = []
        for s in schemes:
            result.append({
                'id':              s.id,
                'name':            s.name or '',
                'scheme_code':     s.scheme_code or '',
                'scheme_type':     s.scheme_type or '',
                'benefit_type':    s.benefit_type or '',
                'state':           s.state or 'draft',
                'date_from':       fields.Date.to_string(s.date_from) if s.date_from else '',
                'date_to':         fields.Date.to_string(s.date_to) if s.date_to else '',
                'benefit_summary': _benefit_summary(s),
                'trigger_summary': _trigger_summary(s),
                'avatar':          avatar_map.get(s.benefit_type, '?'),
                'channels':        [c.name for c in s.channel_ids],
                'line_count':      len(s.line_ids),
                'can_cancel':      s.state in ('active', 'draft'),
            })

        # Available channels for dropdown
        all_channels = all_s.mapped('channel_ids')
        seen, unique_channels = set(), []
        for c in all_channels:
            if c.id not in seen:
                seen.add(c.id)
                unique_channels.append({'id': c.id, 'name': c.name})

        active_budget = sum(
            s.min_invoice_value for s in all_s if s.state == 'active' and s.min_invoice_value
        )

        return {
            'schemes':     result,
            'stats': {
                'active':  len(all_s.filtered(lambda s: s.state == 'active')),
                'draft':   len(all_s.filtered(lambda s: s.state == 'draft')),
                'expired': len(all_s.filtered(lambda s: s.state == 'expired')),
                'total':   len(all_s),
                'budget':  active_budget,
            },
            'channels':    unique_channels,
            'total_count': len(result),
        }


# ─────────────────────────────────────────────────────────────────────────────
# Product line (for types 1–6)
# ─────────────────────────────────────────────────────────────────────────────
class SchemePromotionLine(models.Model):
    _name = 'scheme.promotion.line'
    _description = 'Scheme Product Line'
    _order = 'sequence, id'

    scheme_id    = fields.Many2one('scheme.promotion', required=True, ondelete='cascade')
    sequence     = fields.Integer(default=10)
    product_id   = fields.Many2one('product.product', string='Product', required=True)
    product_name = fields.Char(related='product_id.name', store=True)

    # ── Condition fields ──────────────────────────────────────────────────────
    min_qty   = fields.Float(string='Min Qty',        digits=(12, 3))
    min_value = fields.Float(string='Min Value (₹)',  digits=(12, 2))

    # ── Benefit fields ────────────────────────────────────────────────────────
    free_product_id  = fields.Many2one('product.product', string='Free Product')
    free_qty         = fields.Float(string='Free Qty',       default=1.0, digits=(12, 3))
    discount_pct     = fields.Float(string='Discount %',     digits=(5, 2))
    discount_amount  = fields.Float(string='Disc. Amount (₹)', digits=(12, 2))
    reward_points    = fields.Float(string='Points',          digits=(12, 2))

    # ── Slab sub-lines (for qty/value slabs per product) ─────────────────────
    slab_ids = fields.One2many(
        'scheme.promotion.line.slab', 'line_id', string='Qty / Value Slabs')

    # ── Computed helpers ──────────────────────────────────────────────────────
    benefit_type = fields.Selection(related='scheme_id.benefit_type', store=False)
    scheme_type  = fields.Selection(related='scheme_id.scheme_type',  store=False)

    has_benefit = fields.Boolean(compute='_compute_has_benefit')

    @api.depends('free_product_id', 'discount_pct', 'discount_amount', 'reward_points')
    def _compute_has_benefit(self):
        for rec in self:
            rec.has_benefit = bool(
                rec.free_product_id or rec.discount_pct or
                rec.discount_amount or rec.reward_points)

    def _get_applicable_slab_by_qty(self, qty):
        """Return highest slab whose min_qty <= qty."""
        applicable = self.slab_ids.filtered(lambda s: s.min_qty and qty >= s.min_qty)
        return applicable.sorted('min_qty', reverse=True)[:1] or False

    def _get_applicable_slab_by_value(self, value):
        """Return highest slab whose min_value <= value."""
        applicable = self.slab_ids.filtered(lambda s: s.min_value and value >= s.min_value)
        return applicable.sorted('min_value', reverse=True)[:1] or False


# ─────────────────────────────────────────────────────────────────────────────
# Per-product slab (qty or value tiers within a product line)
# ─────────────────────────────────────────────────────────────────────────────
class SchemePromotionLineSlab(models.Model):
    _name = 'scheme.promotion.line.slab'
    _description = 'Scheme Product Line Slab'
    _order = 'min_qty, min_value'

    line_id   = fields.Many2one('scheme.promotion.line', required=True, ondelete='cascade')
    scheme_id = fields.Many2one(related='line_id.scheme_id', store=True)

    # Condition (one of these)
    min_qty   = fields.Float(string='Min Qty',       digits=(12, 3))
    min_value = fields.Float(string='Min Value (₹)', digits=(12, 2))

    # Benefit
    free_product_id = fields.Many2one('product.product', string='Free Product')
    free_qty        = fields.Float(string='Free Qty',       default=1.0, digits=(12, 3))
    discount_pct    = fields.Float(string='Discount %',     digits=(5, 2))
    discount_amount = fields.Float(string='Disc. Amount (₹)', digits=(12, 2))
    reward_points   = fields.Float(string='Points',          digits=(12, 2))

    benefit_type = fields.Selection(related='line_id.scheme_id.benefit_type', store=False)


# ─────────────────────────────────────────────────────────────────────────────
# Invoice-level slab (for slab_invoice_value type)
# ─────────────────────────────────────────────────────────────────────────────
class SchemePromotionInvoiceSlab(models.Model):
    _name = 'scheme.promotion.invoice.slab'
    _description = 'Scheme Invoice Slab'
    _order = 'min_invoice_value'

    scheme_id         = fields.Many2one('scheme.promotion', required=True, ondelete='cascade')
    min_invoice_value = fields.Float(string='Min Invoice Value (₹)', required=True, digits=(12, 2))

    # Benefit
    free_product_id = fields.Many2one('product.product', string='Free Product')
    free_qty        = fields.Float(string='Free Qty',       default=1.0, digits=(12, 3))
    discount_pct    = fields.Float(string='Discount %',     digits=(5, 2))
    discount_amount = fields.Float(string='Disc. Amount (₹)', digits=(12, 2))
    reward_points   = fields.Float(string='Points',          digits=(12, 2))

    benefit_type = fields.Selection(related='scheme_id.benefit_type', store=False)

    # Display label
    label = fields.Char(compute='_compute_label')

    @api.depends('min_invoice_value', 'free_product_id', 'discount_pct', 'discount_amount', 'reward_points')
    def _compute_label(self):
        for rec in self:
            parts = [f"≥ ₹{rec.min_invoice_value:,.0f}"]
            if rec.free_product_id:
                parts.append(f"→ {rec.free_qty} × {rec.free_product_id.name}")
            if rec.discount_pct:
                parts.append(f"→ {rec.discount_pct}%")
            if rec.discount_amount:
                parts.append(f"→ ₹{rec.discount_amount:,.0f} off")
            if rec.reward_points:
                parts.append(f"→ {rec.reward_points:.0f} pts")
            rec.label = ' | '.join(parts)
