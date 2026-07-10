/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const MODEL = "kpi.metric";

function emptyForm() {
    return {
        id: null, name: "", key: "", display_label: "", category: "sales",
        model_id: false, model_label: "", aggregation: "count",
        date_field_id: false, aggregate_field_id: false, user_field_id: false,
        display_format: "number", icon: "", card_color: "#0176d3",
        raw_filter: "", description: "", sort_order: 10, active: true, allow_forecast: false,
    };
}

class KpiMetricManager extends Component {
    static template = "kpi_target_v19.KpiMetricManager";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading: false, saving: false,
            rows: [],
            options: { models: [], categories: [], aggregations: [], display_formats: [] },
            modelFields: { all: [], numeric: [], date: [], user: [] },
            modal: "none",
            form: emptyForm(),
            objectSearch: "",
            objectDropdownOpen: false,
        });

        onWillStart(async () => {
            await Promise.all([this.loadList(), this.loadOptions()]);
        });
    }

    // ── Loaders ───────────────────────────────────────────────────────────────
    async loadList() {
        this.state.loading = true;
        try {
            const res = await this.orm.call(MODEL, "get_manager_data", []);
            this.state.rows = res.rows || [];
        } catch (e) { this._err(e); } finally { this.state.loading = false; }
    }
    async loadOptions() {
        try { this.state.options = await this.orm.call(MODEL, "get_form_options", []); }
        catch (e) { this._err(e); }
    }
    async loadModelFields(modelId) {
        if (!modelId) { this.state.modelFields = { all: [], numeric: [], date: [], user: [] }; return; }
        try { this.state.modelFields = await this.orm.call(MODEL, "get_model_fields", [modelId]); }
        catch (e) { this._err(e); }
    }

    // ── List actions ──────────────────────────────────────────────────────────
    async toggleActive(id) {
        try { await this.orm.call(MODEL, "toggle_active", [id]); await this.loadList(); }
        catch (e) { this._err(e); }
    }
    async deleteMetric(id, name) {
        if (!window.confirm(`Delete metric "${name}"?`)) return;
        try {
            await this.orm.call(MODEL, "delete_metric", [id]);
            this.notification.add("Metric deleted", { type: "success" });
            await this.loadList();
        } catch (e) { this._err(e); }
    }

    // ── Modal open/close ──────────────────────────────────────────────────────
    openNew() {
        this.state.form = emptyForm();
        this.state.objectSearch = "";
        this.state.modelFields = { all: [], numeric: [], date: [], user: [] };
        this.state.modal = "form";
    }
    async openEdit(id) {
        try {
            const d = await this.orm.call(MODEL, "get_metric_detail", [id]);
            const f = emptyForm();
            Object.assign(f, d);
            const m = this.state.options.models.find(x => x.id === d.model_id);
            f.model_label = m ? m.name : "";
            this.state.form = f;
            this.state.objectSearch = f.model_label;
            await this.loadModelFields(d.model_id);
            this.state.modal = "form";
        } catch (e) { this._err(e); }
    }
    closeModal() { this.state.modal = "none"; }

    // ── Setters / handlers ────────────────────────────────────────────────────
    setField(key, value) { this.state.form[key] = value; }
    onAggregationChange(ev) {
        this.state.form.aggregation = ev.target.value;
        if (this.state.form.aggregation !== "sum") this.state.form.aggregate_field_id = false;
    }

    // ── Source Object combobox ────────────────────────────────────────────────
    get filteredModels() {
        const q = (this.state.objectSearch || "").toLowerCase();
        const list = this.state.options.models || [];
        if (!q) return list.slice(0, 50);
        return list.filter(m => m.name.toLowerCase().includes(q) || m.model.toLowerCase().includes(q)).slice(0, 50);
    }
    onObjectInput(ev) { this.state.objectSearch = ev.target.value; this.state.objectDropdownOpen = true; }
    openObjectDropdown() { this.state.objectDropdownOpen = true; }
    closeObjectDropdown() { setTimeout(() => { this.state.objectDropdownOpen = false; }, 150); }
    async selectModel(m) {
        this.state.form.model_id = m.id;
        this.state.form.model_label = m.name;
        this.state.objectSearch = m.name;
        this.state.objectDropdownOpen = false;
        this.state.form.date_field_id = false;
        this.state.form.aggregate_field_id = false;
        this.state.form.user_field_id = false;
        await this.loadModelFields(m.id);
    }

    // ── Save ──────────────────────────────────────────────────────────────────
    get canSave() {
        const f = this.state.form;
        if (!f.name || !f.name.trim() || !f.key || !f.key.trim()) return false;
        if (!f.display_label || !f.display_label.trim()) return false;
        if (!f.model_id || !f.aggregation || !f.date_field_id || !f.display_format) return false;
        if (f.aggregation === "sum" && !f.aggregate_field_id) return false;
        return true;
    }
    async save() {
        if (!this.canSave) { this._warn("Please fill all required (*) fields."); return; }
        if (/\s/.test(this.state.form.key)) { this._warn("Metric Key cannot contain spaces."); return; }
        this.state.saving = true;
        try {
            const f = this.state.form;
            await this.orm.call(MODEL, "save_metric", [{ ...f }, f.id || false]);
            this.notification.add(f.id ? "Metric updated" : "Metric created", { type: "success" });
            this.closeModal();
            await this.loadList();
        } catch (e) { this._err(e); } finally { this.state.saving = false; }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────
    categoryChipClass(cat) {
        const map = {
            sales: "kmm-chip-sales", visits: "kmm-chip-visits", outlets: "kmm-chip-outlets",
            collections: "kmm-chip-collections", other: "kmm-chip-other",
        };
        return map[cat] || "kmm-chip-other";
    }
    _err(e) {
        const msg = (e && e.data && e.data.message) || (e && e.message) || String(e);
        this.notification.add(msg, { type: "danger" });
    }
    _warn(msg) { this.notification.add(msg, { type: "warning" }); }
}

registry.category("actions").add("kpi_metric_manager", KpiMetricManager);
