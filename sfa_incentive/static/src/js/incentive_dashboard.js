/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const TABS = [
    { key: 'all', label: 'All' },
    { key: 'calculated', label: 'Calculated' },
    { key: 'pending_approval', label: 'Pending Approval' },
    { key: 'approved', label: 'Approved' },
    { key: 'rejected', label: 'Rejected' },
    { key: 'paid', label: 'Paid' },
];

const STATUS_LABELS = {
    calculated: 'Calculated',
    pending_approval: 'Pending Approval',
    approved: 'Approved',
    rejected: 'Rejected',
    paid: 'Paid',
};

const EMPTY_STATS = {
    calculated: { count: 0, amount: 0 },
    pending_approval: { count: 0, amount: 0 },
    approved: { count: 0, amount: 0 },
    paid: { count: 0, amount: 0 },
};

class IncentiveDashboard extends Component {
    static template = "sfa_incentive.IncentiveDashboard";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        const now = new Date();
        this.state = useState({
            periods: [],
            periodId: null,
            // Legacy fallback month/year
            month: now.getMonth() + 1,
            year: now.getFullYear(),
            tabs: TABS,
            activeTab: 'all',
            criteriaId: null,
            profileId: null,
            territoryId: null,
            filterOptions: { criteria: [], profiles: [], territories: [] },
            records: [],
            stats: { ...EMPTY_STATS },
            loading: false,
            calculating: false,
            toast: null,
        });

