/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

export class ExpenseList extends Component {

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            expenseRecords: [],
            expenseFromDate: "",
            expenseToDate: "",
            expenseStatus: "all",
        });

        onWillStart(async () => {
            await this.loadExpenses();
        });
    }

    async loadExpenses() {
        if (!this.props.employeeId) return;
        const today = new Date();
        const firstDay = new Date(today.getFullYear(), today.getMonth() - 5, 1);
        const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);
        this.state.expenseFromDate = firstDay.toISOString().split('T')[0];
        this.state.expenseToDate = lastDay.toISOString().split('T')[0];
        this.state.expenseStatus = "all";
        await this.loadExpenseData();
    }

    async onExpenseDateChange() {
        await this.loadExpenseData();
    }

    async onExpenseStatusChange(ev) {
        this.state.expenseStatus = ev.target.value;
        await this.loadExpenseData();
    }

    async loadExpenseData() {
        if (!this.props.employeeId) return;
        this.state.loading = true;
        try {
            const domain = [["employee_id", "=", this.props.employeeId]];
            const status = this.state.expenseStatus;
            if (status && status !== "all") {
                domain.push(["state", "=", status]);
            }

            const records = await this.orm.searchRead(
                "sfa.expense.manager",
                domain,
                ["name", "month", "year", "state", "total_claimed", "total_approved", "total_eligible"],
                { order: "year desc, month desc" }
            );

            // Filter by from/to date (month-level)
            const from = this.state.expenseFromDate ? new Date(this.state.expenseFromDate) : null;
            const to = this.state.expenseToDate ? new Date(this.state.expenseToDate) : null;

            this.state.expenseRecords = records.filter(r => {
                const recDate = new Date(r.year, parseInt(r.month) - 1, 1);
                if (from && recDate < new Date(from.getFullYear(), from.getMonth(), 1)) return false;
                if (to && recDate > new Date(to.getFullYear(), to.getMonth(), 1)) return false;
                return true;
            }).map(r => ({
                month: `${MONTH_NAMES[parseInt(r.month) - 1]} ${r.year}`,
                monthKey: `${r.year}-${r.month}`,
                status: this.getStatusLabel(r.state),
                eligible: (r.total_eligible || 0).toFixed(0),
                claimed: (r.total_claimed || 0).toFixed(0),
                approved: (r.total_approved || 0).toFixed(0),
                totalAmt: (r.total_claimed || 0).toFixed(0),
                state: r.state,
            }));
        } catch (error) {
            console.error("Error loading expense data:", error);
            this.state.expenseRecords = [];
        }
        this.state.loading = false;
    }

    getStatusLabel(state) {
        return { draft: 'Draft', submitted: 'Submitted', approved: 'Approved', rejected: 'Refused' }[state] || (state || '—');
    }
}

ExpenseList.template = "employee_dashboard_v19.ExpenseList";
