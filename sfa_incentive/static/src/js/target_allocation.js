/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "sfa.target.allocation";

class TargetAllocation extends Component {
    static template = "sfa_incentive.TargetAllocation";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading: false,
            syncing: false,
            periodId: false,
            employeeId: false,
            periods: [],
            employees: [],
            rows: [],
            hasSubordinates: false,
            lastSync: false,
            modal: "none",              // 'none' | 'addTarget' | 'distribute'
            addTargets: {},             // { criteria_id: value }
            distribute: { criteria: [], executives: [], manager_targets: {} },
        });

        onWillStart(async () => {
            const opts = await this.orm.call(MODEL, "get_options", []);
            this.state.periods = opts.periods || [];
            this.state.employees = opts.employees || [];
            this.state.periodId = opts.default_period_id || false;
            this.state.employeeId = opts.default_employee_id || false;
            await this.loadData();
        });
    }

    // ── Data ──────────────────────────────────────────────────────────────────
    async loadData() {
        if (!this.state.periodId || !this.state.employeeId) {
            this.state.rows = [];
            return;
        }
        this.state.loading = true;
        try {
            const res = await this.orm.call(MODEL, "get_allocation_data",
                [this.state.periodId, this.state.employeeId]);
            this.state.rows = res.rows || [];
            this.state.hasSubordinates = res.has_subordinates || false;
            this.state.lastSync = res.last_sync || false;
        } catch (e) { this._err(e); } finally { this.state.loading = false; }
    }

    onPeriodChange(ev) {
        this.state.periodId = ev.target.value ? parseInt(ev.target.value) : false;
        this.loadData();
    }
    onEmployeeChange(ev) {
        this.state.employeeId = ev.target.value ? parseInt(ev.target.value) : false;
        this.loadData();
    }

    // ── Sync achievements (runs the criteria queries) ─────────────────────────
    async syncAchievements() {
        if (!this.state.periodId || !this.state.employeeId) {
            this._warn("Select a period and user first.");
            return;
        }
        this.state.syncing = true;
        try {
            await this.orm.call(MODEL, "sync_achievements",
                [this.state.periodId, this.state.employeeId]);
            this.notification.add("Achievements synced", { type: "success" });
            await this.loadData();
        } catch (e) { this._err(e); } finally { this.state.syncing = false; }
    }

    // ── Add / Edit Targets modal ──────────────────────────────────────────────
    openAddTarget() {
        if (!this.state.periodId || !this.state.employeeId) {
            this._warn("Select a period and user first.");
            return;
        }
        const t = {};
        for (const r of this.state.rows) t[r.criteria_id] = r.target_individual || 0;
        this.state.addTargets = t;
        this.state.modal = "addTarget";
    }
    setAddTarget(critId, ev) {
        this.state.addTargets[critId] = ev.target.value;
    }
    async saveTargets() {
        try {
            await this.orm.call(MODEL, "save_targets",
                [this.state.periodId, this.state.employeeId, this.state.addTargets]);
            this.notification.add("Targets saved", { type: "success" });
            this.closeModal();
            await this.loadData();
        } catch (e) { this._err(e); }
    }

    // ── Distribute modal ──────────────────────────────────────────────────────
    async openDistribute() {
        if (!this.state.periodId || !this.state.employeeId) {
            this._warn("Select a period and user first.");
            return;
        }
        try {
            this.state.distribute = await this.orm.call(MODEL, "get_distribute_data",
                [this.state.periodId, this.state.employeeId]);
            this.state.modal = "distribute";
        } catch (e) { this._err(e); }
    }
    setDistribute(execIdx, critId, ev) {
        this.state.distribute.executives[execIdx].values[critId] = ev.target.value;
    }
    async saveDistribution() {
        const dist = {};
        for (const ex of this.state.distribute.executives) {
            dist[ex.id] = {};
            for (const c of this.state.distribute.criteria) {
                dist[ex.id][c.id] = ex.values[c.id] || 0;
            }
        }
        try {
            await this.orm.call(MODEL, "save_distribution",
                [this.state.periodId, this.state.employeeId, dist]);
            this.notification.add("Distribution saved", { type: "success" });
            this.closeModal();
            await this.loadData();
        } catch (e) { this._err(e); }
    }

    closeModal() { this.state.modal = "none"; }

    // ── Progress bar helpers ──────────────────────────────────────────────────
    barClass(pct) {
        if (pct >= 100) return "tal-bar-green";
        if (pct >= 50) return "tal-bar-orange";
        return "tal-bar-red";
    }
    barTextClass(pct) {
        if (pct >= 100) return "tal-green";
        if (pct >= 50) return "tal-orange";
        return "tal-red";
    }
    barWidth(pct) { return Math.min(Math.max(pct, 0), 100); }
    fmt(v) {
        const n = Number(v) || 0;
        return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }

    // ── Utils ─────────────────────────────────────────────────────────────────
    _err(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message) || String(e);
        this.notification.add(msg, { type: "danger" });
    }
    _warn(msg) { this.notification.add(msg, { type: "warning" }); }
}

registry.category("actions").add("sfa_target_allocation", TargetAllocation);
