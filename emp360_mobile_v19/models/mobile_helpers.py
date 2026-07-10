"""
emp360_mobile — Mobile App Helper Model  (FINAL)

ALL mobile write AND read operations go through these helpers with sudo()
so basic field users never hit access-right errors.

KEY CONTEXT FLAGS USED:
  mobile_end_visit=True  → bypasses _check_store_image_required in visit_model.py
  manual_checkout=True   → bypasses hr.attendance write() override that strips check_out
  skip_image_check=True  → alternative flag for store image constraint
"""
from odoo import models, api, fields
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MobileAppHelpers(models.AbstractModel):
    _name = "emp360.mobile"
    _description = "Employee 360 Mobile App Helpers"

    # ── Access / Role ────────────────────────────────────────────────────────

    @api.model
    def get_user_access_info(self):
        user = self.env.user
        employee = self.env["hr.employee"].sudo().search(
            [("user_id", "=", user.id)], limit=1)
        is_manager = user.has_group(
            "employee_dashboard_v19.group_employee_dashboard_manager")
        return {
            "user_id":     user.id,
            "user_name":   user.name,
            "employee_id": employee.id if employee else False,
            "is_manager":  is_manager,
        }

    @api.model
    def get_accessible_employees(self):
        user = self.env.user
        is_manager = user.has_group(
            "employee_dashboard_v19.group_employee_dashboard_manager")
        if is_manager:
            employees = self.env["hr.employee"].sudo().search(
                [("active", "=", True)], order="name asc", limit=200)
        else:
            employees = self.env["hr.employee"].sudo().search(
                [("user_id", "=", user.id)], limit=1)
        return employees.read(["id", "name", "job_title", "department_id", "job_id"])

    # ═════════════════════════════════════════════════════════════════════════
    # ATTENDANCE  — uses manual_checkout context to bypass hr.attendance
    #               write() override that strips check_out field
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def get_today_attendance(self, employee_id):
        if not employee_id:
            return False
        today = fields.Date.context_today(self)
        att = self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", employee_id),
            ("check_in", ">=", f"{today} 00:00:00"),
        ], order="check_in desc", limit=1)
        if not att:
            return False
        return {
            "id":           att.id,
            "check_in":     fields.Datetime.to_string(att.check_in),
            "check_out":    fields.Datetime.to_string(att.check_out) if att.check_out else False,
            "worked_hours": att.worked_hours or 0,
        }

    @api.model
    def start_day(self, employee_id):
        if not employee_id:
            raise UserError("No employee ID provided.")
        employee = self.env["hr.employee"].sudo().browse(employee_id)
        if not employee.exists():
            raise UserError("Employee not found.")
        today = fields.Date.context_today(self)
        existing = self.env["hr.attendance"].sudo().search([
            ("employee_id", "=", employee_id),
            ("check_in", ">=", f"{today} 00:00:00"),
            ("check_out", "=", False),
        ], limit=1)
        if existing:
            return {"attendance_id": existing.id,
                    "check_in": fields.Datetime.to_string(existing.check_in),
                    "already_in": True}
        now = fields.Datetime.now()
        att = self.env["hr.attendance"].sudo().create({
            "employee_id": employee_id, "check_in": now})
        _logger.info("Mobile check-in: emp=%s att=%s", employee_id, att.id)
        return {"attendance_id": att.id,
                "check_in": fields.Datetime.to_string(att.check_in),
                "already_in": False}

    @api.model
    def end_day(self, employee_id, attendance_id):
        """
        End the day — write check_out to hr.attendance.
        MUST use context manual_checkout=True because hr_attendance.py
        has a write() override that strips check_out unless this flag is set.
        """
        if not attendance_id:
            raise UserError("No attendance record to close.")
        att = self.env["hr.attendance"].sudo().browse(attendance_id)
        if not att.exists():
            raise UserError("Attendance record not found.")
        if att.check_out:
            return {"attendance_id": att.id,
                    "check_out": fields.Datetime.to_string(att.check_out),
                    "worked_hours": att.worked_hours or 0,
                    "already_out": True}
        now = fields.Datetime.now()
        # KEY: manual_checkout=True bypasses the write() override in hr_attendance.py
        att.sudo().with_context(manual_checkout=True).write({"check_out": now})
        att.invalidate_recordset()
        att = self.env["hr.attendance"].sudo().browse(attendance_id)
        _logger.info("Mobile check-out: emp=%s att=%s worked=%.2f",
                      employee_id, att.id, att.worked_hours or 0)
        return {"attendance_id": att.id,
                "check_out": fields.Datetime.to_string(att.check_out),
                "worked_hours": att.worked_hours or 0,
                "already_out": False}

    # ═════════════════════════════════════════════════════════════════════════
    # VISIT — Start & End
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def start_visit(self, vals):
        """
        Create visit.model record with sudo().
        Geolocation and store_image are OPTIONAL — never block the visit.
        """
        if not vals.get("employee_id") or not vals.get("partner_id"):
            raise UserError("Employee and Customer are required.")

        create_vals = {
            "employee_id":       vals["employee_id"],
            "partner_id":        vals["partner_id"],
            "status":            "in_progress",
        }

        if vals.get("beat_id"):
            create_vals["beat_id"] = vals["beat_id"]
        if vals.get("beat_line_id"):
            create_vals["beat_line_id"] = vals["beat_line_id"]
        if vals.get("actual_start_time"):
            create_vals["actual_start_time"] = vals["actual_start_time"]

        # Store image — optional, never block if missing
        if vals.get("store_image"):
            create_vals["store_image"] = vals["store_image"]

        # Geolocation — optional, only set if we got real coordinates
        if vals.get("checkin_latitude") and vals["checkin_latitude"] is not False:
            create_vals["checkin_latitude"] = vals["checkin_latitude"]
        if vals.get("checkin_longitude") and vals["checkin_longitude"] is not False:
            create_vals["checkin_longitude"] = vals["checkin_longitude"]

        try:
            visit = self.env["visit.model"].sudo().create(create_vals)
        except Exception as e:
            _logger.error("Visit create failed: %s | vals: %s", e, create_vals)
            raise UserError(f"Could not start visit: {e}")

        _logger.info("Mobile visit start: v=%s emp=%s partner=%s",
                      visit.id, vals.get("employee_id"), vals.get("partner_id"))

        result = self.env["visit.model"].sudo().browse(visit.id).read([
            "id", "partner_id", "beat_id", "beat_line_id",
            "actual_start_time", "order_count", "total_order_amount"])
        return result[0] if result else {"id": visit.id}

    @api.model
    def end_visit(self, visit_id, vals):
        """
        End visit with sudo(). Geolocation is optional.
        Uses context mobile_end_visit=True to bypass _check_store_image_required
        constraint in visit_model.py.
        """
        if not visit_id:
            raise UserError("No visit to end.")
        visit = self.env["visit.model"].sudo().browse(visit_id)
        if not visit.exists():
            raise UserError("Visit not found.")
        if visit.status == "completed":
            return {"visit_id": visit_id, "status": "completed",
                    "success": True, "already_done": True}

        write_vals = {"status": "completed"}

        if vals.get("actual_end_time"):
            write_vals["actual_end_time"] = vals["actual_end_time"]
        else:
            write_vals["actual_end_time"] = fields.Datetime.now()

        if vals.get("visit_comments"):
            write_vals["visit_comments"] = vals["visit_comments"]

        # Geolocation — only write if we have real values
        if vals.get("checkout_latitude") and vals["checkout_latitude"] is not False:
            write_vals["checkout_latitude"] = vals["checkout_latitude"]
        if vals.get("checkout_longitude") and vals["checkout_longitude"] is not False:
            write_vals["checkout_longitude"] = vals["checkout_longitude"]

        if "is_productive" in vals:
            write_vals["is_productive"] = bool(vals["is_productive"])

        try:
            # KEY FIX: mobile_end_visit=True bypasses _check_store_image_required
            # skip_image_check=True is an alternative flag (belt + suspenders)
            visit.sudo().with_context(
                mobile_end_visit=True,
                skip_image_check=True,
            ).write(write_vals)
        except Exception as e:
            _logger.error("Visit end failed: %s | vals: %s", e, write_vals)
            raise UserError(f"Could not end visit: {e}")

        _logger.info("Mobile visit end: v=%s", visit_id)
        return {"visit_id": visit_id, "status": "completed", "success": True}

    # ═════════════════════════════════════════════════════════════════════════
    # VISIT — Read / Search (field users may not have read access)
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def get_visits(self, employee_id, is_manager, domain_extra=None, limit=50):
        domain = []
        if employee_id and not is_manager:
            domain.append(("employee_id", "=", employee_id))
        if domain_extra:
            domain.extend(domain_extra)
        visits = self.env["visit.model"].sudo().search_read(
            domain,
            ["id", "name", "partner_id", "beat_id", "employee_id",
             "actual_start_time", "actual_end_time", "duration_display",
             "status", "order_count", "total_order_amount", "is_productive",
             "total_collected", "visit_for"],
            order="actual_start_time desc", limit=limit)
        return visits

    @api.model
    def get_visit_detail(self, visit_id):
        if not visit_id:
            return False
        visit = self.env["visit.model"].sudo().search_read(
            [("id", "=", visit_id)],
            ["id", "name", "partner_id", "beat_id", "employee_id",
             "actual_start_time", "actual_end_time", "duration_display",
             "status", "order_count", "total_order_amount", "is_productive",
             "productivity_reason", "total_collected", "visit_for",
             "visit_comments", "checkin_latitude", "checkin_longitude",
             "checkout_latitude", "checkout_longitude", "geofence_valid",
             "checklist_done", "checklist_total", "travel_type", "vehicle_used"],
            limit=1)
        if not visit:
            return False
        collections = self.env["visit.collection"].sudo().search_read(
            [("visit_id", "=", visit_id), ("state", "=", "confirmed")],
            ["id", "name", "amount", "payment_mode", "date"], limit=20)
        orders = self.env["sale.order"].sudo().search_read(
            [("visit_id", "=", visit_id)],
            ["id", "name", "amount_total", "state"], limit=20)
        tickets = self.env["visit.ticket"].sudo().search_read(
            [("visit_id", "=", visit_id)],
            ["id", "name", "subject", "category", "priority", "state"], limit=10)
        result = visit[0]
        result["collections"] = collections
        result["orders"] = orders
        result["tickets"] = tickets
        return result

    # ═════════════════════════════════════════════════════════════════════════
    # ORDERS — Read
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def get_orders(self, employee_id, is_manager, domain_extra=None, limit=100):
        domain = []
        if domain_extra:
            domain.extend(domain_extra)
        if employee_id and not is_manager:
            emp = self.env["hr.employee"].sudo().browse(employee_id)
            if emp.user_id:
                domain.append(("user_id", "=", emp.user_id.id))
        orders = self.env["sale.order"].sudo().search_read(
            domain,
            ["id", "name", "partner_id", "amount_total", "state",
             "date_order", "order_line", "visit_id", "user_id"],
            order="date_order desc", limit=limit)
        return orders

    @api.model
    def get_order_lines(self, order_id):
        if not order_id:
            return []
        return self.env["sale.order.line"].sudo().search_read(
            [("order_id", "=", order_id)],
            ["id", "product_id", "product_uom_qty", "price_unit",
             "price_subtotal", "product_tag", "scheme_discount"],
            limit=50)

    # ═════════════════════════════════════════════════════════════════════════
    # COLLECTIONS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def create_collection(self, vals):
        coll = self.env["visit.collection"].sudo().create(vals)
        try:
            coll.sudo().action_confirm()
        except Exception:
            pass
        return {"collection_id": coll.id, "success": True}

    # ═════════════════════════════════════════════════════════════════════════
    # ORDERS — Create
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def create_order(self, vals):
        order = self.env["sale.order"].sudo().create(vals)
        return {"order_id": order.id, "order_name": order.name, "success": True}

    # ═════════════════════════════════════════════════════════════════════════
    # TICKETS
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def create_ticket(self, vals):
        ticket = self.env["visit.ticket"].sudo().create(vals)
        return {"ticket_id": ticket.id, "success": True}

    # ═════════════════════════════════════════════════════════════════════════
    # STOCK
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def save_stock(self, visit_id, lines):
        if not visit_id or not lines:
            return {"success": True, "count": 0}
        StockLedger = self.env.get("visit.stock.ledger")
        if StockLedger is not None:
            try:
                StockLedger.sudo().save_stock_from_visit(visit_id, lines)
                return {"success": True, "count": len(lines)}
            except Exception as e:
                _logger.warning("save_stock_from_visit failed: %s", e)
            for line in lines:
                try:
                    StockLedger.sudo().create({
                        "visit_id": visit_id,
                        "product_id": line.get("product_id"),
                        "opening_stock": line.get("opening_stock", 0),
                        "closing_stock": line.get("closing_stock", 0),
                        "damaged_stock": line.get("damaged_stock", 0),
                    })
                except Exception as e:
                    _logger.warning("Stock line failed: %s", e)
        return {"success": True, "count": len(lines)}

    # ═════════════════════════════════════════════════════════════════════════
    # SCHEMES
    # ═════════════════════════════════════════════════════════════════════════

    @api.model
    def get_schemes(self, status_filter='all', benefit_filter='all', search='', limit=100):
        """Return schemes for the mobile schemes dashboard."""
        SchemePromotion = self.env.get('scheme.promotion')
        if SchemePromotion is None:
            return []

        domain = [('active', '=', True)]
        if status_filter and status_filter != 'all':
            domain.append(('state', '=', status_filter))
        if benefit_filter and benefit_filter != 'all':
            domain.append(('benefit_type', '=', benefit_filter))

        schemes = SchemePromotion.sudo().search(domain, order='date_from desc', limit=limit)

        if search:
            sl = search.lower()
            schemes = schemes.filtered(
                lambda s: sl in (s.name or '').lower() or sl in (s.scheme_code or '').lower()
            )

        result = []
        for s in schemes:
            # Build a human-readable benefit summary
            benefit_summary = ''
            if s.benefit_type == 'free_product':
                if s.inv_free_product_id:
                    benefit_summary = 'Get %s %s free' % (s.inv_free_qty, s.inv_free_product_id.name)
                elif s.line_ids and s.line_ids[0].free_product_id:
                    l = s.line_ids[0]
                    benefit_summary = 'Get %s %s free' % (l.free_qty, l.free_product_id.name)
            elif s.benefit_type == 'percent_discount':
                pct = s.inv_discount_pct or (s.line_ids[0].discount_pct if s.line_ids else 0)
                benefit_summary = '%s%% discount' % pct
            elif s.benefit_type == 'price_discount':
                amt = s.inv_discount_amount or (s.line_ids[0].discount_amount if s.line_ids else 0)
                benefit_summary = u'₹%s off' % int(amt)
            elif s.benefit_type == 'points':
                pts = s.inv_reward_points or (s.line_ids[0].reward_points if s.line_ids else 0)
                benefit_summary = '%s reward points' % int(pts)

            result.append({
                'id': s.id,
                'name': s.name or '',
                'scheme_code': s.scheme_code or '',
                'scheme_type': s.scheme_type or '',
                'benefit_type': s.benefit_type or '',
                'date_from': fields.Date.to_string(s.date_from) if s.date_from else '',
                'date_to': fields.Date.to_string(s.date_to) if s.date_to else '',
                'state': s.state or 'draft',
                'benefit_summary': benefit_summary,
                'min_invoice_value': s.min_invoice_value or 0,
                'line_count': len(s.line_ids),
                'notes': s.notes or '',
            })
        return result

    @api.model
    def get_scheme_stats(self):
        """Return summary counts for the schemes dashboard header."""
        SchemePromotion = self.env.get('scheme.promotion')
        if SchemePromotion is None:
            return {'active': 0, 'draft': 0, 'expired': 0, 'total': 0}
        all_s = SchemePromotion.sudo().search([('active', '=', True)])
        return {
            'active':  len(all_s.filtered(lambda s: s.state == 'active')),
            'draft':   len(all_s.filtered(lambda s: s.state == 'draft')),
            'expired': len(all_s.filtered(lambda s: s.state == 'expired')),
            'total':   len(all_s),
        }