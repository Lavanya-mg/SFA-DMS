/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE PROFILE / MORE SCREEN
 * Employee profile, attendance history, KPI, collections, tickets, settings
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MobileProfile extends Component {
    static template = "employee_mobile_v19.MobileProfile";
    static props = {
        employeeId: { type: [Number, { value: false }], optional: true },
        isManager: { type: Boolean, optional: true },
    };

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");
        this.action       = useService("action");

        // ── Bind all methods used in template ────────────────────────────────
        this.setSection = this.setSection.bind(this);

        this.state = useState({
            loading:       true,
            employee:      null,
            activeSection: "profile",
            attendance:    [],
            attLoading:    false,
            kpiTargets:    [],
            kpiPeriod:     null,
            kpiLoading:    false,
            collections:   [],
            collLoading:   false,
            tickets:       [],
            tickLoading:   false,
            pjps:          [],
            pjpLoading:    false,
            monthStats: {
                visits:      0,
                orders:      0,
                sales:       0,
                collections: 0,
                attendance:  0,
                worked_hrs:  0,
            },
        });

        onWillStart(async () => {
            await this._loadProfile();
            await this._loadMonthStats();
        });
    }

    get empId()     { return this.props.employeeId; }
    get isManager() { return this.props.isManager; }

    async _loadProfile() {
        if (!this.empId) { this.state.loading = false; return; }
        try {
            const rows = await this.orm.searchRead(
                "hr.employee", [["id", "=", this.empId]],
                ["name", "work_email", "work_phone", "department_id",
                 "job_id", "coach_id", "parent_id", "image_128"],
                { limit: 1 }
            );
            this.state.employee = rows[0] || null;
        } catch (e) { console.warn("profile:", e); }
        this.state.loading = false;
    }

    async _loadMonthStats() {
        if (!this.empId) return;
        const now      = new Date();
        const firstDay = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-01`;

        try {
            const [visits, att, collections] = await Promise.all([
                this.orm.searchRead(
                    "visit.model",
                    [["employee_id", "=", this.empId], ["actual_start_time", ">=", firstDay + " 00:00:00"]],
                    ["id", "status", "order_count"], { limit: 500 }
                ),
                this.orm.searchRead(
                    "hr.attendance",
                    [["employee_id", "=", this.empId], ["check_in", ">=", firstDay + " 00:00:00"]],
                    ["id", "worked_hours"], { limit: 100 }
                ),
                this.orm.searchRead(
                    "visit.collection",
                    [["employee_id", "=", this.empId], ["date", ">=", firstDay], ["state", "=", "confirmed"]],
                    ["amount"], { limit: 200 }
                ),
            ]);

            const done = visits.filter(v => v.status === "completed");
            const totalWrk = att.reduce((s, a) => s + (a.worked_hours || 0), 0);
            const hrs  = Math.floor(totalWrk);
            const mins = Math.round((totalWrk - hrs) * 60);

            this.state.monthStats = {
                visits:      done.length,
                orders:      done.reduce((s, v) => s + (v.order_count || 0), 0),
                sales:       0,
                collections: collections.reduce((s, c) => s + (c.amount || 0), 0),
                attendance:  att.length,
                worked_hrs:  `${hrs}h ${mins}m`,
            };
        } catch (e) { console.warn("monthStats:", e); }
    }

    async setSection(s) {
        this.state.activeSection = s;
        switch (s) {
            case "attendance":
                await this._loadAttendance(); break;
            case "kpi":
                await this._loadKPI(); break;
            case "collections":
                await this._loadCollections(); break;
            case "tickets":
                await this._loadTickets(); break;
            case "pjp":
                await this._loadPJP(); break;
        }
    }

    async _loadAttendance() {
        this.state.attLoading = true;
        try {
            const rows = await this.orm.searchRead(
                "hr.attendance",
                [["employee_id", "=", this.empId]],
                ["id", "check_in", "check_out", "worked_hours",
                 "checkin_city", "checkout_city"],
                { order: "check_in desc", limit: 30 }
            );
            this.state.attendance = rows;
        } catch (e) { console.warn("attendance:", e); }
        this.state.attLoading = false;
    }

    async _loadKPI() {
        this.state.kpiLoading = true;
        try {
            const today = new Date().toISOString().slice(0, 10);
            const periods = await this.orm.searchRead(
                "kpi.period",
                [["date_from", "<=", today], ["date_to", ">=", today]],
                ["id", "name", "date_from", "date_to"],
                { limit: 1 }
            );
            this.state.kpiPeriod = periods[0] || null;

            if (periods.length) {
                const targets = await this.orm.searchRead(
                    "kpi.target",
                    [["employee_id", "=", this.empId], ["period_id", "=", periods[0].id]],
                    ["id", "name", "state",
                     "target_orders",      "actual_orders",      "achievement_orders",
                     "target_visits",      "actual_visits",      "achievement_visits",
                     "target_new_dealers", "actual_new_dealers", "achievement_new_dealers",
                     "target_payment_collected", "actual_payment_collected", "achievement_payment_collected",
                     "target_complaints_solved", "actual_complaints_solved", "achievement_complaints_solved",
                     "overall_achievement"],
                    { limit: 1 }
                );
                this.state.kpiTargets = targets;
            } else {
                this.state.kpiTargets = [];
            }
        } catch (e) { console.warn("kpi:", e); }
        this.state.kpiLoading = false;
    }

    async _loadCollections() {
        this.state.collLoading = true;
        try {
            const now      = new Date();
            const firstDay = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-01`;
            const rows = await this.orm.searchRead(
                "visit.collection",
                [["employee_id", "=", this.empId], ["date", ">=", firstDay]],
                ["id", "name", "date", "amount", "payment_mode", "partner_id", "state", "reference"],
                { order: "date desc", limit: 50 }
            );
            this.state.collections = rows;
        } catch (e) { console.warn("collections:", e); }
        this.state.collLoading = false;
    }

    async _loadTickets() {
        this.state.tickLoading = true;
        try {
            const rows = await this.orm.searchRead(
                "visit.ticket",
                [["employee_id", "=", this.empId]],
                ["id", "name", "subject", "category", "priority", "state", "date", "partner_id"],
                { order: "date desc", limit: 30 }
            );
            this.state.tickets = rows;
        } catch (e) { console.warn("tickets:", e); }
        this.state.tickLoading = false;
    }

    async _loadPJP() {
        this.state.pjpLoading = true;
        try {
            const rows = await this.orm.searchRead(
                "pjp.model",
                [["employee_id", "=", this.empId]],
                ["id", "name", "start_date", "end_date", "state"],
                { order: "start_date desc", limit: 20 }
            );
            this.state.pjps = rows;
        } catch (e) { console.warn("pjp:", e); }
        this.state.pjpLoading = false;
    }

    // ── KPI helpers ──────────────────────────────────────────────────────────
    kpiItems(target) {
        if (!target) return [];
        return [
            { label: "Visits",      target: target.target_visits,             actual: target.actual_visits,             pct: target.achievement_visits,             color: "#4361ee" },
            { label: "Orders",      target: target.target_orders,             actual: target.actual_orders,             pct: target.achievement_orders,             color: "#06d6a0" },
            { label: "Collections", target: target.target_payment_collected,  actual: target.actual_payment_collected,  pct: target.achievement_payment_collected,  color: "#f77f00" },
            { label: "New Dealers", target: target.target_new_dealers,        actual: target.actual_new_dealers,        pct: target.achievement_new_dealers,        color: "#7209b7" },
            { label: "Complaints",  target: target.target_complaints_solved,  actual: target.actual_complaints_solved,  pct: target.achievement_complaints_solved,  color: "#f72585" },
        ].filter(k => k.target > 0);
    }

    achievementColor(pct) {
        if (pct >= 80) return "#06d6a0";
        if (pct >= 50) return "#f77f00";
        return "#ef233c";
    }

    openOdooView(model, domain, viewType = "list") {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            domain,
            views: [[false, viewType]],
        });
    }

    // ── Formatters ───────────────────────────────────────────────────────────
    fmtDate(dt) {
        if (!dt) return "—";
        return new Date(dt).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
    }

    fmtTime(dt) {
        if (!dt) return "--:--";
        return new Date(dt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
    }

    fmtHours(h) {
        if (!h) return "0h";
        const hrs  = Math.floor(h);
        const mins = Math.round((h - hrs) * 60);
        return `${hrs}h ${mins}m`;
    }

    fmtMoney(v) {
        if (!v) return "₹0";
        if (v >= 100000) return `₹${(v / 100000).toFixed(1)}L`;
        if (v >= 1000)   return `₹${(v / 1000).toFixed(0)}K`;
        return `₹${Math.round(v).toLocaleString("en-IN")}`;
    }

    stateLabel(s) {
        const map = { draft: "Draft", confirmed: "Confirmed", done: "Done", active: "Active", approved: "Approved", cancelled: "Cancelled" };
        return map[s] || s;
    }

    stateClass(s) {
        const map = { confirmed: "success", done: "success", active: "success", approved: "info", draft: "warning", cancelled: "danger" };
        return map[s] || "muted";
    }

    ticketStateClass(s) {
        const map = { open: "warning", in_progress: "info", resolved: "success", closed: "muted" };
        return map[s] || "muted";
    }

    priorityClass(p) {
        const map = { Low: "info", Medium: "warning", High: "danger", Critical: "danger" };
        return map[p] || "muted";
    }

    paymentModeIcon(mode) {
        const map = { Cash: "fa-money", UPI: "fa-mobile", Cheque: "fa-file-text-o", NEFT: "fa-bank" };
        return map[mode] || "fa-credit-card";
    }

    get initials() {
        const name = this.state.employee?.name || "";
        return name.split(" ").slice(0, 2).map(w => w[0] || "").join("").toUpperCase() || "U";
    }
}