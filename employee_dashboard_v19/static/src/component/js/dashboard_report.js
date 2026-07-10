/** @odoo-module **/

import { Component, onMounted, onPatched, onWillUnmount, useState, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ─────────────────────────────────────────────────────────────────
//  Colour palette
// ─────────────────────────────────────────────────────────────────
const C = {
    blue:   "#4361ee",
    indigo: "#3a0ca3",
    purple: "#7209b7",
    pink:   "#f72585",
    cyan:   "#4cc9f0",
    green:  "#06d6a0",
    yellow: "#ffd166",
    red:    "#ef476f",
    teal:   "#0077b6",
    dark:   "#073b4c",
    orange: "#f77f00",
    violet: "#560bad",
};

const PALETTE      = Object.values(C);
const STATUS_COLOR = {
    completed:   C.green,
    planned:     C.blue,
    in_progress: C.yellow,
    cancelled:   C.red,
};

// ─────────────────────────────────────────────────────────────────
//  Chart helpers
// ─────────────────────────────────────────────────────────────────
const TOOLTIP_DEFAULTS = {
    backgroundColor: "rgba(15,20,50,0.92)",
    titleColor:      "#ffffff",
    bodyColor:       "rgba(255,255,255,0.85)",
    borderColor:     "rgba(255,255,255,0.1)",
    borderWidth:     1,
    padding:         12,
    cornerRadius:    10,
};

function destroyChart(map, key) {
    if (map[key]) { try { map[key].destroy(); } catch (_) {} delete map[key]; }
}

function makeChart(ctx, cfg) {
    // eslint-disable-next-line no-undef
    return new Chart(ctx, cfg);
}

// ─────────────────────────────────────────────────────────────────
//  Main OWL Component
// ─────────────────────────────────────────────────────────────────
export class DashboardReport extends Component {

    static template = "employee_dashboard_v19.DashboardReport";

    setup() {
        this.orm          = useService("orm");
        this.action       = useService("action");
        this.notification = useService("notification");

        // ── canvas refs ──────────────────────────────────────────
        this.canvasRefs = {
            visitStatus:       useRef("canvasVisitStatus"),
            visitProductivity: useRef("canvasVisitProductivity"),
            employeeVisits:    useRef("canvasEmployeeVisits"),
            monthlyVisits:     useRef("canvasMonthlyVisits"),
            attendance:        useRef("canvasAttendance"),
            monthlyAttendance: useRef("canvasMonthlyAttendance"),
            beatCoverage:      useRef("canvasBeatCoverage"),
            beatSwitchDist:    useRef("canvasBeatSwitchDist"),
            employeeSwitches:  useRef("canvasEmployeeSwitches"),
            pjpStatus:         useRef("canvasPjpStatus"),
            
        };

        this.charts          = {};
        this._pendingChart   = null;

        // ── reactive state ───────────────────────────────────────
        this.state = useState({
            loading:      true,
            data:         {
                kpi: { total_visits: 0, completed_visits: 0, productive_visits: 0, total_order_amount: 0, total_attendance: 0, total_worked_hours: 0, total_beats: 0, total_beat_reports: 0, total_switches: 0, total_switch_history: 0, total_pjp: 0, approved_pjp: 0, active_pjp: 0 },
                visit_status: { labels: [], data: [] },
                visit_productivity: { labels: [], data: [] },
                employee_visits: { labels: [], counts: [] },
                monthly_visits: { labels: [], completed: [], planned: [], in_progress: [], cancelled: [] },
                attendance: { labels: [], hours: [] },
                monthly_attendance: { labels: [], hours: [] },
                beat_coverage: { labels: [], data: [] },
                beat_switch_dist: { labels: [], data: [] },
                employee_switches: { labels: [], counts: [] },
                pjp_status: { labels: [], data: [] },
                recent_visits: [],
                recent_beat_reports: [],
                recent_switch_history: [],
            },
            employees:    [],
            departments:  [],
            dateFrom:     this._firstDayOfMonth(),
            dateTo:       this._today(),
            employeeId:   null,
            departmentId: null,
            activeTab:    "visits",
            activePreset: "month",
            generating:   false,
        });

        onMounted(async () => {
            await this._loadFilterOptions();
            await this._loadData();
        });

        onPatched(() => {
            if (this._pendingChart) {
                const d = this._pendingChart;
                this._pendingChart = null;
                this._renderCharts(d);
            }
        });

        onWillUnmount(() => {
            Object.keys(this.charts).forEach(k => destroyChart(this.charts, k));
        });
    }

    // ── Date helpers ─────────────────────────────────────────────
    _today() {
        return new Date().toISOString().split("T")[0];
    }

    _firstDayOfMonth() {
        const d = new Date();
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
    }

    _formatDisplayDate(iso) {
        if (!iso) return "";
        const [y, m, day] = iso.split("-");
        const months = ["Jan","Feb","Mar","Apr","May","Jun",
                        "Jul","Aug","Sep","Oct","Nov","Dec"];
        return `${parseInt(day, 10)} ${months[parseInt(m, 10) - 1]} ${y}`;
    }

    formatDateRange() {
        return `${this._formatDisplayDate(this.state.dateFrom)} – ${this._formatDisplayDate(this.state.dateTo)}`;
    }

    // ── Data loading ─────────────────────────────────────────────
    async _loadFilterOptions() {
        try {
            const opts = await this.orm.call("dashboard.report", "get_filter_options", []);
            this.state.employees   = opts.employees   || [];
            this.state.departments = opts.departments || [];
        } catch (e) {
            console.error("DashboardReport: filter options failed", e);
        }
    }

    async _loadData() {
        this.state.loading = true;
        Object.keys(this.charts).forEach(k => destroyChart(this.charts, k));

        try {
            const args = [
                this.state.dateFrom     || false,
                this.state.dateTo       || false,
                this.state.employeeId   ? parseInt(this.state.employeeId,   10) : false,
                this.state.departmentId ? parseInt(this.state.departmentId, 10) : false,
            ];
            const data = await this.orm.call("dashboard.report", "get_dashboard_data", args);
            this._pendingChart = data;
            this.state.data = {
                ...this.state.data,
                ...data,
                recent_beat_reports:   data.recent_beat_reports   || [],
                recent_switch_history: data.recent_switch_history || [],
                recent_visits:         data.recent_visits         || [],
            };
            this.state.loading = false;
        } catch (e) {
            this.state.loading = false;
            console.error("DashboardReport: get_dashboard_data failed", e);
            this.notification.add(
                "Failed to load dashboard data. Please check your permissions or try again.",
                { type: "danger" }
            );
        }
    }

    // ── Chart rendering ───────────────────────────────────────────
    _renderCharts(data) {
        this._renderDoughnut("visitStatus",       data.visit_status,            "Visit Status");
        this._renderDoughnut("visitProductivity", data.visit_productivity,       "Productivity");
        this._renderBarH(    "employeeVisits",    data.employee_visits.labels,   data.employee_visits.counts,  "Visits",  PALETTE);
        this._renderMonthlyVisits(data.monthly_visits);
        this._renderBarH(    "attendance",        data.attendance.labels,        data.attendance.hours,        "Hours",   PALETTE);
        this._renderBarV(    "monthlyAttendance", data.monthly_attendance.labels, data.monthly_attendance.hours,"Worked Hours", C.teal);
        this._renderDoughnut("beatCoverage",      data.beat_coverage,            "Beat Coverage");
        this._renderDoughnut("beatSwitchDist",    data.beat_switch_dist,         "Switch Distribution");
        this._renderBarH(    "employeeSwitches",  data.employee_switches.labels, data.employee_switches.counts,"Switches", PALETTE);
        this._renderDoughnut("pjpStatus",         data.pjp_status,              "PJP Status");
    }

    _getCtx(key) {
        const ref = this.canvasRefs[key];
        return ref && ref.el ? ref.el.getContext("2d") : null;
    }

    // Doughnut / donut chart
    _renderDoughnut(key, payload, title) {
        destroyChart(this.charts, key);
        const ctx = this._getCtx(key);
        if (!ctx || !payload || !payload.labels || !payload.labels.length) return;

        this.charts[key] = makeChart(ctx, {
            type: "doughnut",
            data: {
                labels:   payload.labels,
                datasets: [{
                    data:            payload.data,
                    backgroundColor: PALETTE.slice(0, payload.labels.length),
                    borderWidth:     3,
                    borderColor:     "#ffffff",
                    hoverOffset:     8,
                    hoverBorderWidth: 4,
                }],
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                cutout:              "62%",
                animation:           { animateRotate: true, duration: 700 },
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            padding:         14,
                            font:            { size: 11, weight: "600" },
                            usePointStyle:   true,
                            pointStyleWidth: 8,
                            color:           "#4b5563",
                        },
                    },
                    tooltip: {
                        ...TOOLTIP_DEFAULTS,
                        callbacks: {
                            label: ctx => {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct   = total > 0 ? Math.round(ctx.parsed / total * 100) : 0;
                                return ` ${ctx.label}: ${ctx.parsed} (${pct}%)`;
                            },
                        },
                    },
                },
            },
        });
    }

    // Stacked bar – monthly visits
    _renderMonthlyVisits(mv) {
        destroyChart(this.charts, "monthlyVisits");
        const ctx = this._getCtx("monthlyVisits");
        if (!ctx || !mv || !mv.labels || !mv.labels.length) return;

        const sets = [
            { key: "completed",   label: "Completed",   col: STATUS_COLOR.completed   },
            { key: "planned",     label: "Planned",     col: STATUS_COLOR.planned     },
            { key: "in_progress", label: "In Progress", col: STATUS_COLOR.in_progress },
            { key: "cancelled",   label: "Cancelled",   col: STATUS_COLOR.cancelled   },
        ];

        this.charts["monthlyVisits"] = makeChart(ctx, {
            type: "bar",
            data: {
                labels:   mv.labels,
                datasets: sets.map(s => ({
                    label:           s.label,
                    data:            mv[s.key] || [],
                    backgroundColor: s.col + "d5",
                    borderColor:     s.col,
                    borderWidth:     0,
                    borderRadius:    4,
                    borderSkipped:   false,
                })),
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 600 },
                plugins: {
                    legend: {
                        position: "top",
                        labels: {
                            font:            { size: 11, weight: "600" },
                            usePointStyle:   true,
                            pointStyleWidth: 8,
                            padding:         18,
                        },
                    },
                    tooltip: {
                        ...TOOLTIP_DEFAULTS,
                        mode:      "index",
                        intersect: false,
                    },
                },
                scales: {
                    x: { stacked: true, grid: { display: false }, ticks: { font: { size: 11 } } },
                    y: {
                        stacked:     true,
                        beginAtZero: true,
                        ticks:       { precision: 0, font: { size: 11 } },
                        grid:        { color: "rgba(0,0,0,0.05)" },
                    },
                },
            },
        });
    }

    // Horizontal bar chart
    _renderBarH(key, labels, data, title, colors) {
        destroyChart(this.charts, key);
        const ctx = this._getCtx(key);
        if (!ctx || !labels || !labels.length) return;

        const bg = Array.isArray(colors)
            ? colors.slice(0, labels.length).map(c => c + "cc")
            : (colors + "cc");
        const border = Array.isArray(colors)
            ? colors.slice(0, labels.length)
            : colors;

        this.charts[key] = makeChart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label:           title,
                    data,
                    backgroundColor: bg,
                    borderColor:     border,
                    borderWidth:     0,
                    borderRadius:    5,
                    borderSkipped:   false,
                }],
            },
            options: {
                indexAxis:           "y",
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 600 },
                plugins: {
                    legend:  { display: false },
                    tooltip: { ...TOOLTIP_DEFAULTS },
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks:       { precision: 0, font: { size: 11 } },
                        grid:        { color: "rgba(0,0,0,0.05)" },
                    },
                    y: {
                        grid:  { display: false },
                        ticks: { font: { size: 11 }, color: "#374151" },
                    },
                },
            },
        });
    }

    // Vertical bar chart
    _renderBarV(key, labels, data, title, color) {
        destroyChart(this.charts, key);
        const ctx = this._getCtx(key);
        if (!ctx || !labels || !labels.length) return;

        const col = color || C.blue;
        this.charts[key] = makeChart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label:           title,
                    data,
                    backgroundColor: col + "cc",
                    borderColor:     col,
                    borderWidth:     0,
                    borderRadius:    5,
                    borderSkipped:   false,
                }],
            },
            options: {
                responsive:          true,
                maintainAspectRatio: false,
                animation:           { duration: 600 },
                plugins: {
                    legend:  { display: false },
                    tooltip: { ...TOOLTIP_DEFAULTS },
                },
                scales: {
                    x: { grid: { display: false }, ticks: { font: { size: 11 } } },
                    y: {
                        beginAtZero: true,
                        ticks:       { font: { size: 11 } },
                        grid:        { color: "rgba(0,0,0,0.05)" },
                    },
                },
            },
        });
    }

    

    // ── UI Event Handlers ─────────────────────────────────────────
    onDateFromChange(ev) {
        this.state.dateFrom     = ev.target.value;
        this.state.activePreset = "custom";
    }

    onDateToChange(ev) {
        this.state.dateTo       = ev.target.value;
        this.state.activePreset = "custom";
    }

    onEmployeeChange(ev)   { this.state.employeeId   = ev.target.value || null; }
    onDepartmentChange(ev) { this.state.departmentId = ev.target.value || null; }

    async onApplyFilters() { await this._loadData(); }

    async onResetFilters() {
        this.state.dateFrom     = this._firstDayOfMonth();
        this.state.dateTo       = this._today();
        this.state.employeeId   = null;
        this.state.departmentId = null;
        this.state.activePreset = "month";
        await this._loadData();
    }

    async setDatePreset(preset) {
        this.state.activePreset = preset;
        const today = this._today();

        if (preset === "today") {
            this.state.dateFrom = today;
            this.state.dateTo   = today;

        } else if (preset === "week") {
            const d  = new Date();
            const dd = new Date(d);
            dd.setDate(d.getDate() - ((d.getDay() + 6) % 7)); // Monday
            this.state.dateFrom = dd.toISOString().split("T")[0];
            this.state.dateTo   = today;

        } else if (preset === "month") {
            this.state.dateFrom = this._firstDayOfMonth();
            this.state.dateTo   = today;

        } else if (preset === "lastmonth") {
            const d     = new Date();
            const first = new Date(d.getFullYear(), d.getMonth(), 1);
            const last  = new Date(first - 1);
            const lf    = new Date(last.getFullYear(), last.getMonth(), 1);
            this.state.dateFrom = lf.toISOString().split("T")[0];
            this.state.dateTo   = last.toISOString().split("T")[0];

        } else if (preset === "quarter") {
            const d  = new Date();
            const qs = new Date(d.getFullYear(), Math.floor(d.getMonth() / 3) * 3, 1);
            this.state.dateFrom = qs.toISOString().split("T")[0];
            this.state.dateTo   = today;
        }

        await this._loadData();
    }

    setActiveTab(tab) { this.state.activeTab = tab; }

    async onGenerateReport() {
        this.state.generating = true;
        try {
            await this.action.doAction(
                "employee_dashboard_v19.action_executive_beat_report_wizard"
            );
        } catch (e) {
            this.notification.add("Could not open the report wizard.", { type: "warning" });
        } finally {
            this.state.generating = false;
        }
    }

    async onRefresh() {
        await this._loadData();
    }

    // ── Formatting helpers ────────────────────────────────────────
    formatCurrency(val, symbol) {
        if (val === null || val === undefined) return "—";
        return `${symbol || ""}${Number(val).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
        })}`;
    }

    formatHours(val) {
        if (val === null || val === undefined) return "—";
        const h = Math.floor(val);
        const m = Math.round((val - h) * 60);
        return `${h}h ${String(m).padStart(2, "0")}m`;
    }

    formatNumber(val) {
        if (val === null || val === undefined) return "0";
        return Number(val).toLocaleString();
    }

    productivityRate(data) {
        if (!data || !data.kpi || !data.kpi.total_visits) return 0;
        return Math.round(data.kpi.productive_visits / data.kpi.total_visits * 100);
    }

    completionRate(data) {
        if (!data || !data.kpi || !data.kpi.total_visits) return 0;
        return Math.round(data.kpi.completed_visits / data.kpi.total_visits * 100);
    }

    switchRate(data) {
        if (!data || !data.kpi || !data.kpi.total_beat_reports) return 0;
        const withSwitch = data.beat_switch_dist &&
            data.beat_switch_dist.data && data.beat_switch_dist.data[0]
            ? data.beat_switch_dist.data[0] : 0;
        return Math.round(withSwitch / data.kpi.total_beat_reports * 100);
    }

    statusBadgeClass(status) {
        const map = {
            completed:        "badge-dr-success",
            planned:          "badge-dr-info",
            in_progress:      "badge-dr-warning",
            cancelled:        "badge-dr-danger",
            Productive:       "badge-dr-success",
            "Non-Productive": "badge-dr-danger",
        };
        return "badge-dr " + (map[status] || "badge-dr-secondary");
    }

    switchBadgeClass(count) {
        if (count === 0) return "badge-dr badge-dr-success";
        if (count <= 1)  return "badge-dr badge-dr-warning";
        return "badge-dr badge-dr-danger";
    }

    // Return CSS width% for a progress bar (0-100)
    progressWidth(val, max) {
        if (!max || !val) return "0%";
        return Math.min(Math.round(val / max * 100), 100) + "%";
    }
}

registry.category("actions").add(
    "employee_dashboard.dashboard_report_action",
    DashboardReport
);

