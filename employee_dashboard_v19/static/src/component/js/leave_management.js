/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class LeaveManagement extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.dialog = useService("dialog");

        const year = new Date().getFullYear();
        this.state = useState({
            loading: true,
            activeTab: 'my',       // 'my' | 'team'
            selectedYear: year,
            statusFilter: 'all',   // 'all'|'draft'|'confirm'|'validate1'|'validate'|'refuse'|'cancel'

            // My leaves
            leaveTypes: [],        // [{id, name, code, available, accrued, carry_fwd, used}]
            myLeaves: [],          // hr.leave records

            // Team approvals (manager only)
            pendingLeaves: [],
            recentDecisions: [],

            // Apply form
            showApplyForm: false,
            applyForm: {
                holiday_status_id: false,
                holiday_status_name: '',
                date_from: '',
                date_to: '',
                name: '',
                request_session_from: 'am', // Default
                request_session_to: 'pm',
            },
            availableLeaveTypes: [],
            submitting: false,
        });

        onWillStart(async () => {
            await this._loadAll();
        });
    }

    async _loadAll() {
        this.state.loading = true;
        try {
            await Promise.all([
                this._loadLeaveTypes(),
                this._loadMyLeaves(),
                this._loadTeamLeaves(),
            ]);
        } finally {
            this.state.loading = false;
        }
    }

    async _loadLeaveTypes() {
        const empId = this.props.employeeId;
        if (!empId) return;
        try {
            // Fetch all active leave types (Odoo 19: no leave_validation_type filter)
            const safeFields = ['id', 'name'];
            // Try to fetch balance via hr.leave.type.with_context or just get names
            const types = await this.orm.searchRead('hr.leave.type',
                [['active', '=', true]],
                safeFields, { limit: 30 });

            // Store for the apply form dropdown
            this.state.availableLeaveTypes = types.map(t => ({ id: t.id, name: t.name }));

            // Fetch approved allocations for this employee
            let allocations = [];
            try {
                allocations = await this.orm.searchRead('hr.leave.allocation', [
                    ['employee_id', '=', empId],
                    ['state', '=', 'validate'],
                ], ['holiday_status_id', 'number_of_days', 'date_from', 'date_to'], { limit: 200 });
            } catch (_) { allocations = []; }

            const allocationMap = {};
            const carryFwdMap = {};
            for (const a of allocations) {
                const tid = a.holiday_status_id[0];
                const days = a.number_of_days || 0;
                // Current year allocations = accrued; prior year = carry forward
                const isCurrentYear = !a.date_from || a.date_from.startsWith(String(this.state.selectedYear));
                allocationMap[tid] = (allocationMap[tid] || 0) + days;
                if (!isCurrentYear) {
                    carryFwdMap[tid] = (carryFwdMap[tid] || 0) + days;
                }
            }

            // Fetch leaves taken (approved) this year
            let taken = [];
            try {
                taken = await this.orm.searchRead('hr.leave', [
                    ['employee_id', '=', empId],
                    ['state', '=', 'validate'],
                    ['date_from', '>=', `${this.state.selectedYear}-01-01`],
                    ['date_from', '<=', `${this.state.selectedYear}-12-31`],
                ], ['holiday_status_id', 'number_of_days'], { limit: 500 });
            } catch (_) { taken = []; }

            const takenMap = {};
            for (const t of taken) {
                const tid = t.holiday_status_id[0];
                takenMap[tid] = (takenMap[tid] || 0) + Math.abs(t.number_of_days || 0);
            }

            // Build display records — only show types that have allocations or usage
            this.state.leaveTypes = types
                .map(t => {
                    const accrued = allocationMap[t.id] || 0;
                    const used = takenMap[t.id] || 0;
                    const carry_fwd = carryFwdMap[t.id] || 0;
                    return {
                        id: t.id,
                        name: t.name,
                        code: this._leaveTypeCode(t.name),
                        available: Math.max(0, accrued - used),
                        accrued: accrued,
                        carry_fwd: carry_fwd,
                        used: used,
                    };
                })
                .filter(t => t.accrued > 0 || t.used > 0);
        } catch (e) {
            console.error("Leave types load error:", e);
        }
    }

    _leaveTypeCode(name) {
        // Generate abbreviation: CL → Casual Leave, SL → Sick Leave, etc.
        const map = {
            'casual': 'CL', 'sick': 'SL', 'earned': 'EL', 'paid': 'PL',
            'unpaid': 'UL', 'compensatory': 'CO', 'parental': 'PA',
            'extra time': 'ET', 'extra hours': 'EH', 'training': 'TR',
            'maternity': 'ML', 'paternity': 'PAL', 'annual': 'AL',
        };
        const lower = (name || '').toLowerCase();
        for (const [key, code] of Object.entries(map)) {
            if (lower.includes(key)) return code;
        }
        // Fallback: first letters of each word
        return (name || 'LV').split(' ').map(w => w[0]).join('').substring(0, 3).toUpperCase();
    }

    async _loadMyLeaves() {
        const empId = this.props.employeeId;
        if (!empId) return;
        try {
            const domain = [
                ['employee_id', '=', empId],
                ['date_from', '>=', `${this.state.selectedYear}-01-01`],
                ['date_from', '<=', `${this.state.selectedYear}-12-31`],
            ];
            if (this.state.statusFilter !== 'all') {
                domain.push(['state', '=', this.state.statusFilter]);
            }
            const leaves = await this.orm.searchRead('hr.leave', domain,
                ['id', 'name', 'holiday_status_id', 'date_from', 'date_to', 'number_of_days', 'state'],
                { order: 'date_from desc', limit: 100 });
            this.state.myLeaves = leaves.map(l => ({
                ...l,
                label: l.holiday_status_id ? l.holiday_status_id[1] : '',
                typeCode: this._leaveTypeCode(l.holiday_status_id ? l.holiday_status_id[1] : 'LV'),
                stateLabel: this._stateLabel(l.state),
                stateColor: this._stateColor(l.state),
                dateRange: this._formatDateRange(l.date_from, l.date_to),
                days: Math.abs(l.number_of_days || 0),
            }));
        } catch (e) {
            console.error("My leaves load error:", e);
        }
    }

    async _loadTeamLeaves() {
        if (!this.props.isManager) return;
        try {
            const pending = await this.orm.searchRead('hr.leave', [
                ['state', 'in', ['confirm', 'validate1']],
                ['department_id.manager_id.user_id', '=', this.props.currentUserId || false],
            ], ['id', 'employee_id', 'holiday_status_id', 'date_from', 'date_to',
                'number_of_days', 'state', 'name'],
            { order: 'date_from asc', limit: 50 });

            this.state.pendingLeaves = pending.map(l => ({
                ...l,
                empName: l.employee_id ? l.employee_id[1] : '',
                typeCode: l.holiday_status_id ? l.holiday_status_id[1].substring(0, 2).toUpperCase() : 'LV',
                typeName: l.holiday_status_id ? l.holiday_status_id[1] : '',
                dateRange: this._formatDateRange(l.date_from, l.date_to),
                days: Math.abs(l.number_of_days || 0),
                reason: l.name || '',
            }));

            const recent = await this.orm.searchRead('hr.leave', [
                ['state', 'in', ['validate', 'refuse']],
                ['department_id.manager_id.user_id', '=', this.props.currentUserId || false],
            ], ['id', 'employee_id', 'holiday_status_id', 'date_from', 'date_to',
                'number_of_days', 'state', 'write_date'],
            { order: 'write_date desc', limit: 20 });

            this.state.recentDecisions = recent.map(l => ({
                ...l,
                empName: l.employee_id ? l.employee_id[1] : '',
                typeCode: l.holiday_status_id ? l.holiday_status_id[1].substring(0, 2).toUpperCase() : 'LV',
                typeName: l.holiday_status_id ? l.holiday_status_id[1] : '',
                dateRange: this._formatDateRange(l.date_from, l.date_to),
                days: Math.abs(l.number_of_days || 0),
                stateLabel: l.state === 'validate' ? 'Approved' : 'Refused',
                decisionDate: l.write_date ? l.write_date.split(' ')[0] : '',
            }));
        } catch (e) {
            console.error("Team leaves load error:", e);
        }
    }

    _stateLabel(state) {
        const map = {
            draft: 'Draft', confirm: 'Submitted', validate1: 'Pending',
            validate: 'Approved', refuse: 'Rejected', cancel: 'Cancelled',
        };
        return map[state] || state;
    }

    _stateColor(state) {
        const map = {
            draft: '#6b7280', confirm: '#3b82f6', validate1: '#f59e0b',
            validate: '#059669', refuse: '#ef4444', cancel: '#9ca3af',
        };
        return map[state] || '#6b7280';
    }

    _formatDateRange(from, to) {
        if (!from) return '--';
        const fmt = (d) => {
            const dt = new Date(d);
            return `${dt.getDate().toString().padStart(2,'0')} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][dt.getMonth()]} ${dt.getFullYear()}`;
        };
        const f = from.includes('T') ? from : from + 'T00:00:00';
        const t = to && to !== from ? (to.includes('T') ? to : to + 'T00:00:00') : null;
        return t ? `${fmt(f)} - ${fmt(t)}` : fmt(f);
    }

    // ── Filters / tabs ──────────────────────────────────────────

    async switchTab(tab) {
        this.state.activeTab = tab;
    }

    async setStatusFilter(val) {
        this.state.statusFilter = val;
        await this._loadMyLeaves();
    }

    async changeYear(ev) {
        this.state.selectedYear = parseInt(ev.target.value);
        await this._loadAll();
    }

    // ── Actions ─────────────────────────────────────────────────

    openApplyForm() {
        const today = new Date();
        const pad = n => n.toString().padStart(2, '0');
        const todayStr = `${today.getFullYear()}-${pad(today.getMonth()+1)}-${pad(today.getDate())}`;
        this.state.applyForm = {
            holiday_status_id: false,
            holiday_status_name: '',
            date_from: todayStr,
            date_to: todayStr,
            name: '',
        };
        this.state.showApplyForm = true;
    }

    closeApplyForm() {
        this.state.showApplyForm = false;
    }

    onApplyFormChange(field, ev) {
        if (field === 'holiday_status_id') {
            const opt = ev.target.selectedOptions[0];
            this.state.applyForm.holiday_status_id = parseInt(ev.target.value) || false;
            this.state.applyForm.holiday_status_name = opt ? opt.text : '';
        } else {
            this.state.applyForm[field] = ev.target.value;
        }
    }

    async submitLeave() {
        const f = this.state.applyForm;
        if (!f.holiday_status_id) {
            this.notification.add("Please select a leave type", { type: "warning" }); return;
        }
        if (!f.date_from || !f.date_to) {
            this.notification.add("Please select date range", { type: "warning" }); return;
        }
        if (f.date_from > f.date_to) {
            this.notification.add("End date must be after start date", { type: "warning" }); return;
        }
        this.state.submitting = true;
        try {
            // const vals = {
            //     employee_id: this.props.employeeId,
            //     holiday_status_id: f.holiday_status_id,
            //     date_from: f.date_from + ' 09:00:00',
            //     date_to: f.date_to + ' 18:00:00',
            //     request_unit_half: true, // Mark as half-day if needed
            //     request_date_from_period: this.state.applyForm.request_session_from,
            //     request_date_to_period: this.state.applyForm.request_session_to,
            //     name: f.name || f.holiday_status_name,
            // };
            const vals = {
                employee_id: this.props.employeeId,
                holiday_status_id: parseInt(f.holiday_status_id),
                // Pass only the date strings (YYYY-MM-DD). 
                // Odoo will append the session times automatically.
                request_unit_half: true,
                request_date_from: f.date_from, 
                request_date_to: f.date_to,
                // Match the selection values from image_58787a.png
                request_date_from_period: f.request_session_from, // 'am' or 'pm'
                request_date_to_period: f.request_session_to,
                name: f.name || f.holiday_status_name,
            };
            const id = await this.orm.create('hr.leave', [vals]);
            // Auto-submit (confirm) the leave request
            try {
                await this.orm.call('hr.leave', 'action_draft', [[id]]);
                await this.orm.call('hr.leave', 'action_confirm', [[id]]);
            } catch (_) { /* stay in draft if confirm fails */ }
            this.notification.add("Leave request submitted successfully!", { type: "success" });
            this.state.showApplyForm = false;
            await this._loadAll();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add("Failed to submit leave: " + msg, { type: "danger" });
        } finally {
            this.state.submitting = false;
        }
    }

    async approveLeave(id) {
        try {
            await this.orm.call('hr.leave', 'action_approve', [[id]]);
            this.notification.add("Leave approved", { type: "success" });
            await this._loadTeamLeaves();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add("Failed to approve: " + msg, { type: "danger" });
        }
    }

    async refuseLeave(id) {
        try {
            await this.orm.call('hr.leave', 'action_refuse', [[id]]);
            this.notification.add("Leave refused", { type: "success" });
            await this._loadTeamLeaves();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add("Failed to refuse: " + msg, { type: "danger" });
        }
    }
}

LeaveManagement.template = "employee_dashboard_v19.LeaveManagement";
LeaveManagement.props = {
    employeeId: { type: Number, optional: true },
    isManager: { type: Boolean, optional: true },
    currentUserId: { optional: true },
};
