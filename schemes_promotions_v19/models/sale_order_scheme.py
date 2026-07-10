# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ── Scheme tracking fields ────────────────────────────────────────────────
    applied_scheme_ids   = fields.Many2many(
        'scheme.promotion', string='Applied Schemes',
        relation='sale_order_scheme_rel',
        column1='order_id', column2='scheme_id')
    scheme_points_earned = fields.Float(string='Points Earned', readonly=True, default=0.0)
    scheme_summary       = fields.Text(string='Scheme Summary', readonly=True)

    # ── Apply Schemes ─────────────────────────────────────────────────────────
    def action_apply_schemes(self):
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            raise UserError("Schemes can only be applied to draft / quotation orders.")
        self._remove_scheme_lines()

        applicable    = self.env['scheme.promotion'].get_active_schemes_for_order(self)
        total_points  = 0.0
        applied       = self.env['scheme.promotion']
        summary_lines = []

        for scheme in applicable:
            benefits = scheme.evaluate_for_order(self)
            if not benefits:
                continue
            applied |= scheme
            for b in benefits:
                if b['type'] == 'free_product':
                    self._apply_free_product_benefit(b, scheme)
                    prod = self.env['product.product'].browse(b['product_id'])
                    summary_lines.append(
                        f"✓ {scheme.scheme_code}: Free {b['qty']} × {prod.name}")
                elif b['type'] == 'percent_discount':
                    self._apply_percent_discount_benefit(b, scheme)
                    summary_lines.append(
                        f"✓ {scheme.scheme_code}: {b['discount_pct']}% Discount")
                elif b['type'] == 'price_discount':
                    self._apply_price_discount_benefit(b, scheme)
                    summary_lines.append(
                        f"✓ {scheme.scheme_code}: ₹{b['amount']:,.2f} Discount")
                elif b['type'] == 'points':
                    total_points += b['points']
                    summary_lines.append(
                        f"✓ {scheme.scheme_code}: {b['points']:.0f} Points")

        self.applied_scheme_ids   = applied
        self.scheme_points_earned = total_points
        self.scheme_summary = (
            '\n'.join(summary_lines) if summary_lines else 'No applicable schemes found.')
        return True

    def action_clear_schemes(self):
        self.ensure_one()
        self._remove_scheme_lines()
        self.applied_scheme_ids   = [(5,)]
        self.scheme_points_earned = 0.0
        self.scheme_summary       = ''
        return True

    def _remove_scheme_lines(self):
        self.order_line.filtered(lambda l: l.is_scheme_line).unlink()

    def _apply_free_product_benefit(self, benefit, scheme):
        product = self.env['product.product'].browse(benefit['product_id'])
        if not product.exists():
            return
        self.env['sale.order.line'].create({
            'order_id':        self.id,
            'product_id':      product.id,
            'product_uom_qty': benefit['qty'],
            'price_unit':      0.0,
            'discount':        100.0,
            'name':            f"[SCHEME] {benefit['description']}",
            'is_scheme_line':  True,
            'scheme_id':       scheme.id,
        })

    def _apply_percent_discount_benefit(self, benefit, scheme):
        for line in self.order_line.filtered(lambda l: not l.is_scheme_line):
            line.scheme_discount = benefit['discount_pct']
            line.discount        = max(line.discount, benefit['discount_pct'])
            line.scheme_id       = scheme.id

    def _apply_price_discount_benefit(self, benefit, scheme):
        disc_prod = self._get_or_create_discount_product()
        if not disc_prod:
            return
        self.env['sale.order.line'].create({
            'order_id':        self.id,
            'product_id':      disc_prod.id,
            'product_uom_qty': 1,
            'price_unit':      -abs(benefit['amount']),
            'name':            f"[SCHEME] {benefit['description']}",
            'is_scheme_line':  True,
            'scheme_id':       scheme.id,
        })

    def _get_or_create_discount_product(self):
        product = self.env['product.product'].search(
            [('name', '=', 'Scheme Discount'), ('type', '=', 'service')], limit=1)
        if not product:
            product = self.env['product.product'].create({
                'name': 'Scheme Discount', 'type': 'service',
                'sale_ok': True, 'purchase_ok': False,
            })
        return product


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    is_scheme_line  = fields.Boolean(string='Scheme Line', default=False)
    scheme_id       = fields.Many2one(
        'scheme.promotion', string='Applied Scheme', ondelete='set null')
    scheme_discount = fields.Float(string='Scheme Disc %', digits=(5, 2))
