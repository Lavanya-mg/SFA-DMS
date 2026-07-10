/** @odoo-module **/
/**
 * SCHEME MANAGER — Custom OWL Dashboard
 * Rich dashboard with stat tiles + filter dropdowns + scheme cards
 */
import { registry }   from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const BENEFIT_LABELS = {
    free_product:     "Free Products",
    percent_discount: "Discount in %",
    price_discount:   "Discount in Value",
    points:           "Reward Points",
};

const TYPE_LABELS = {
    each_product:           "Each Product",
    each_product_qty:       "Same Product (QTY)",
    each_product_value:     "Same Product (VAL)",
    assorted_product:       "Assorted Product",
    assorted_product_qty:   "Assorted Product (QTY)",
    assorted_product_value: "Assorted Product (VAL)",
    invoice_value:          "Invoice Qty Based",
    slab_invoice_value:     "Invoice Val Based",
};

const STATE_LABELS = {
    draft:     "Draft",
    active:    "Active",
    expired:   "Expired",
    cancelled: "Cancelled",
};

const AVATAR_COLORS = {
    free_product:     "#06d6a0",
    percent_discount: "#f77f00",
    price_discount:   "#0077b6",
    points:           "#7209b7",
};

export class SchemeManager extends Component {
    static template = "schemes_promotions_v19.SchemeManager";
    static props = ["*"];

    setup() {
        this.orm          = useService("orm");
        this.actionSvc    = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading:       true,
            schemes:       [],
            stats:         { active: 0, draft: 0, expired: 0, total: 0, budget: 0 },
            channels:      [],
            totalCount:    0,
            // Filters
            search:        "",
            statusFilter:  "all",
            benefitFilter: "all",
            typeFilter:    "all",
            channelFilter: 0,
            sortField:     "create_date",
            sortAsc:       false,
            // UI
            openDropdown:  null,
        });

        onWillStart(async () => { await this._load(); });
    }

    async _load() {
        this.state.loading = true;
        try {
            const data = await this.orm.call("scheme.promotion", "get_dashboard_data", [
                this.state.statusFilter,
                this.state.benefitFilter,
                this.state.typeFilter,
                this.state.channelFilter || false,
                this.state.search,
                this.state.sortField,
                100,
            ]);
            this.state.schemes    = data.schemes    || [];
            this.state.stats      = data.stats      || {};
            this.state.channels   = data.channels   || [];
            this.state.totalCount = data.total_count || 0;
        } catch (e) {
            console.error("[SchemeManager]", e);
            this.notification.add("Failed to load schemes", { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    // ── Filters ──────────────────────────────────────────────────────────────
    async setStatus(v)  { this.state.statusFilter  = v; this.state.openDropdown = null; await this._load(); }
    async setBenefit(v) { this.state.benefitFilter = v; this.state.openDropdown = null; await this._load(); }
    async setType(v)    { this.state.typeFilter    = v; this.state.openDropdown = null; await this._load(); }
    async setChannel(v) { this.state.channelFilter = v; this.state.openDropdown = null; await this._load(); }
    async onSearch(ev)  { this.state.search = ev.target.value; await this._load(); }

    async resetFilters() {
        Object.assign(this.state, {
            search: "", statusFilter: "all", benefitFilter: "all",
            typeFilter: "all", channelFilter: 0,
        });
        await this._load();
    }

    async setSortField(f) { this.state.sortField = f; this.state.openDropdown = null; await this._load(); }
    toggleSort() { this.state.sortAsc = !this.state.sortAsc; this._load(); }
    toggleDropdown(name) { this.state.openDropdown = this.state.openDropdown === name ? null : name; }

    // ── Scheme actions ────────────────────────────────────────────────────────
    openScheme(id) {
        if (!id) {
            this.notification.add("Invalid scheme record.", { type: "warning" });
            return;
        }
        try {
            this.actionSvc.doAction({
                type: "ir.actions.act_window",
                res_model: "scheme.promotion",
                res_id: id,
                views: [[false, "form"]],
                target: "current",
            });
        } catch (e) {
            this.notification.add("Could not open scheme form.", { type: "danger" });
        }
    }

    goBack() {
        window.history.back();
    }

    newScheme() {
        try {
            this.actionSvc.doAction({
                type: "ir.actions.act_window",
                res_model: "scheme.promotion",
                views: [[false, "form"]],
                target: "current",
            });
        } catch (e) {
            this.notification.add("Could not open new scheme form.", { type: "danger" });
        }
    }

    async cloneScheme(ev, id) {
        ev.stopPropagation();
        try {
            await this.orm.call("scheme.promotion", "copy", [[id]]);
            this.notification.add("Scheme cloned successfully", { type: "success" });
            await this._load();
        } catch (e) {
            this.notification.add("Clone failed", { type: "danger" });
        }
    }

    async cancelScheme(ev, id) {
        ev.stopPropagation();
        try {
            await this.orm.call("scheme.promotion", "action_cancel", [[id]]);
            this.notification.add("Scheme cancelled", { type: "warning" });
            await this._load();
        } catch (e) {
            this.notification.add("Cancel failed", { type: "danger" });
        }
    }

    // ── Formatters ────────────────────────────────────────────────────────────
    fmtDate(d) {
        if (!d) return "—";
        return new Date(d).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
    }

    fmtMoney(v) {
        if (!v) return "₹0";
        if (v >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`;
        if (v >= 100000)   return `₹${(v / 100000).toFixed(1)}L`;
        if (v >= 1000)     return `₹${(v / 1000).toFixed(0)}K`;
        return `₹${Math.round(v).toLocaleString("en-IN")}`;
    }

    stateClass(s) {
        return ({
            active:    "sch-badge-active",
            draft:     "sch-badge-draft",
            expired:   "sch-badge-expired",
            cancelled: "sch-badge-cancelled",
        })[s] || "sch-badge-draft";
    }

    avatarColor(bt) { return AVATAR_COLORS[bt] || "#4361ee"; }

    get statusLabel()  {
        return this.state.statusFilter  === "all" ? "All Statuses"   : STATE_LABELS[this.state.statusFilter]   || this.state.statusFilter;
    }
    get benefitLabel() {
        return this.state.benefitFilter === "all" ? "All Categories" : BENEFIT_LABELS[this.state.benefitFilter] || this.state.benefitFilter;
    }
    get typeLabel()    {
        return this.state.typeFilter    === "all" ? "All Types"      : TYPE_LABELS[this.state.typeFilter]       || this.state.typeFilter;
    }
    get channelLabel() {
        if (!this.state.channelFilter) return "All Channels";
        const ch = this.state.channels.find(c => c.id === this.state.channelFilter);
        return ch ? ch.name : "All Channels";
    }
}

registry.category("actions").add("scheme_manager_v19", SchemeManager);