        onWillStart(async () => {
            await this.loadPeriods();
            await this.loadData();
        });
    }

    async loadPeriods() {
        try {
            const periods = await this.orm.call(
                'sfa.incentive.dashboard', 'get_periods', []
            );
            if (periods && periods.length) {
                this.state.periods = periods;
                const now = new Date();
                const nowStr = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
                const match = periods.find(p =>
                    p.type === 'monthly' && p.date_from.substring(0, 7) === nowStr
                ) || periods[0];
                if (match) this.state.periodId = match.id;
            } else {
                // Generate month-year options for last 2 years + next year
                this.state.periods = this._generateMonthPeriods();
                const now = new Date();
                const key = `m-${now.getMonth()+1}-${now.getFullYear()}`;
                const match = this.state.periods.find(p => p.id === key);
                if (match) this.state.periodId = match.id;
            }
        } catch(e) {
            this.state.periods = this._generateMonthPeriods();
        }
    }

    _generateMonthPeriods() {
        const months = ['January','February','March','April','May','June',
                        'July','August','September','October','November','December'];
        const now = new Date();
        const result = [];
        for (let y = now.getFullYear() - 1; y <= now.getFullYear() + 1; y++) {
            for (let m = 1; m <= 12; m++) {
                result.push({
                    id: `m-${m}-${y}`,
                    name: `${months[m-1]} ${y}`,
                    type: 'monthly',
                    month: m,
                    year: y,
                });
            }
        }
        return result.reverse();
    }

    _resolvedPeriod() {
        const pid = this.state.periodId;
        if (!pid) return { month: null, year: null, periodId: false };
        if (typeof pid === 'string' && pid.startsWith('m-')) {
            const [, m, y] = pid.split('-');
            return { month: parseInt(m), year: parseInt(y), periodId: false };
        }
        // Real kpi.target.period id
        const p = this.state.periods.find(x => x.id === pid);
        if (p && p.month) return { month: p.month, year: p.year, periodId: false };
        return { month: this.state.month, year: this.state.year, periodId: pid };
    }

    async loadData() {
        this.state.loading = true;
        const { month, year, periodId } = this._resolvedPeriod();
        try {
            const result = await this.orm.call(
                'sfa.incentive.dashboard', 'get_dashboard_data',
                [month || this.state.month, year || this.state.year],
                {
                    period_id: periodId || false,
                    criteria_id: this.state.criteriaId || false,
                    profile_id: this.state.profileId || false,
                    territory_id: this.state.territoryId || false,
                    status: this.state.activeTab !== 'all' ? this.state.activeTab : false,
                }
            );
            this.state.records = result.records || [];
            this.state.stats = { ...EMPTY_STATS, ...(result.stats || {}) };
            if (result.filter_options) {
                this.state.filterOptions = result.filter_options;
            }
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.showToast('Failed to load: ' + msg, 'error');
        } finally {
            this.state.loading = false;
        }
    }

    get filteredRecords() {
        const tab = this.state.activeTab;
        if (tab === 'all') return this.state.records;
        return this.state.records.filter(r => r.status === tab);
    }

    get tabCounts() {
        const counts = { all: this.state.records.length };
        for (const tab of TABS) {
            if (tab.key !== 'all') {
                counts[tab.key] = this.state.stats[tab.key] ? this.state.stats[tab.key].count : 0;
            }
        }
        return counts;
    }

    // ── Filters ──────────────────────────────────────────────────────────────

    onPeriodChange(ev) {
        const val = ev.target.value;
        if (!val) {
            this.state.periodId = null;
        } else if (val.startsWith('m-')) {
            this.state.periodId = val;
        } else {
            this.state.periodId = parseInt(val);
        }
        this.loadData();
    }

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

    setTab(key) {
        this.state.activeTab = key;
    }

    // ── Actions ──────────────────────────────────────────────────────────────

    async runCalculation() {
        this.state.calculating = true;
        const { month, year } = this._resolvedPeriod();
        try {
            const result = await this.orm.call(
                'sfa.incentive.dashboard', 'run_calculation',
                [month || this.state.month, year || this.state.year],
                { annual: false }
            );
            this.showToast(result.message || 'Calculation complete', 'success');
            await this.loadData();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.showToast('Calculation failed: ' + msg, 'error');
        } finally {
            this.state.calculating = false;
        }
    }

    async openAnnualBonus() {
        const confirmed = window.confirm('Run Annual Bonus calculation?');
        if (!confirmed) return;
        this.state.calculating = true;
        const { month: aMonth, year: aYear } = this._resolvedPeriod();
        try {
            const result = await this.orm.call(
                'sfa.incentive.dashboard', 'run_calculation',
                [aMonth || this.state.month, aYear || this.state.year],
                { annual: true }
            );
            this.showToast(result.message || 'Annual bonus calculation complete', 'success');
            await this.loadData();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.showToast('Annual bonus failed: ' + msg, 'error');
        } finally {
            this.state.calculating = false;
        }
    }

    async submitForApproval(recordId) {
        try {
            await this.orm.call('sfa.incentive.dashboard', 'update_record_status',
                [recordId, 'pending_approval']);
            this.showToast('Submitted for approval', 'success');
            await this.loadData();
        } catch (e) {
            this.showToast((e.data && e.data.message) || e.message, 'error');
        }
    }

    async approveRecord(recordId) {
        try {
            await this.orm.call('sfa.incentive.dashboard', 'update_record_status',
                [recordId, 'approved']);
            this.showToast('Record approved', 'success');
            await this.loadData();
        } catch (e) {
            this.showToast((e.data && e.data.message) || e.message, 'error');
        }
    }

    async rejectRecord(recordId) {
        const reason = window.prompt('Enter rejection reason (optional):');
        try {
            await this.orm.call('sfa.incentive.dashboard', 'update_record_status',
                [recordId, 'rejected'], { reason: reason || '' });
            this.showToast('Record rejected', 'success');
            await this.loadData();
        } catch (e) {
            this.showToast((e.data && e.data.message) || e.message, 'error');
        }
    }

    async markPaid(recordId) {
        try {
            await this.orm.call('sfa.incentive.dashboard', 'update_record_status',
                [recordId, 'paid']);
            this.showToast('Marked as paid', 'success');
            await this.loadData();
        } catch (e) {
            this.showToast((e.data && e.data.message) || e.message, 'error');
        }
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    statusLabel(status) { return STATUS_LABELS[status] || status; }

    formatAmount(val) {
        if (!val && val !== 0) return '₹0';
        const n = Number(val);
        if (n >= 1e7) return '₹' + (n / 1e7).toFixed(1) + 'Cr';
        if (n >= 1e5) return '₹' + (n / 1e5).toFixed(1) + 'L';
        if (n >= 1e3) return '₹' + (n / 1e3).toFixed(1) + 'K';
        return '₹' + n.toLocaleString('en-IN');
    }

    showToast(message, type = 'success') {
        this.state.toast = { message, type };
        setTimeout(() => { this.state.toast = null; }, 3500);
    }
}

registry.category("actions").add("sfa_incentive_dashboard", IncentiveDashboard);
