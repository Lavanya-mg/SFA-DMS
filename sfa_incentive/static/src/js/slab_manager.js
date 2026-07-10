/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const PAYOUT_TYPE_LABELS = {
    percentage: 'Percentage (of Target Value)',
    fixed: 'Fixed Amount',
    salary_pct: 'Salary Percentage (of Gross Salary)',
};

class SlabManager extends Component {
    static template = "sfa_incentive.SlabManager";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            slabs: [],
            stats: { total: 0, active: 0, inactive: 0 },
            filterOptions: { criteria: [], profiles: [], territories: [] },
            criteriaId: null,
            profileId: null,
            territoryId: null,
            payoutType: null,
            activeFilter: 'all',
            loading: false,
            selectedIds: [],
        });

        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.state.loading = true;
        try {
            const result = await this.orm.call(
                'sfa.incentive.dashboard', 'get_slab_manager_data', [],
                {
                    criteria_id: this.state.criteriaId || false,
                    profile_id: this.state.profileId || false,
                    territory_id: this.state.territoryId || false,
                    payout_type: this.state.payoutType || false,
                    active_filter: this.state.activeFilter,
                }
            );
            this.state.slabs = result.slabs || [];
            this.state.stats = result.stats || { total: 0, active: 0, inactive: 0 };
            if (result.filter_options) {
                this.state.filterOptions = result.filter_options;
            }
        } catch(e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add('Failed to load: ' + msg, { type: 'danger' });
        } finally {
            this.state.loading = false;
        }
    }

    // ── Filter handlers ───────────────────────────────────────────────────────

    onCriteriaChange(ev) {
        this.state.criteriaId = ev.target.value ? parseInt(ev.target.value) : null;
        this.loadData();
    }

    onProfileChange(ev) {
        this.state.profileId = ev.target.value ? parseInt(ev.target.value) : null;
        this.loadData();
    }

    onTerritoryChange(ev) {
        this.state.territoryId = ev.target.value ? parseInt(ev.target.value) : null;
        this.loadData();
    }

    onPayoutTypeChange(ev) {
        this.state.payoutType = ev.target.value || null;
        this.loadData();
    }

    setActiveFilter(filter) {
        this.state.activeFilter = filter;
        this.loadData();
    }

    // ── Actions ───────────────────────────────────────────────────────────────

    async openNewSlab() {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'New Slab',
            res_model: 'sfa.incentive.slab',
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: {},
        });
        await this.loadData();
    }

    async editSlab(slabId) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            name: 'Edit Slab',
            res_model: 'sfa.incentive.slab',
            res_id: slabId,
            view_mode: 'form',
            views: [[false, 'form']],
            target: 'new',
            context: { active_test: false },
        });
        await this.loadData();
    }

    async copySlab(slabId) {
        try {
            const newId = await this.orm.call(
                'sfa.incentive.dashboard', 'copy_slab', [slabId]
            );
            this.notification.add('Slab copied', { type: 'success' });
            await this.loadData();
            // Open the copy for editing
            await this.editSlab(newId);
        } catch(e) {
            this.notification.add((e.data && e.data.message) || e.message, { type: 'danger' });
        }
    }

    async deleteSlab(slabId, slabName) {
        if (!window.confirm(`Delete slab "${slabName}"?`)) return;
        try {
            await this.orm.call('sfa.incentive.dashboard', 'delete_slab', [slabId]);
            this.notification.add('Slab deleted', { type: 'success' });
            await this.loadData();
        } catch(e) {
            this.notification.add((e.data && e.data.message) || e.message, { type: 'danger' });
        }
    }

    async toggleActive(slabId) {
        try {
            await this.orm.call('sfa.incentive.dashboard', 'toggle_slab_active', [slabId]);
            await this.loadData();
        } catch(e) {
            this.notification.add((e.data && e.data.message) || e.message, { type: 'danger' });
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    get payoutTypeLabels() { return PAYOUT_TYPE_LABELS; }

    criteriaColor(name) {
        if (!name || name === 'Universal') return 'gray';
        const map = { 'Revenue': 'purple', 'Collection': 'green', 'New Outlets': 'blue', 'Productive Calls': 'orange' };
        return map[name] || 'gray';
    }

    profileColor(name) {
        if (!name || name === 'All') return 'gray';
        return 'pink';
    }
}

registry.category("actions").add("sfa_slab_manager", SlabManager);
