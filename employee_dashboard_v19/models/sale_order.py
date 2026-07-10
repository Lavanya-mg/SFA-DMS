# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.fields import Date
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MustSellProduct(models.Model):
    """Admin-configured Must Sell / Focus Sell products."""
    _name = 'must.sell.product'
    _description = 'Must Sell / Focus Sell Product'
    _order = 'sequence, id'

    sequence   = fields.Integer(default=10)
    product_id = fields.Many2one('product.product', string='Product', required=True, index=True)
    tag_type   = fields.Selection([
        ('must_sell',  'Must Sell'),
        ('focus_sell', 'Focus Sell'),
    ], string='Tag', required=True, default='must_sell')
    date_from  = fields.Date(string='Valid From')
    date_to    = fields.Date(string='Valid To')
    active     = fields.Boolean(default=True)
    notes      = fields.Text(string='Notes')

    _sql_constraints = [
        ('unique_product_tag', 'UNIQUE(product_id, tag_type)',
         'A product can only be tagged once per type.'),
    ]


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    visit_id    = fields.Many2one(
        related='order_id.visit_id', string='Visit', store=True, readonly=True)
    product_tag = fields.Selection([
        ('must_sell',  'Must Sell'),
        ('focus_sell', 'Focus Sell'),
        ('normal',     'Normal'),
    ], string='Product Tag', default='normal')

    @api.onchange('product_id')
    def _onchange_product_tag(self):
        if not self.product_id:
            self.product_tag = 'normal'
            return
        today = Date.today()
        tag_record = self.env['must.sell.product'].sudo().search([
            ('product_id', '=', self.product_id.id),
            ('active', '=', True),
            '|', ('date_from', '=', False), ('date_from', '<=', today),
            '|', ('date_to', '=', False), ('date_to', '>=', today),
        ], limit=1, order='tag_type asc')
        self.product_tag = tag_record.tag_type if tag_record else 'normal'

        if hasattr(self, '_compute_applied_schemes'):
            self._compute_applied_schemes()

