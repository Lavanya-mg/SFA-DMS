/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const RULE = "sfa.expense.policy.rule";
const CITY = "sfa.city.tier";

function emptyRule() {
    return {
        id: null, band_id: false, expense_type_id: false, duty_type_id: false,
        category: "", rate_type: "actual", rate: "",
        travel_mode_ids: [], mode_rates: {}, min_distance: "", max_distance: "",
        tier1_limit: "", tier2_limit: "", tier3_limit: "",
        receipt_required: false, receipt_threshold: "", remarks_required: false,
        auto_create: false, date_from: "", date_to: "", active: true, sequence: 10,
    };
}

class ExpensePolicyManager extends Component {
    static template = "sfa_expense_v19.ExpensePolicyManager";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            activeTab: "rules",                 // 'rules' | 'cityTiers'
            loading: false, saving: false,
            rows: [],
            filters: { band_id: "", type_id: "", duty_id: "" },
            listOptions: { bands: [], types: [], duty_types: [] },
            formOptions: { bands: [], types: [], duty_types: [], rate_types: [], mode_groups: [] },
            form: emptyRule(),
            formOpen: false,
            // City Tiers tab
            cityRows: [], cityConfigs: [], cityForm: { id: null, city: "", tier_id: false, active: true },
            cityFormOpen: false,
        });

        onWillStart(async () => {
            this.state.formOptions = await this.orm.call(RULE, "get_rule_form_options", []);
            await this.loadRules();
        });
    }

    // ── Rules list ────────────────────────────────────────────────────────────
    async loadRules() {
        this.state.loading = true;
        try {
            const f = this.state.filters;
            const res = await this.orm.call(RULE, "get_policy_manager_data", [], {
                band_id: f.band_id || false, type_id: f.type_id || false, duty_id: f.duty_id || false,
            });
            this.state.rows = res.rows || [];
            this.state.listOptions = { bands: res.bands, types: res.types, duty_types: res.duty_types };
        } catch (e) { this._err(e); } finally { this.state.loading = false; }
    }
    setFilter(key, ev) { this.state.filters[key] = ev.target.value; this.loadRules(); }

    async toggleActive(id) {
        try { await this.orm.call(RULE, "toggle_rule_active", [id]); await this.loadRules(); }
        catch (e) { this._err(e); }
    }
    async deleteRule(id) {
        if (!window.confirm("Delete this rule?")) return;
        try {
            await this.orm.call(RULE, "delete_rule", [id]);
            if (this.state.form.id === id) { this.state.form = emptyRule(); this.state.formOpen = false; }
            await this.loadRules();
        } catch (e) { this._err(e); }
    }

    // ── Rule form ─────────────────────────────────────────────────────────────
    newRule() { this.state.form = emptyRule(); this.state.formOpen = true; }
    async editRule(id) {
        try {
            const d = await this.orm.call(RULE, "get_rule_detail", [id]);
            const f = emptyRule();
            Object.assign(f, d, { travel_mode_ids: (d.travel_mode_ids || []).slice() });
            f.mode_rates = {};
            for (const mr of d.mode_rates || []) {
                f.mode_rates[mr.travel_mode_id] = {
                    rate_type: mr.rate_type || "per_km",
                    rate: mr.rate || "", max_amount: mr.max_amount || "",
                };
            }
            this.state.form = f;
            this.state.formOpen = true;
        } catch (e) { this._err(e); }
    }
    cancelForm() { this.state.form = emptyRule(); this.state.formOpen = false; }

    setField(key, value) { this.state.form[key] = value; }
    setCheck(key, ev) { this.state.form[key] = ev.target.checked; }

    onTypeChange(ev) {
        const id = ev.target.value ? parseInt(ev.target.value) : false;
        this.state.form.expense_type_id = id;
        const t = (this.state.formOptions.types || []).find(x => x.id === id);
        if (t) {
            this.state.form.rate_type = t.rate_type || "actual";
            this.state.form.receipt_required = !!t.receipt_required;
            this.state.form.remarks_required = !!t.remarks_required;
        }
    }

    // Flat lookup: mode id -> { name, group } from the grouped options.
    get modeIndex() {
        const idx = {};
        for (const g of this.state.formOptions.mode_groups || []) {
            for (const m of g.modes) idx[m.id] = { name: m.name, group: g.key };
        }
        return idx;
    }

    _defaultRateType(modeId) {
        const info = this.modeIndex[modeId];
        return info && info.group === "distance" ? "per_km" : "actual";
    }

    // Travel-mode checkboxes
    isModeSelected(modeId) { return this.state.form.travel_mode_ids.includes(modeId); }
    toggleMode(modeId, ev) {
        const arr = this.state.form.travel_mode_ids;
        if (ev.target.checked) {
            if (!arr.includes(modeId)) arr.push(modeId);
            if (!this.state.form.mode_rates[modeId]) {
                this.state.form.mode_rates = {
                    ...this.state.form.mode_rates,
                    [modeId]: { rate_type: this._defaultRateType(modeId), rate: "", max_amount: "" },
                };
            }
        } else {
            const i = arr.indexOf(modeId); if (i >= 0) arr.splice(i, 1);
        }
    }

    // One row per selected mode for the MODE RATE CONFIGURATION table.
    get selectedModeRates() {
        const idx = this.modeIndex;
        return this.state.form.travel_mode_ids.map((id) => {
            const info = idx[id] || { name: "#" + id, group: "other" };
            const mr = this.state.form.mode_rates[id] || {};
            return {
                id,
                name: info.name,
                group: info.group,
                rate_type: mr.rate_type || this._defaultRateType(id),
                rate: mr.rate ?? "",
                max_amount: mr.max_amount ?? "",
            };
        });
    }

    setModeRate(modeId, key, ev) {
        const mr = { ...(this.state.form.mode_rates[modeId] || {}) };
        mr[key] = ev.target.value;
        this.state.form.mode_rates = { ...this.state.form.mode_rates, [modeId]: mr };
    }

    // Dynamic section visibility — driven ONLY by the Expense Type's nature.
    // (Rate type can't discriminate — e.g. Fuel and Lodging are both "Actual" —
    // so travel modes / tier limits key off the type's nature, nothing else.)
    get currentNature() {
        const t = (this.state.formOptions.types || []).find(x => x.id === this.state.form.expense_type_id);
        return t ? t.nature : "";
    }
    get showTravel() { return this.currentNature === "travelling"; }
    get showTiers() { return this.currentNature === "lodging"; }

    async saveRule() {
        if (!this.state.form.band_id || !this.state.form.expense_type_id) {
            this._warn("Band and Expense Type are required.");
            return;
        }
        this.state.saving = true;
        try {
            const f = this.state.form;
            const mode_rates = f.travel_mode_ids.map((id) => {
                const mr = f.mode_rates[id] || {};
                return {
                    travel_mode_id: id,
                    rate_type: mr.rate_type || this._defaultRateType(id),
                    rate: mr.rate || 0,
                    max_amount: mr.max_amount || 0,
                };
            });
            await this.orm.call(RULE, "save_rule", [{ ...f, mode_rates }, f.id || false]);
            this.notification.add(f.id ? "Rule updated" : "Rule created", { type: "success" });
            this.state.form = emptyRule();
            this.state.formOpen = false;
            await this.loadRules();
        } catch (e) { this._err(e); } finally { this.state.saving = false; }
    }

    // ── City Tiers tab ────────────────────────────────────────────────────────
    async switchTab(tab) {
        this.state.activeTab = tab;
        if (tab === "cityTiers" && !this.state.cityConfigs.length) await this.loadCityTiers();
    }
    async loadCityTiers() {
        try {
            const res = await this.orm.call(CITY, "get_city_tier_data", []);
            this.state.cityRows = res.rows || [];
            this.state.cityConfigs = res.configs || [];
        } catch (e) { this._err(e); }
    }
    newCity() { this.state.cityForm = { id: null, city: "", tier_id: false, active: true }; this.state.cityFormOpen = true; }
    editCity(row) { this.state.cityForm = { id: row.id, city: row.city, tier_id: row.tier_id, active: row.active }; this.state.cityFormOpen = true; }
    cancelCity() { this.state.cityForm = { id: null, city: "", tier_id: false, active: true }; this.state.cityFormOpen = false; }
    setCityField(key, ev) {
        this.state.cityForm[key] = key === "active" ? ev.target.checked : ev.target.value;
    }
    async saveCity() {
        if (!this.state.cityForm.city || !this.state.cityForm.tier_id) {
            this._warn("City Name and Tier are required.");
            return;
        }
        try {
            await this.orm.call(CITY, "save_city_tier", [{ ...this.state.cityForm }, this.state.cityForm.id || false]);
            this.notification.add("City tier saved", { type: "success" });
            this.state.cityForm = { id: null, city: "", tier_id: false, active: true };
            this.state.cityFormOpen = false;
            await this.loadCityTiers();
        } catch (e) { this._err(e); }
    }
    async deleteCity(id) {
        if (!window.confirm("Delete this city tier?")) return;
        try { await this.orm.call(CITY, "delete_city_tier", [id]); await this.loadCityTiers(); }
        catch (e) { this._err(e); }
    }

    // ── Utils ─────────────────────────────────────────────────────────────────
    _err(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message) || String(e);
        this.notification.add(msg, { type: "danger" });
    }
    _warn(msg) { this.notification.add(msg, { type: "warning" }); }
}

registry.category("actions").add("sfa_expense_policy_manager", ExpensePolicyManager);
