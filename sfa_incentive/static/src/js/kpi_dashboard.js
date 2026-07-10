/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "sfa.target.allocation";
const GAUGE_R = 34;
const GAUGE_C = 2 * Math.PI * GAUGE_R;

class SfaKpiDashboard extends Component {
    static template = "sfa_incentive.SfaKpiDashboard";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading: false,
            view: "my",                // 'my' | 'team' | 'org'
            periodId: false,
            comparePeriodId: false,
            employeeId: false,
            periods: [],
            activeFilter: "all",
            trendChart: "line",         // 'line' | 'bar'
            critChart: "bar",           // 'bar' | 'pie'
            data: null,
        });

        onWillStart(async () => {
            const opts = await this.orm.call(MODEL, "get_options", []);
            this.state.periods = opts.periods || [];
            this.state.periodId = opts.default_period_id || false;
            this.state.employeeId = opts.default_employee_id || false;
            await this.loadData();
        });
    }

    async loadData() {
        if (!this.state.periodId || !this.state.employeeId) return;
        this.state.loading = true;
        try {
            this.state.data = await this.orm.call(MODEL, "get_kpi_dashboard", [
                this.state.view, this.state.periodId, this.state.employeeId,
                this.state.comparePeriodId || false,
            ]);
        } catch (e) {
            const msg = (e && e.data && e.data.message) || (e && e.message) || String(e);
            this.notification.add(msg, { type: "danger" });
        } finally { this.state.loading = false; }
    }

    setView(v) { this.state.view = v; this.loadData(); }
    onPeriodChange(ev) { this.state.periodId = ev.target.value ? parseInt(ev.target.value) : false; this.loadData(); }
    onCompareChange(ev) { this.state.comparePeriodId = ev.target.value ? parseInt(ev.target.value) : false; this.loadData(); }
    setFilter(f) { this.state.activeFilter = f; }
    setTrendChart(t) { this.state.trendChart = t; }
    setCritChart(t) { this.state.critChart = t; }

    // ── Derived ───────────────────────────────────────────────────────────────
    get filteredBreakdown() {
        const b = (this.state.data && this.state.data.breakdown) || [];
        if (this.state.activeFilter === "all") return b;
        return b.filter(x => x.criteria_id === this.state.activeFilter);
    }
    get maxCriteriaPct() {
        const bc = (this.state.data && this.state.data.by_criteria) || [];
        return Math.max(100, ...bc.map(x => x.pct || 0));
    }
    get maxPerformerPct() {
        const tp = (this.state.data && this.state.data.top_performers) || [];
        return Math.max(100, ...tp.map(x => x.pct || 0));
    }

    // ── Gauge / bar helpers ───────────────────────────────────────────────────
    gaugeDash(pct) {
        const filled = Math.min(Math.max(pct, 0), 100) / 100 * GAUGE_C;
        return `${filled} ${GAUGE_C - filled}`;
    }
    gaugeColorClass(pct) {
        if (pct >= 100) return "kdb-stroke-green";
        if (pct >= 50) return "kdb-stroke-orange";
        return "kdb-stroke-red";
    }
    textColorClass(pct) {
        if (pct >= 100) return "kdb-green";
        if (pct >= 50) return "kdb-orange";
        return "kdb-red";
    }
    barColorClass(pct) {
        if (pct >= 100) return "kdb-bar-green";
        if (pct >= 50) return "kdb-bar-orange";
        return "kdb-bar-red";
    }
    critBarWidth(pct) { return Math.min((pct / this.maxCriteriaPct) * 100, 100); }
    perfBarWidth(pct) { return Math.min((pct / this.maxPerformerPct) * 100, 100); }

    // Indian-style short number: 130000 → "1.3L", 50000 → "50.0K"
    fmt(n) {
        n = Number(n) || 0;
        const a = Math.abs(n);
        if (a >= 1e7) return (n / 1e7).toFixed(1) + "Cr";
        if (a >= 1e5) return (n / 1e5).toFixed(1) + "L";
        if (a >= 1e3) return (n / 1e3).toFixed(1) + "K";
        return String(Math.round(n));
    }

    // ── Performance-trend SVG geometry ────────────────────────────────────────
    get trend() { return (this.state.data && this.state.data.trend) || []; }
    _points(key) {
        const t = this.trend;
        if (t.length < 1) return "";
        const W = 600, H = 200, padL = 40, padR = 15, padT = 15, padB = 28;
        const max = Math.max(1, ...t.map(p => Math.max(p.target, p.achievement)));
        const n = t.length;
        const span = n > 1 ? (W - padL - padR) / (n - 1) : 0;
        return t.map((p, i) => {
            const x = padL + i * span;
            const y = (H - padB) - (p[key] / max) * (H - padT - padB);
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(" ");
    }
    get targetPoints() { return this._points("target"); }
    get achievementPoints() { return this._points("achievement"); }
    _dots(key) {
        const t = this.trend;
        const W = 600, H = 200, padL = 40, padR = 15, padT = 15, padB = 28;
        const max = Math.max(1, ...t.map(p => Math.max(p.target, p.achievement)));
        const n = t.length;
        const span = n > 1 ? (W - padL - padR) / (n - 1) : 0;
        return t.map((p, i) => ({
            x: padL + i * span,
            y: (H - padB) - (p[key] / max) * (H - padT - padB),
        }));
    }
    get targetDots() { return this._dots("target"); }
    get achievementDots() { return this._dots("achievement"); }
    _area(key) {
        const pts = this._points(key);
        if (!pts) return "";
        const d = this._dots(key);
        const baseY = 172;   // H(200) - padB(28)
        return `${pts} ${d[d.length - 1].x.toFixed(1)},${baseY} ${d[0].x.toFixed(1)},${baseY}`;
    }
    get targetArea() { return this._area("target"); }
    get achievementArea() { return this._area("achievement"); }
    get trendLabels() {
        const t = this.trend;
        const W = 600, padL = 40, padR = 15;
        const n = t.length;
        const span = n > 1 ? (W - padL - padR) / (n - 1) : 0;
        return t.map((p, i) => ({ label: p.label, x: padL + i * span }));
    }

    // Grouped target/achievement bars for the Performance Trend "bar" mode.
    get trendBars() {
        const t = this.trend;
        if (!t.length) return [];
        const W = 600, H = 200, padL = 40, padR = 15, padT = 15, padB = 28;
        const plotW = W - padL - padR, plotH = H - padT - padB, baseY = H - padB;
        const max = Math.max(1, ...t.map(p => Math.max(p.target, p.achievement)));
        const gw = plotW / t.length;
        const bw = Math.min(20, gw * 0.3);
        return t.map((p, i) => {
            const cx = padL + i * gw + gw / 2;
            const th = (p.target / max) * plotH, ah = (p.achievement / max) * plotH;
            return {
                label: p.label, bw,
                tx: cx - bw - 2, ty: baseY - th, th,
                ax: cx + 2, ay: baseY - ah, ah,
                labelX: cx,
            };
        });
    }

    // Pie slices for the Achievement by Criteria "pie" mode (sliced by actual value).
    get critPie() {
        const items = ((this.state.data && this.state.data.breakdown) || [])
            .filter(x => (x.actual || 0) > 0);
        const total = items.reduce((s, x) => s + (x.actual || 0), 0);
        if (!total) return [];
        const cx = 100, cy = 100, r = 82;
        const pal = ['#4b2fd6', '#16a34a', '#f59e0b', '#2563eb', '#e5227a',
                     '#0891b2', '#7c3aed', '#dc2626', '#059669', '#d97706'];
        let a0 = -Math.PI / 2;
        return items.map((x, i) => {
            const frac = (x.actual || 0) / total;
            const a1 = a0 + frac * 2 * Math.PI;
            let d;
            if (items.length === 1) {
                // single slice → full circle (two half arcs)
                d = `M${cx},${(cy - r).toFixed(1)} A${r},${r} 0 1 1 ${(cx - 0.01).toFixed(2)},${(cy - r).toFixed(1)} Z`;
            } else {
                const large = frac > 0.5 ? 1 : 0;
                const x0 = cx + r * Math.cos(a0), y0 = cy + r * Math.sin(a0);
                const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
                d = `M${cx},${cy} L${x0.toFixed(1)},${y0.toFixed(1)} A${r},${r} 0 ${large} 1 ${x1.toFixed(1)},${y1.toFixed(1)} Z`;
            }
            a0 = a1;
            return { d, color: pal[i % pal.length], name: x.name, pct: Math.round(frac * 100) };
        });
    }
}

registry.category("actions").add("sfa_kpi_dashboard", SfaKpiDashboard);
