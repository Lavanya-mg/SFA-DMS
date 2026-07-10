/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE SCHEMES SCREEN
 * Schemes master dashboard — mirrors Salesforce-style activity view
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MobileSchemes extends Component {
    static template = "employee_mobile_v19.MobileSchemes";
    static props = {
        employeeId: { type: [Number, { value: false }], optional: true },
        isManager:  { type: Boolean, optional: true },
    };

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading:       true,
            schemes:       [],
            filtered:      [],
            stats:         { active: 0, draft: 0, expired: 0, total: 0 },
            statusFilter:  "active",
            benefitFilter: "all",
            search:        "",
            selected:      null,
            showDetail:    false,
        });

        onWillStart(async () => { await this._load(); });
    }

    async _load() {
        this.state.loading = true;
        try {
            const [schemes, stats] = await Promise.all([
                this.orm.call("emp360.mobile", "get_schemes",
                    [this.state.statusFilter, this.state.benefitFilter, this.state.search, 100]),
                this.orm.call("emp360.mobile", "get_scheme_stats", []),
            ]);
            this.state.schemes  = schemes;
            this.state.filtered = schemes;
            this.state.stats    = stats;
        } catch (e) {
            console.error("[Schemes]", e);
            this.notification.add("Failed to load schemes", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    async setStatusFilter(f) {
        this.state.statusFilter = f;
        await this._load();
    }

    async setBenefitFilter(b) {
        this.state.benefitFilter = b;
        await this._load();
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        const q = this.state.search.toLowerCase();
        this.state.filtered = this.state.schemes.filter(s =>
            (s.name || "").toLowerCase().includes(q) ||
            (s.scheme_code || "").toLowerCase().includes(q)
        );
    }

    openDetail(scheme) {
        this.state.selected   = scheme;
        this.state.showDetail = true;
    }

    closeDetail() {
        this.state.showDetail = false;
        this.state.selected   = null;
    }

    // ── Formatters ────────────────────────────────────────────────────────────
    fmtDate(d) {
        if (!d) return "—";
        return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
    }

    schemeTypeLabel(t) {
        const MAP = {
            each_product:           "Each Product",
            each_product_qty:       "Each Product Qty",
            each_product_value:     "Each Product Value",
            assorted_product:       "Assorted Product",
            assorted_product_qty:   "Assorted Qty",
            assorted_product_value: "Assorted Value",
            invoice_value:          "Invoice Value",
            slab_invoice_value:     "Slab Invoice",
        };
        return MAP[t] || t;
    }

    benefitTypeLabel(b) {
        const MAP = {
            free_product:     "Free Products",
            percent_discount: "% Discount",
            price_discount:   "Price Discount",
            points:           "Reward Points",
        };
        return MAP[b] || b;
    }

    stateLabel(s) {
        return ({ draft: "Draft", active: "Active", expired: "Expired", cancelled: "Cancelled" })[s] || s;
    }

    stateClass(s) {
        return ({ active: "success", draft: "warning", expired: "danger", cancelled: "muted" })[s] || "muted";
    }

    benefitIcon(b) {
        return ({
            free_product:     "fa-gift",
            percent_discount: "fa-percent",
            price_discount:   "fa-tag",
            points:           "fa-star",
        })[b] || "fa-star";
    }

    benefitGradient(b) {
        return ({
            free_product:     "linear-gradient(135deg,#06d6a0,#019b72)",
            percent_discount: "linear-gradient(135deg,#4cc9f0,#0077b6)",
            price_discount:   "linear-gradient(135deg,#f77f00,#d62828)",
            points:           "linear-gradient(135deg,#f72585,#b5179e)",
        })[b] || "linear-gradient(135deg,#4361ee,#3a0ca3)";
    }
}
