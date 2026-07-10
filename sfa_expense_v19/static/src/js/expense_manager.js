/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

class ExpenseManager extends Component {
    static template = "sfa_expense_v19.ExpenseManager";

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        const today = new Date();
        this.state = useState({
            month: String(today.getMonth() + 1),
            year: today.getFullYear(),
            activeTab: 'expenses',
            data: null,
            loading: true,
            expandedDates: {},
            showAddExpense: {},
            addExpenseType: {},
            editingLine: null,
            showAddDay: false,
            addDayDateVal: '',
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        this.state.loading = true;
        try {
            const data = await this.orm.call(
                'sfa.expense.manager',
                'get_expense_data',
                [parseInt(this.state.month), this.state.year]
            );
            this.state.data = data;
            const today = new Date().toISOString().split('T')[0];
            if (data.lines_by_date && data.lines_by_date[today]) {
                this.state.expandedDates[today] = true;
            }
        } catch (e) {
            console.error('Failed to load expense data:', e);
            this.notification.add('Failed to load expense data', { type: 'danger' });
        }
        this.state.loading = false;
    }

    get months() {
        return [
            { value: '1', label: 'January' }, { value: '2', label: 'February' },
            { value: '3', label: 'March' }, { value: '4', label: 'April' },
            { value: '5', label: 'May' }, { value: '6', label: 'June' },
            { value: '7', label: 'July' }, { value: '8', label: 'August' },
            { value: '9', label: 'September' }, { value: '10', label: 'October' },
            { value: '11', label: 'November' }, { value: '12', label: 'December' },
        ];
    }

    get years() {
        const y = new Date().getFullYear();
        return [y - 2, y - 1, y, y + 1].map(v => ({ value: v, label: String(v) }));
    }

    get sortedDates() {
        if (!this.state.data || !this.state.data.lines_by_date) return [];
        return Object.values(this.state.data.lines_by_date).sort((a, b) => a.date.localeCompare(b.date));
    }

    get stateBadgeClass() {
        const s = this.state.data?.header?.state || 'draft';
        return { draft: 'badge-draft', submitted: 'badge-submitted', approved: 'badge-approved', rejected: 'badge-rejected' }[s] || 'badge-draft';
    }

    async onMonthChange(ev) {
        this.state.month = ev.target.value;
        await this.loadData();
    }

    async onYearChange(ev) {
        this.state.year = parseInt(ev.target.value);
        await this.loadData();
    }

    toggleDate(date) {
        this.state.expandedDates[date] = !this.state.expandedDates[date];
    }

    showAddForDate(date) {
        this.state.showAddExpense[date] = true;
    }

    async saveLine(date, typeId, vals) {
        if (!typeId) {
            this.notification.add('Please select an expense type', { type: 'warning' });
            return;
        }
        try {
            const managerId = this.state.data.header.id;
            await this.orm.call('sfa.expense.manager', 'save_expense_line', [{
                date: date,
                expense_type_id: typeId,
                ...vals,
            }]);
            this.state.showAddExpense[date] = false;
            this.state.expandedDates[date] = true;
            await this.loadData();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add(msg, { type: 'danger', title: 'Save Failed' });
        }
    }

    async updateLineField(lineId, field, value) {
        try {
            if (field === 'amount') {
                await this.orm.call('sfa.expense.manager', 'save_expense_line', [{
                    line_id: lineId,
                    amount: value,
                }]);
            } else {
                const fieldMap = { remarks: 'name', daily_km: 'daily_km', hours: 'hours' };
                const hrField = fieldMap[field] || field;
                await this.orm.write('hr.expense', [lineId], { [hrField]: value });
            }
            await this.loadData();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add(msg, { type: 'danger', title: 'Update Failed' });
        }
    }

    async deleteLine(lineId) {
        try {
            await this.orm.call('sfa.expense.manager', 'delete_expense_line', [lineId]);
            await this.loadData();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add(msg, { type: 'danger', title: 'Delete Failed' });
        }
    }

    onShowAddDayClick() {
        const today = new Date().toISOString().split('T')[0];
        this.state.addDayDateVal = today;
        this.state.showAddDay = true;
    }

    onAddDayDateChange(ev) {
        this.state.addDayDateVal = ev.target.value;
    }

    onConfirmAddDay() {
        const date = this.state.addDayDateVal;
        if (!date) return;
        if (!this.state.data.lines_by_date[date]) {
            const dt = new Date(date + 'T00:00:00');
            const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            const dd = String(dt.getDate()).padStart(2, '0');
            const mm = String(dt.getMonth() + 1).padStart(2, '0');
            const yyyy = dt.getFullYear();
            this.state.data.lines_by_date = Object.assign({}, this.state.data.lines_by_date, {
                [date]: {
                    date,
                    date_display: `${days[dt.getDay()]}, ${dd}/${mm}/${yyyy}`,
                    duty_type_code: '',
                    location: '',
                    hours: 0,
                    total: 0,
                    eligible: 0,
                    lines: [],
                },
            });
        }
        this.state.expandedDates[date] = true;
        this.state.showAddExpense[date] = true;
        this.state.showAddDay = false;
        this.state.addDayDateVal = '';
    }

    onCancelAddDay() {
        this.state.showAddDay = false;
        this.state.addDayDateVal = '';
    }

    onBackClick() {
        window.history.back();
    }

    async submitExpense() {
        try {
            await this.orm.call('sfa.expense.manager', 'action_submit', [
                parseInt(this.state.month), this.state.year
            ]);
            await this.loadData();
            this.notification.add('Expense submitted successfully', { type: 'success' });
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add(msg, { type: 'danger', title: 'Submit Failed' });
        }
    }

    setTab(tab) {
        this.state.activeTab = tab;
    }

    get tabDefs() {
        return [
            { key: 'expenses', icon: 'fa-list', label: 'Expenses' },
            { key: 'summary', icon: 'fa-table', label: 'Summary' },
            { key: 'overview', icon: 'fa-th-large', label: 'Overview' },
            { key: 'team', icon: 'fa-users', label: 'Team' },
        ];
    }

    onTabClick(ev) {
        this.setTab(ev.currentTarget.dataset.tab);
    }

    onHistoryClick() {
        this.setTab('overview');
    }

    onDateRowClick(ev) {
        this.toggleDate(ev.currentTarget.dataset.date);
    }

    onDeleteLineClick(ev) {
        this.deleteLine(parseInt(ev.currentTarget.dataset.lineId));
    }

    onLineFieldChange(ev) {
        const { lineId, field } = ev.target.dataset;
        this.updateLineField(parseInt(lineId), field, parseFloat(ev.target.value) || 0);
    }

    onLineFieldChangeText(ev) {
        const { lineId, field } = ev.target.dataset;
        this.updateLineField(parseInt(lineId), field, ev.target.value);
    }

    onShowAddExpenseClick(ev) {
        this.showAddForDate(ev.currentTarget.dataset.date);
    }

    onExpenseTypeSelect(ev) {
        this.state.addExpenseType[ev.target.dataset.date] = parseInt(ev.target.value);
    }

    onAddExpenseClick(ev) {
        const date = ev.currentTarget.dataset.date;
        this.saveLine(date, this.state.addExpenseType[date], { amount: 0 });
    }

    onCancelAddExpenseClick(ev) {
        this.state.showAddExpense[ev.currentTarget.dataset.date] = false;
    }
}

registry.category("actions").add("sfa_expense_v19.expense_manager_action", ExpenseManager);
