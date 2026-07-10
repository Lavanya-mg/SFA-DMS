/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE MANAGER / TEAM SCREEN
 * Team overview, employee cards, attendance, beat reports
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MobileManager extends Component {
    static template = "employee_mobile_v19.MobileManager";
    static props = {
        employeeId: { type: [Number, { value: false }], optional: true },
    };

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");

        // ── Bind all methods used in template ────────────────────────────────
        this.setFilter      = this.setFilter.bind(this);
        this.onSearchInput  = this.onSearchInput.bind(this);
        this.openEmpDetail  = this.openEmpDetail.bind(this);
        this.closeEmpDetail = this.closeEmpDetail.bind(this);

        this.state = useState({
            loading:   true,
            employees: [],
            empStats:  {},
            filter:    "all",
            search:    "",
            filtered:  [],
            selectedEmpId:   null,
            showEmpDetail:   false,
            empDetail:       null,
            empDetailBusy:   false,
            teamSummary: {
                total:        0,
                checked_in:   0,
                beat_active:  0,
                visits_today: 0,
                orders_today: 0,
                sales_today:  0,
            },
        });

        onWillStart(async () => {
            await this._load();
        });
    }

    async _load() {
        this.state.loading = true;
        try {
            const employees = await this.orm.call("emp360.mobile", "get_accessible_employees", []);
            this.state.employees = employees;
            this.state.teamSummary.total = employees.length;

            const today  = new Date().toISOString().slice(0, 10);
            const empIds = employees.map(e => e.id);

            if (!empIds.length) {
                this.state.loading = false;
                return;
            }

            const [attRows, beatRows, visitRows] = await Promise.all([
                this.orm.searchRead(
                    "hr.attendance",
                    [["employee_id", "in", empIds], ["check_in", ">=", today + " 00:00:00"]],
                    ["id", "employee_id", "check_in", "check_out", "worked_hours"],
                    { limit: 500 }
                ),
                this.orm.searchRead(
                    "beat.module",
                    [["employee_id", "in", empIds], ["beat_date", "=", today]],
                    ["id", "employee_id", "status", "customer_count"],
                    { limit: 200 }
                ),
                this.orm.searchRead(
                    "visit.model",
                    [["employee_id", "in", empIds], ["actual_start_time", ">=", today + " 00:00:00"]],
                    ["id", "employee_id", "status", "total_order_amount", "order_count"],
                    { limit: 500 }
                ),
            ]);

            const stats = {};
            for (const emp of employees) {
                const id = emp.id;
                const att = attRows.filter(a => a.employee_id[0] === id);
                const beats = beatRows.filter(b => b.employee_id[0] === id);
                const visits = visitRows.filter(v => v.employee_id[0] === id);
                const done = visits.filter(v => v.status === "completed");

                stats[id] = {
                    checked_in:    att.length > 0 && !att[0].check_out,
                    check_in:      att[0]?.check_in || null,
                    worked_hours:  att[0]?.worked_hours || 0,
                    beat_status:   beats[0]?.status || "none",
                    beat_name:     beats[0]?.name   || "—",
                    visits_done:   done.length,
                    visits_total:  visits.length,
                    orders_count:  done.reduce((s, v) => s + (v.order_count || 0), 0),
                    sales:         done.reduce((s, v) => s + (v.total_order_amount || 0), 0),
                    active_visit:  visits.find(v => v.status === "in_progress") || null,
                };
            }
            this.state.empStats = stats;

            const allAtt    = Object.values(stats).filter(s => s.checked_in).length;
            const allBeats  = Object.values(stats).filter(s => s.beat_status === "in_progress").length;
            const allVisits = Object.values(stats).reduce((s, e) => s + e.visits_done, 0);
            const allOrders = Object.values(stats).reduce((s, e) => s + e.orders_count, 0);
            const allSales  = Object.values(stats).reduce((s, e) => s + e.sales, 0);

            this.state.teamSummary = {
                total:        employees.length,
                checked_in:   allAtt,
                beat_active:  allBeats,
                visits_today: allVisits,
                orders_today: allOrders,
                sales_today:  allSales,
            };

            this._applyFilters();
        } catch (e) {
            console.error("[MobileManager] load:", e);
        } finally {
            this.state.loading = false;
        }
    }

    _applyFilters() {
        let list = [...this.state.employees];

        if (this.state.filter === "active") {
            list = list.filter(e => this.state.empStats[e.id]?.checked_in);
        } else if (this.state.filter === "inactive") {
            list = list.filter(e => !this.state.empStats[e.id]?.checked_in);
        }

        if (this.state.search) {
            const q = this.state.search.toLowerCase();
            list = list.filter(e => e.name.toLowerCase().includes(q));
        }

        this.state.filtered = list;
    }

    setFilter(f) {
        this.state.filter = f;
        this._applyFilters();
    }

    onSearchInput(ev) {
        this.state.search = ev.target.value;
        this._applyFilters();
    }

    async openEmpDetail(emp) {
        this.state.selectedEmpId = emp.id;
        this.state.showEmpDetail = true;
        this.state.empDetailBusy = true;
        this.state.empDetail     = null;

        try {
            const today    = new Date().toISOString().slice(0, 10);
            const firstDay = `${new Date().getFullYear()}-${String(new Date().getMonth()+1).padStart(2,"0")}-01`;

            const [empRows, monthVisits, monthOrders] = await Promise.all([
                this.orm.searchRead(
                    "hr.employee", [["id", "=", emp.id]],
                    ["name", "work_email", "work_phone", "department_id", "job_id"],
                    { limit: 1 }
                ),
                this.orm.searchRead(
                    "visit.model",
                    [["employee_id", "=", emp.id], ["actual_start_time", ">=", firstDay + " 00:00:00"]],
                    ["id", "status", "partner_id", "actual_start_time", "actual_end_time", "order_count"],
                    { limit: 100 }
                ),
                this.orm.searchRead(
                    "sale.order",
                    [["create_date", ">=", firstDay + " 00:00:00"]],
                    ["id", "amount_total", "state"],
                    { limit: 100 }
                ),
            ]);

            const stats = this.state.empStats[emp.id] || {};
            const done  = monthVisits.filter(v => v.status === "completed");
            const confOrders = monthOrders.filter(o => o.state === "sale" || o.state === "done");

            this.state.empDetail = {
                ...empRows[0],
                stats,
                month: {
                    visits:       done.length,
                    visits_total: monthVisits.length,
                    orders:       confOrders.length,
                    sales:        confOrders.reduce((s, o) => s + (o.amount_total || 0), 0),
                },
                todayVisits: monthVisits.filter(v => v.actual_start_time?.startsWith(today)).slice(0, 5),
            };
        } catch (e) {
            console.error("[MobileManager] emp detail:", e);
        } finally {
            this.state.empDetailBusy = false;
        }
    }

    closeEmpDetail() {
        this.state.showEmpDetail = false;
        this.state.empDetail     = null;
    }

    // ── Formatters ───────────────────────────────────────────────────────────
    fmtMoney(v) {
        if (!v) return "₹0";
        if (v >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`;
        if (v >= 100000)   return `₹${(v / 100000).toFixed(1)}L`;
        if (v >= 1000)     return `₹${(v / 1000).toFixed(0)}K`;
        return `₹${Math.round(v).toLocaleString("en-IN")}`;
    }

    fmtTime(dt) {
        if (!dt) return "--:--";
        return new Date(dt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
    }

    fmtHours(h) {
        if (!h) return "0h 0m";
        const hrs  = Math.floor(h);
        const mins = Math.round((h - hrs) * 60);
        return `${hrs}h ${mins}m`;
    }

    getInitials(name) {
        return (name || "?").split(" ").slice(0, 2).map(w => w[0] || "").join("").toUpperCase();
    }

    getAvatarGradient(str) {
        const gradients = [
            "linear-gradient(135deg,#4361ee,#3a0ca3)",
            "linear-gradient(135deg,#06d6a0,#019b72)",
            "linear-gradient(135deg,#f72585,#b5179e)",
            "linear-gradient(135deg,#f77f00,#d62828)",
            "linear-gradient(135deg,#7209b7,#3a0ca3)",
            "linear-gradient(135deg,#4cc9f0,#0077b6)",
        ];
        let h = 0;
        for (let i = 0; i < (str || "").length; i++) h = str.charCodeAt(i) + ((h << 5) - h);
        return gradients[Math.abs(h) % gradients.length];
    }

    beatStatusClass(status) {
        const map = { in_progress: "warning", completed: "success", pending: "info", draft: "muted" };
        return map[status] || "muted";
    }
}