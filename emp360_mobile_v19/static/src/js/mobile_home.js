/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE HOME SCREEN
 * Hero KPI cards + quick actions + today's summary
 */

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MobileHome extends Component {
    static template = "employee_mobile_v19.MobileHome";
    static props = {
        employeeId: { type: [Number, { value: false }], optional: true },
        employeeName: { type: [String, { value: "" }], optional: true },
        isManager: { type: Boolean, optional: true },
        employees: { type: Array, optional: true },
        onNavigate: { type: Function, optional: true },
    };

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");

        // ── Bind methods that are called from template ───────────────────────
        this.navigateTo = this.navigateTo.bind(this);

        this.state = useState({
            loading:     true,
            kpi: {
                visits_today:    0,
                visits_month:    0,
                orders_month:    0,
                sales_month:     0,
                collections:     0,
                achievement:     0,
                beats_today:     0,
                beats_completed: 0,
            },
            attendance: {
                checkedIn:    false,
                checkIn:      null,
                checkOut:     null,
                workedHours:  null,
            },
            activeVisit:   null,
            currentBeat:   null,
            recentVisits:  [],
            recentOrders:  [],
            todayKpi:      null,
            // Manager overview
            teamStats: {
                total:        0,
                active:       0,
                visits_today: 0,
                orders_today: 0,
            },
            topPerformers: [],
        });

        onWillStart(async () => {
            await this._load();
        });
    }

    get empId()     { return this.props.employeeId; }
    get isManager() { return this.props.isManager; }

    async _load() {
        this.state.loading = true;
        try {
            if (this.isManager) {
                await this._loadManagerData();
            } else {
                await this._loadFieldUserData();
            }
        } catch (e) {
            console.error("[MobileHome] load error:", e);
        } finally {
            this.state.loading = false;
        }
    }

    async _loadFieldUserData() {
        if (!this.empId) return;

        const today     = new Date().toISOString().slice(0, 10);
        const now       = new Date();
        const firstDay  = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`;
        const empId     = this.empId;

        // 1. Attendance
        try {
            const att = await this.orm.call("hr.attendance", "get_today_attendance", [empId]);
            if (att && att.check_in) {
                this.state.attendance.checkedIn   = !att.check_out;
                this.state.attendance.checkIn     = att.check_in;
                this.state.attendance.checkOut    = att.check_out;
                this.state.attendance.workedHours = att.worked_hours
                    ? this._fmtHours(att.worked_hours) : null;
            }
        } catch (e) { console.warn("attendance:", e); }

        // 2. Today's visits
        try {
            const todayVisits = await this.orm.searchRead(
                "visit.model",
                [["employee_id", "=", empId], ["actual_start_time", ">=", today + " 00:00:00"]],
                ["id", "status", "partner_id", "actual_start_time", "actual_end_time", "order_count", "total_order_amount"],
                { limit: 50 }
            );
            this.state.kpi.visits_today    = todayVisits.length;
            const completedToday           = todayVisits.filter(v => v.status === "completed");
            this.state.kpi.visits_today    = completedToday.length;

            // Active visit
            const inProgress = todayVisits.find(v => v.status === "in_progress");
            this.state.activeVisit = inProgress || null;

            // Recent visits
            this.state.recentVisits = todayVisits.slice(0, 5);
        } catch (e) { console.warn("visits:", e); }

        // 3. Month visits
        try {
            const monthVisits = await this.orm.searchRead(
                "visit.model",
                [["employee_id", "=", empId], ["actual_start_time", ">=", firstDay + " 00:00:00"]],
                ["id", "status"],
                { limit: 500 }
            );
            this.state.kpi.visits_month = monthVisits.filter(v => v.status === "completed").length;
        } catch (e) { console.warn("month visits:", e); }

        // 4. Today's beats
        try {
            const beats = await this.orm.searchRead(
                "beat.module",
                [["employee_id", "=", empId], ["beat_date", "=", today]],
                ["id", "name", "beat_number", "status", "customer_count"],
                { limit: 10 }
            );
            this.state.kpi.beats_today     = beats.length;
            this.state.kpi.beats_completed = beats.filter(b => b.status === "completed").length;
            this.state.currentBeat         = beats.find(b => b.status === "in_progress") || beats[0] || null;
        } catch (e) { console.warn("beats:", e); }

        // 5. Month orders + sales
        try {
            const empRow = await this.orm.searchRead(
                "hr.employee", [["id", "=", empId]], ["user_id"]
            );
            const userId = empRow[0]?.user_id?.[0];
            if (userId) {
                const orders = await this.orm.searchRead(
                    "sale.order",
                    [
                        ["user_id", "=", userId],
                        ["date_order", ">=", firstDay + " 00:00:00"],
                        ["state", "in", ["sale", "done"]],
                    ],
                    ["amount_total"],
                    { limit: 500 }
                );
                this.state.kpi.orders_month = orders.length;
                this.state.kpi.sales_month  = orders.reduce((s, o) => s + (o.amount_total || 0), 0);
            }
        } catch (e) { console.warn("orders:", e); }

        // 6. KPI target achievement
        try {
            const kpiPeriods = await this.orm.searchRead(
                "kpi.period",
                [["date_from", "<=", today], ["date_to", ">=", today]],
                ["id"],
                { limit: 1 }
            );
            if (kpiPeriods.length) {
                const targets = await this.orm.searchRead(
                    "kpi.target",
                    [["employee_id", "=", empId], ["period_id", "=", kpiPeriods[0].id]],
                    ["overall_achievement"],
                    { limit: 1 }
                );
                if (targets.length) {
                    this.state.kpi.achievement = Math.round(targets[0].overall_achievement || 0);
                }
            }
        } catch (e) { console.warn("kpi:", e); }

        // 7. Collections
        try {
            const collections = await this.orm.searchRead(
                "visit.collection",
                [
                    ["employee_id", "=", empId],
                    ["date", ">=", firstDay],
                    ["state", "=", "confirmed"],
                ],
                ["amount"],
                { limit: 500 }
            );
            this.state.kpi.collections = collections.reduce((s, c) => s + (c.amount || 0), 0);
        } catch (e) { console.warn("collections:", e); }
    }

    async _loadManagerData() {
        const today = new Date().toISOString().slice(0, 10);

        try {
            const employees = await this.orm.call("emp360.mobile", "get_accessible_employees", []);
            this.state.teamStats.total = employees.length;

            // Today's attendance (checked in)
            const empIds = employees.map(e => e.id);
            if (!empIds.length) return;

            const todayAtt = await this.orm.searchRead(
                "hr.attendance",
                [["employee_id", "in", empIds], ["check_in", ">=", today + " 00:00:00"]],
                ["employee_id"],
                { limit: 500 }
            );
            this.state.teamStats.active = new Set(todayAtt.map(a => a.employee_id[0])).size;

            // Today's visits
            const todayVisits = await this.orm.searchRead(
                "visit.model",
                [["employee_id", "in", empIds], ["actual_start_time", ">=", today + " 00:00:00"]],
                ["employee_id", "status"],
                { limit: 500 }
            );
            this.state.teamStats.visits_today = todayVisits.filter(v => v.status === "completed").length;

            // Top performers
            const byEmp = {};
            for (const v of todayVisits) {
                const eid  = v.employee_id[0];
                const name = v.employee_id[1];
                if (!byEmp[eid]) byEmp[eid] = { id: eid, name, visits: 0 };
                if (v.status === "completed") byEmp[eid].visits++;
            }
            this.state.topPerformers = Object.values(byEmp).sort((a, b) => b.visits - a.visits).slice(0, 5);

        } catch (e) { console.error("[MobileHome] manager data:", e); }
    }

    // ── Formatters ───────────────────────────────────────────────────────────
    _fmtHours(h) {
        const hrs  = Math.floor(h);
        const mins = Math.round((h - hrs) * 60);
        return `${hrs}h ${mins}m`;
    }

    fmtMoney(v) {
        if (!v) return "₹0";
        if (v >= 10000000) return `₹${(v / 10000000).toFixed(1)}Cr`;
        if (v >= 100000)   return `₹${(v / 100000).toFixed(1)}L`;
        if (v >= 1000)     return `₹${(v / 1000).toFixed(0)}K`;
        return `₹${Math.round(v).toLocaleString("en-IN")}`;
    }

    fmtTime(dt) {
        if (!dt) return "--:--";
        const d = typeof dt === "string" ? new Date(dt) : dt;
        return d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
    }

    get todayDateStr() {
        return new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
    }

    get beatProgressPct() {
        const { beats_completed, beats_today } = this.state.kpi;
        return beats_today > 0 ? Math.round((beats_completed / beats_today) * 100) : 0;
    }

    get achievementColor() {
        const pct = this.state.kpi.achievement;
        if (pct >= 80) return "#06d6a0";
        if (pct >= 50) return "#f77f00";
        return "#ef233c";
    }

    navigateTo(screen) {
        if (this.props.onNavigate) {
            this.props.onNavigate(screen);
        }
    }

    get greeting() {
        const h = new Date().getHours();
        if (h < 12) return "Good Morning";
        if (h < 17) return "Good Afternoon";
        return "Good Evening";
    }

    get employeeFirstName() {
        const name = this.props.employeeName || "";
        return name.split(" ")[0] || "there";
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
        let hash = 0;
        for (let i = 0; i < (str || "").length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
        return gradients[Math.abs(hash) % gradients.length];
    }
}