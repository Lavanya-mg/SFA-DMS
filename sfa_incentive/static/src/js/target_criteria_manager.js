/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "sfa.target.criteria";

function emptyForm() {
    return {
        id: null,
        name: "",
        category: "",
        model_id: false,
        model_label: "",
        incentive_weight: "",
        prerequisite_criteria_id: false,
        prerequisite_min_pct: 90.0,
        operator: "count",
        aggregate_field_id: false,
        date_field_id: false,
        user_field_id: false,
        display_format: "number",
        filter_logic: "",
        filters: [],
    };
}

class TargetCriteriaManager extends Component {
    static template = "sfa_incentive.TargetCriteriaManager";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            view: "list",              // 'list' | 'wizard'
            step: 1,                   // 1..4
            loading: false,
            saving: false,

            rows: [],
            stats: { total: 0, active: 0, inactive: 0 },
            categories: [],
            activeCategory: "all",

            options: {
                models: [], categories: [], operators: [],
                display_formats: [], filter_operators: [], criteria: [],
            },
            modelFields: { all: [], numeric: [], date: [], user: [] },

            objectSearch: "",
            objectDropdownOpen: false,

            form: emptyForm(),
        });

        onWillStart(async () => {
            await Promise.all([this.loadList(), this.loadOptions()]);
        });
    }

    // ── Loaders ───────────────────────────────────────────────────────────────
    async loadList() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(MODEL, "get_manager_data", [], {
                category: this.state.activeCategory,
                active_filter: "all",
            });
            this.state.rows = res.rows || [];
            this.state.stats = res.stats || { total: 0, active: 0, inactive: 0 };
            this.state.categories = res.categories || [];
        } catch (e) {
            this._err(e);
        } finally {
            this.state.loading = false;
        }
    }

    async loadOptions() {
        try {
            this.state.options = await this.orm.call(MODEL, "get_form_options", []);
        } catch (e) {
            this._err(e);
        }
    }

    async loadModelFields(modelId) {
        if (!modelId) {
            this.state.modelFields = { all: [], numeric: [], date: [], user: [] };
            return;
        }
        try {
            this.state.modelFields = await this.orm.call(MODEL, "get_model_fields", [modelId]);
        } catch (e) {
            this._err(e);
        }
    }

    // ── Category tabs ─────────────────────────────────────────────────────────
    setCategory(cat) {
        this.state.activeCategory = cat;
        this.loadList();
    }

    // ── List actions ──────────────────────────────────────────────────────────
    async toggleActive(id) {
        try {
            await this.orm.call(MODEL, "toggle_active", [id]);
            await this.loadList();
        } catch (e) { this._err(e); }
    }

    async deleteCriteria(id, name) {
        if (!window.confirm(`Delete criteria "${name}"?`)) return;
        try {
            await this.orm.call(MODEL, "delete_criteria", [id]);
            this.notification.add("Criteria deleted", { type: "success" });
            await this.loadList();
        } catch (e) { this._err(e); }
    }

    // ── Wizard open/close ─────────────────────────────────────────────────────
    openNew() {
        this.state.form = emptyForm();
        this.state.objectSearch = "";
        this.state.modelFields = { all: [], numeric: [], date: [], user: [] };
        this.state.step = 1;
        this.state.view = "wizard";
    }

    async openEdit(id) {
        try {
            const d = await this.orm.call(MODEL, "get_criteria_detail", [id]);
            const f = emptyForm();
            Object.assign(f, {
                id: d.id, name: d.name, category: d.category,
                model_id: d.model_id, incentive_weight: d.incentive_weight,
                prerequisite_criteria_id: d.prerequisite_criteria_id,
                prerequisite_min_pct: d.prerequisite_min_pct,
                operator: d.operator, aggregate_field_id: d.aggregate_field_id,
                date_field_id: d.date_field_id, user_field_id: d.user_field_id,
                display_format: d.display_format, filter_logic: d.filter_logic,
                filters: (d.filters || []).map(x => ({ ...x })),
            });
            const m = this.state.options.models.find(x => x.id === d.model_id);
            f.model_label = m ? m.name : "";
            this.state.form = f;
            this.state.objectSearch = f.model_label;
            await this.loadModelFields(d.model_id);
            this.state.step = 1;
            this.state.view = "wizard";
        } catch (e) { this._err(e); }
    }

    backToList() {
        this.state.view = "list";
        this.loadList();
    }

    // ── Wizard step navigation ────────────────────────────────────────────────
    goToStep(n) {
        if (n > this.state.step && !this._validateUpTo(this.state.step)) return;
        this.state.step = n;
    }
    nextStep() {
        if (!this._validateUpTo(this.state.step)) return;
        if (this.state.step < 4) this.state.step += 1;
    }
    prevStep() {
        if (this.state.step > 1) this.state.step -= 1;
    }

    _validateUpTo(step) {
        const f = this.state.form;
        if (step >= 1) {
            if (!f.name || !f.name.trim()) { this._warn("Criteria Name is required."); return false; }
            if (!f.model_id) { this._warn("Search Object is required."); return false; }
        }
        if (step >= 2) {
            if (!f.operator) { this._warn("Operator is required."); return false; }
            if (f.operator === "sum" && !f.aggregate_field_id) { this._warn("SUM Field is required when Operator is SUM."); return false; }
            if (!f.date_field_id) { this._warn("Date Field is required."); return false; }
            if (!f.user_field_id) { this._warn("User Field is required."); return false; }
        }
        return true;
    }

    get canSave() {
        const f = this.state.form;
        if (!f.name || !f.name.trim() || !f.model_id) return false;
        if (!f.operator || !f.date_field_id || !f.user_field_id) return false;
        if (f.operator === "sum" && !f.aggregate_field_id) return false;
        return true;
    }

    // ── Search Object combobox ────────────────────────────────────────────────
    get filteredModels() {
        const q = (this.state.objectSearch || "").toLowerCase();
        const list = this.state.options.models || [];
        if (!q) return list.slice(0, 50);
        return list.filter(m =>
            m.name.toLowerCase().includes(q) || m.model.toLowerCase().includes(q)
        ).slice(0, 50);
    }
    onObjectInput(ev) {
        this.state.objectSearch = ev.target.value;
        this.state.objectDropdownOpen = true;
    }
    openObjectDropdown() { this.state.objectDropdownOpen = true; }
    closeObjectDropdown() {
        // small delay so a click on an option registers before closing
        setTimeout(() => { this.state.objectDropdownOpen = false; }, 150);
    }
    async selectModel(m) {
        this.state.form.model_id = m.id;
        this.state.form.model_label = m.name;
        this.state.objectSearch = m.name;
        this.state.objectDropdownOpen = false;
        // reset field mappings/filters that belonged to the previous object
        this.state.form.aggregate_field_id = false;
        this.state.form.date_field_id = false;
        this.state.form.user_field_id = false;
        this.state.form.filters = [];
        await this.loadModelFields(m.id);
    }

    // ── Generic setters (named refs — no inline-logic arrows in template) ─────
    setField(key, value) {
        this.state.form[key] = value;
    }
    setFilter(idx, key, value) {
        this.state.form.filters[idx][key] = value;
    }

    // ── Field-mapping handlers ────────────────────────────────────────────────
    onOperatorChange(ev) {
        this.state.form.operator = ev.target.value;
        if (this.state.form.operator !== "sum") this.state.form.aggregate_field_id = false;
    }

    // ── Filter rows ───────────────────────────────────────────────────────────
    addFilter() {
        this.state.form.filters.push({ field_id: false, field_label: "", operator: "=", value: "" });
    }
    removeFilter(idx) {
        this.state.form.filters.splice(idx, 1);
    }
    onFilterField(idx, ev) {
        const fid = ev.target.value ? parseInt(ev.target.value) : false;
        this.state.form.filters[idx].field_id = fid;
        const fld = this.state.modelFields.all.find(x => x.id === fid);
        this.state.form.filters[idx].field_label = fld ? fld.label : "";
    }

    // ── Save ──────────────────────────────────────────────────────────────────
    async save() {
        if (!this._validateUpTo(2)) return;
        this.state.saving = true;
        try {
            const f = this.state.form;
            const vals = {
                name: f.name.trim(),
                category: f.category || false,
                model_id: f.model_id,
                incentive_weight: parseFloat(f.incentive_weight) || 0.0,
                prerequisite_criteria_id: f.prerequisite_criteria_id || false,
                prerequisite_min_pct: parseFloat(f.prerequisite_min_pct) || 0.0,
                operator: f.operator,
                aggregate_field_id: f.operator === "sum" ? (f.aggregate_field_id || false) : false,
                date_field_id: f.date_field_id || false,
                user_field_id: f.user_field_id || false,
                display_format: f.display_format || "number",
                filter_logic: f.filter_logic || false,
                filters: (f.filters || []).filter(x => x.field_id).map(x => ({
                    field_id: x.field_id, operator: x.operator || "=", value: x.value || "",
                })),
            };
            await this.orm.call(MODEL, "save_criteria", [vals, f.id || false]);
            this.notification.add(f.id ? "Criteria updated" : "Criteria created", { type: "success" });
            this.backToList();
        } catch (e) {
            this._err(e);
        } finally {
            this.state.saving = false;
        }
    }

    // ── Preview / labels ──────────────────────────────────────────────────────
    get domainPreview() {
        const f = this.state.form;
        const rows = (f.filters || []).filter(x => x.field_id);
        if (!rows.length) return "(no filters — matches all records)";
        const setOps = { set: "is set", "not set": "is not set" };
        const lines = rows.map((r, i) => {
            const name = r.field_label || this._fieldName(r.field_id);
            if (setOps[r.operator]) return `${i + 1}. ${name} ${setOps[r.operator]}`;
            return `${i + 1}. ${name} ${r.operator} ${r.value || "''"}`;
        });
        const logic = (f.filter_logic || "").trim() ||
            rows.map((_, i) => i + 1).join(" AND ");
        return lines.join("\n") + "\n\nLogic: " + logic;
    }
    _fieldName(id) {
        const fld = this.state.modelFields.all.find(x => x.id === id);
        return fld ? fld.label : "?";
    }
    labelFor(list, value) {
        const o = (this.state.options[list] || []).find(x => (x.value ?? x.id) === value);
        return o ? (o.label ?? o.name) : "";
    }
    categoryLabel(v) { return this.labelFor("categories", v); }
    operatorLabel(v) { return this.labelFor("operators", v); }
    displayFormatLabel(v) { return this.labelFor("display_formats", v); }
    get prerequisiteLabel() {
        const c = (this.state.options.criteria || []).find(x => x.id === this.state.form.prerequisite_criteria_id);
        return c ? c.name : "";
    }
    fieldLabelById(id) {
        const fld = this.state.modelFields.all.find(x => x.id === id);
        return fld ? fld.label : "";
    }
    categoryChipClass(cat) {
        const map = {
            revenue: "tcm-chip-revenue", activity: "tcm-chip-activity",
            collection: "tcm-chip-collection", coverage: "tcm-chip-coverage",
            quality: "tcm-chip-quality", other: "tcm-chip-other",
        };
        return map[cat] || "tcm-chip-other";
    }

    // ── Utils ─────────────────────────────────────────────────────────────────
    _err(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message) || String(e);
        this.notification.add(msg, { type: "danger" });
    }
    _warn(msg) {
        this.notification.add(msg, { type: "warning" });
    }
}

registry.category("actions").add("sfa_target_criteria_manager", TargetCriteriaManager);