class RedeemPointsWizard(models.TransientModel):
    _name = 'sale.order.redeem.wizard'
    _description = 'Wizard to redeem points'

    order_id = fields.Many2one('sale.order', required=True)
    points_available = fields.Float(related='order_id.customer_points_balance')
    points_to_redeem = fields.Float(string="Points to redeem", required=True)

    def action_apply_redemption(self):
        self.ensure_one()
        if self.points_to_redeem <= 0:
            raise UserError("Please enter points greater than 0.")
        if self.points_to_redeem > self.points_available:
            raise UserError("Insufficient points.")

        # 1. Deduct from Partner (The Dynamic Part)
        self.order_id.partner_id.sudo().write({
            'total_reward_points': self.order_id.partner_id.total_reward_points - self.points_to_redeem
        })

        # 2. Update Order
        self.order_id.write({
            'reward_points_redeemed': self.points_to_redeem,
            'loyalty_discount': self.points_to_redeem
        })
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
class ResPartner(models.Model):
    _inherit = 'res.partner'

    total_reward_points = fields.Float(string="Total Reward Points", default=0.0)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ── Visit / Beat ─────────────────────────────────────────────────────────
    visit_id = fields.Many2one(
        'visit.model', string='Visit', index=True, ondelete='set null')
    beat_id  = fields.Many2one(
        'beat.module', string='Beat',
        related='visit_id.beat_id', store=True, readonly=True)

    # ── Task 1: Order Classification ─────────────────────────────────────────
    channel = fields.Selection([
        ('field_app',       'Field App'),
        ('retailer_portal', 'Retailer Portal'),
        ('whatsapp',        'WhatsApp'),
        ('api',             'API'),
    ], string='Channel', default='field_app', index=True)

    order_type = fields.Selection([
        ('regular',     'Regular'),
        ('urgent',      'Urgent'),
        ('replacement', 'Replacement'),
        ('sample',      'Sample'),
    ], string='Order Type', default='regular')

    trade_channel = fields.Selection([
        ('gt',         'GT (General Trade)'),
        ('mt',         'MT (Modern Trade)'),
        ('ecommerce',  'E-Commerce'),
    ], string='Trade Channel')

    # ── Task 1: Territory ─────────────────────────────────────────────────────
    territory_id = fields.Many2one('fmcg.territory', string='Territory', index=True)
    region       = fields.Char(
        related='territory_id.region', string='Region', store=True, readonly=True)

    # ── Task 1: Attendance / Visit ────────────────────────────────────────────
    day_attendance_id = fields.Many2one('hr.attendance', string='Day Attendance')

    # ── Task 1: Loyalty / Points ──────────────────────────────────────────────
    reward_points_redeemed = fields.Float(string='Reward Points Redeemed', default=0.0)
    loyalty_discount       = fields.Float(string='Loyalty Discount', default=0.0)

    # ── Task 1: Warehouse / Address ───────────────────────────────────────────
    warehouse_state_id = fields.Many2one('res.country.state', string='Warehouse State')
    shipping_state_id  = fields.Many2one('res.country.state', string='Shipping State')

    # ── Task 1: Priority Sell Compliance ─────────────────────────────────────
    priority_sell_compliance = fields.Boolean(string='Priority Sell Compliance', default=False)
    priority_sell_override   = fields.Boolean(string='Priority Sell Override', default=False)

    # ── Task 1: Sync / Offline ────────────────────────────────────────────────
    offline_created = fields.Boolean(string='Offline Created', default=False)
    is_synced       = fields.Boolean(string='Is Synced', default=False)

    # ── Task 2: Approval Workflow ─────────────────────────────────────────────
    approval_state = fields.Selection([
        ('draft',     'Draft'),
        ('pending',   'Pending Approval'),
        ('approved',  'Approved'),
        ('rejected',  'Rejected'),
    ], string='Approval Status', default='draft', index=True, copy=False)

    approver_id     = fields.Many2one('res.users', string='Approver', copy=False)
    submitted_by    = fields.Many2one('res.users', string='Submitted By', copy=False)
    submitted_date  = fields.Datetime(string='Submitted Date', copy=False)
    approved_by     = fields.Many2one('res.users', string='Approved By', copy=False)
    approval_date   = fields.Datetime(string='Approval Date', copy=False)
    rejection_reason = fields.Text(string='Rejection Reason', copy=False)
    
    # ── Task 3: Reward Points (computed) ─────────────────────────────────────
    customer_points_balance = fields.Float(
        string='Customer Balance', compute='_compute_customer_points', store=False)
    available_headroom = fields.Float(
        string='Available Headroom', compute='_compute_customer_points', store=False)

    # @api.depends('partner_id', 'reward_points_redeemed')
    # def _compute_customer_points(self):
    #     for order in self:
    #         if order.partner_id:
    #             earned = self.env['sale.order'].sudo().search([
    #                 ('partner_id', '=', order.partner_id.id),
    #                 ('id', '!=', order.id or 0),
    #             ]).mapped('scheme_points_earned') if hasattr(self.env['sale.order'], '_fields') and 'scheme_points_earned' in self.env['sale.order']._fields else []
    #             balance = sum(earned) if earned else 0.0
    #         else:
    #             balance = 0.0
    #         order.customer_points_balance = balance
    #         order.available_headroom = max(0.0, balance - (order.reward_points_redeemed or 0.0))

    @api.depends('partner_id', 'reward_points_redeemed')
    def _compute_customer_points(self):
        for order in self:
            if order.partner_id:
                # 1. Search for all other confirmed orders for this partner
                other_orders = self.env['sale.order'].sudo().search([
                    ('partner_id', '=', order.partner_id.id),
                    ('id', '!=', order.id or 0),
                    ('state', 'in', ['sale', 'done'])
                ])
                
                # 2. Sum points earned (if the field exists)
                earned_points = sum(other_orders.mapped('scheme_points_earned')) if hasattr(self.env['sale.order'], '_fields') and 'scheme_points_earned' in self.env['sale.order']._fields else 0.0
                
                # 3. Sum points already redeemed in previous orders
                redeemed_points = sum(other_orders.mapped('reward_points_redeemed'))
                
                # 4. Calculate Net Balance (Earned - Redeemed)
                balance = earned_points - redeemed_points
            else:
                balance = 0.0
            
            # 5. Set values
            order.customer_points_balance = balance
            order.available_headroom = max(0.0, balance - (order.reward_points_redeemed or 0.0)) 

    @api.model
    def get_quick_order_product_data(self, partner_id, product_ids):
        """Return price book price, active schemes, and available UOMs for each product."""
        from odoo.fields import Date
        today = Date.today()
        result = {}

        for prod_id in product_ids:
            product = self.env['product.product'].browse(prod_id)
            if not product.exists():
                continue

            # Price Book: customer → category → base → list
            price = product.list_price
            price_source = 'list'
            base_domain = [
                ('product_id', '=', prod_id), ('active', '=', True),
                '|', ('date_from', '=', False), ('date_from', '<=', today),
                '|', ('date_to', '=', False), ('date_to', '>=', today),
            ]
            pb = self.env['price.book'].search(
                base_domain + [('price_type', '=', 'customer'), ('customer_id', '=', partner_id)],
                order='sequence', limit=1)
            if pb:
                price, price_source = pb.unit_price, 'customer'
            else:
                pb = self.env['price.book'].search(
                    base_domain + [('price_type', '=', 'category'),
                                   ('category_id', '=', product.categ_id.id)],
                    order='sequence', limit=1)
                if pb:
                    price, price_source = pb.unit_price, 'category'
                else:
                    pb = self.env['price.book'].search(
                        base_domain + [('price_type', '=', 'base')],
                        order='sequence', limit=1)
                    if pb:
                        price, price_source = pb.unit_price, 'base'

            # Active Schemes for this product
            schemes = []
            try:
                active_schemes = self.env['scheme.promotion'].search([
                    ('state', '=', 'active'),
                    ('date_from', '<=', today),
                    ('date_to', '>=', today),
                    ('line_ids.product_id', '=', prod_id),
                ])
                for scheme in active_schemes:
                    for line in scheme.line_ids.filtered(lambda l: l.product_id.id == prod_id):
                        badge = ''
                        if scheme.benefit_type == 'free_product' and line.free_product_id:
                            badge = f'+{int(line.free_qty or 1)} Free'
                        elif scheme.benefit_type == 'percent_discount' and line.discount_pct:
                            badge = f'{line.discount_pct:.0f}% Off'
                        elif scheme.benefit_type == 'price_discount':
                            badge = 'Price Off'
                        elif scheme.benefit_type == 'points':
                            badge = 'Points'
                        schemes.append({
                            'scheme_id': scheme.id,
                            'name': scheme.name,
                            'benefit_type': scheme.benefit_type,
                            'badge': badge,
                            'min_qty': line.min_qty or 0,
                            'free_product_id': line.free_product_id.id if line.free_product_id else False,
                            'free_product_name': line.free_product_id.name if line.free_product_id else '',
                            'free_qty': line.free_qty or 0,
                            'discount_pct': line.discount_pct or 0,
                        })
            except Exception:
                pass

            # UOMs offered for this product = base UOM + every conversion-rule target.
            # Built purely from uom.conversion.rule (which carries the target UOM and factor),
            # so it works regardless of the uom.uom model internals (Odoo 19 dropped the old
            # category_id/factor fields) and surfaces box/g/mm even if those UOMs are archived.
            uoms = []
            try:
                default_uom = product.uom_id

                # Base UOM first (multiplier 1).
                if default_uom:
                    uoms.append({
                        'id': default_uom.id,
                        'name': default_uom.name,
                        'price_multiplier': 1.0,
                        'compatible': True,
                        'has_rule': False,
                    })

                # Product-specific + global conversion rules whose source is this base UOM.
                # Rule factor = "how many From UoM fit in one To UoM" (e.g. Units→box, factor=12),
                # which is exactly the price multiplier: 1 target UOM costs `factor` base UOMs.
                conv_rules = self.env['uom.conversion.rule'].sudo().search([
                    ('active', '=', True),
                    ('from_uom_id', '=', default_uom.id if default_uom else False),
                    '|',
                    ('product_id', '=', prod_id),
                    ('is_global', '=', True),
                ])
                # Product-specific rules win over global ones for the same target UOM.
                conv_rules = conv_rules.sorted(key=lambda r: 0 if r.product_id else 1)
                seen_ids = {default_uom.id} if default_uom else set()
                for rule in conv_rules:
                    to_uom = rule.to_uom_id
                    if not to_uom or to_uom.id in seen_ids:
                        continue  # product-specific rule already won for this target
                    seen_ids.add(to_uom.id)
                    uoms.append({
                        'id': to_uom.id,
                        'name': to_uom.name,
                        'price_multiplier': rule.factor,
                        'compatible': True,
                        'has_rule': True,
                    })
            except Exception as e:
                _logger.warning("UOM fetch error for product %s: %s", prod_id, e)

            result[prod_id] = {
                'price': price,
                'price_source': price_source,
                'schemes': schemes,
                'uoms': uoms,
                'default_uom_id': product.uom_id.id if product.uom_id else False,
                'default_uom_name': product.uom_id.name if product.uom_id else '',
            }

        return result

    # ── Task 2: Approval Methods ──────────────────────────────────────────────
    def _get_approver(self):
        """Return the approver: owner's manager or company admin."""
        self.ensure_one()
        owner = self.user_id
        if owner:
            employee = self.env['hr.employee'].sudo().search(
                [('user_id', '=', owner.id)], limit=1)
            if employee and employee.parent_id and employee.parent_id.user_id:
                return employee.parent_id.user_id
        return self.env.ref('base.user_admin', raise_if_not_found=False) or self.env.user

    def action_submit_approval(self):
        for order in self:
            approver = order._get_approver()
            order.write({
                'approval_state': 'pending',
                'submitted_by':   self.env.uid,
                'submitted_date': fields.Datetime.now(),
                'approver_id':    approver.id,
                'rejection_reason': False,
            })
            order.message_post(
                body=f"Order submitted for approval. Approver: <b>{approver.name}</b>",
                subtype_xmlid='mail.mt_note',
                partner_ids=[approver.partner_id.id] if approver.partner_id else [],
            )
        return True

    def action_recall(self):
        for order in self:
            if order.approval_state != 'pending':
                raise UserError("Only orders in 'Pending Approval' state can be recalled.")
            order.write({'approval_state': 'draft'})
            order.message_post(
                body="Approval recalled. Order returned to Draft.",
                subtype_xmlid='mail.mt_note',
            )
        return True

    def action_approve(self):
        for order in self:
            if order.approval_state != 'pending':
                raise UserError("Only orders in 'Pending Approval' state can be approved.")
            order.write({
                'approval_state': 'approved',
                'approved_by':    self.env.uid,
                'approval_date':  fields.Datetime.now(),
            })
            order.message_post(
                body=f"Order <b>approved</b> by {self.env.user.name}.",
                subtype_xmlid='mail.mt_note',
                partner_ids=[order.submitted_by.partner_id.id] if order.submitted_by and order.submitted_by.partner_id else [],
            )
        return True

    def action_reject(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Reject Order',
            'res_model': 'sale.order.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

    # ── Task 3: Redeem Points ─────────────────────────────────────────────────
    def action_redeem_points(self):
        self.ensure_one()
        if self.customer_points_balance <= 0:
            raise UserError("Customer has no points to redeem.")
        if self.reward_points_redeemed > 0:
            raise UserError("Points already redeemed on this order.")
        discount = min(self.customer_points_balance, self.amount_total)
        self.write({
            'reward_points_redeemed': self.customer_points_balance,
            'loyalty_discount': discount,
        })
        self.message_post(
            body=f"Redeemed {self.customer_points_balance:.0f} reward points. Discount applied: ₹{discount:.2f}",
            subtype_xmlid='mail.mt_note',
        )
        # return True
        return {
            'name': 'Redeem Reward Points',
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.redeem.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_order_id': self.id},
        }
    
    def action_clear_redemption(self):
        self.ensure_one()
        # Restore points to partner
        if self.reward_points_redeemed > 0:
            self.partner_id.sudo().write({
                'total_reward_points': self.partner_id.total_reward_points + self.reward_points_redeemed
            })
            # Reset order fields
            self.write({
                'reward_points_redeemed': 0.0,
                'loyalty_discount': 0.0,
            })
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    # ── CRUD ──────────────────────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        for order in orders:
            _logger.info("DEBUG: Order %s created. State: %s. Lines: %s",
                         order.name, order.state, len(order.order_line))

            if self._context.get('visit_id') and not order.visit_id:
                order.visit_id = self._context['visit_id']

            if order.state in ('draft', 'sent'):
                try:
                    order.sudo().action_apply_schemes()
                    _logger.info("DEBUG: action_apply_schemes executed for %s", order.name)
                except Exception as e:
                    _logger.error("DEBUG: Failed to apply schemes to %s: %s", order.name, e)
            else:
                _logger.warning("DEBUG: Skipped schemes for %s because state is %s", order.name, order.state)
        orders.filtered(lambda o: o.state in ('sale', 'done'))._trigger_kpi_recompute()
        return orders

    def write(self, vals):
        result = super().write(vals)
        if vals.get('state') in ('sale', 'done', 'cancel') or 'user_id' in vals:
            self._trigger_kpi_recompute()
        return result

    def _trigger_kpi_recompute(self):
        if 'kpi.target' not in self.env:
            return
        employees = self.env['hr.employee']
        user_ids = self.mapped('user_id').ids
        if user_ids:
            employees |= self.env['hr.employee'].sudo().search(
                [('user_id', 'in', user_ids)])
        visit_emp_ids = self.sudo().mapped('visit_id.employee_id').ids
        if visit_emp_ids:
            employees |= self.env['hr.employee'].sudo().browse(visit_emp_ids)
        if not employees:
            return
        kpi_targets = self.env['kpi.target'].sudo().search(
            [('employee_id', 'in', employees.ids)])
        if not kpi_targets:
            return
        kpi_targets._compute_actuals()
        kpi_targets.flush_recordset([
            'actual_orders', 'actual_order_amount', 'actual_visits',
            'actual_new_dealers', 'actual_payment_collected', 'actual_complaints_solved',
        ])
        kpi_targets._compute_achievements()
        kpi_targets.flush_recordset([
            'achievement_orders', 'achievement_visits', 'achievement_new_dealers',
            'achievement_payment_collected', 'achievement_complaints_solved',
            'overall_achievement',
        ])

    @api.model
    def get_top_selling_products(self, partner_id, limit=10):
        # Get the last 10 products sold to this partner
        self.env.cr.execute("""
            SELECT sol.product_id, SUM(sol.product_uom_qty) as total_qty
            FROM sale_order_line sol
            JOIN sale_order so ON sol.order_id = so.id
            WHERE so.partner_id = %s
            AND so.state IN ('sale', 'done')
            GROUP BY sol.product_id
            ORDER BY total_qty DESC
            LIMIT %s
        """, (partner_id, limit))
        
        results = self.env.cr.dictfetchall()
        
        # Enrich with product names
        product_data = []
        for row in results:
            product = self.env['product.product'].browse(row['product_id'])
            product_data.append({
                'product_id': product.id,
                'product_name': product.name,
                'total_sold': row['total_qty'],
                'price': product.list_price
            })
        return product_data


class SaleOrderRejectWizard(models.TransientModel):
    _name = 'sale.order.reject.wizard'
    _description = 'Sale Order Rejection Wizard'

    order_id         = fields.Many2one('sale.order', string='Order', required=True)
    rejection_reason = fields.Text(string='Rejection Reason', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        order = self.order_id
        if order.approval_state != 'pending':
            raise UserError("Only orders in 'Pending Approval' state can be rejected.")
        order.write({
            'approval_state':   'rejected',
            'rejection_reason': self.rejection_reason,
        })
        order.message_post(
            body=f"Order <b>rejected</b> by {self.env.user.name}.<br/>Reason: {self.rejection_reason}",
            subtype_xmlid='mail.mt_note',
            partner_ids=[order.submitted_by.partner_id.id] if order.submitted_by and order.submitted_by.partner_id else [],
        )
        return {'type': 'ir.actions.act_window_close'}
