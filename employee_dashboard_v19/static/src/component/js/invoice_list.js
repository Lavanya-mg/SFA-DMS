/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class InvoiceList extends Component {

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.actionService = useService("action");

        this.state = useState({
            loading: true,
            invoices: [],
            invoiceFilter : {customer: "", from_date: "", to_date: "", status: ""},
        });

        onWillStart(async () => {
            await this.loadInvoices();
        });
    }

    async loadInvoices(){
        const invoiceData = await this.orm.searchRead(
            "account.move",
            [["invoice_user_id", "=", this.props.userId], ["invoice_user_id", "!=", false], ["move_type", "=", "out_invoice"]],
            ["name", "partner_id", "invoice_date", "state", "amount_total", "invoice_line_ids"]
        );
        const invoices = invoiceData.map(invoice => ({
            ...invoice,
            item_count: invoice.invoice_line_ids.length
        }));
        this.state.invoices = invoices || null;
        this.state.loading = false;
    }

    async applyInvoiceFilters() {
        const { customer, from_date, to_date, status } = this.state.invoiceFilter;
        const domain = [
            ["invoice_user_id", "=", this.props.userId],
            ["invoice_user_id", "!=", false],
            ["move_type", "=", "out_invoice"],
        ];
        if (customer) domain.push(["partner_id.name", "ilike", customer]);
        if (from_date) domain.push(["invoice_date", ">=", from_date]);
        if (to_date) domain.push(["invoice_date", "<=", to_date]);
        if (status && status !== "All") domain.push(["state", "=", status]);
        const invoiceData = await this.orm.searchRead(
            "account.move", domain,
            ["name", "partner_id", "invoice_date", "state", "amount_total", "invoice_line_ids"]
        );
        this.state.invoices = invoiceData.map(inv => ({ ...inv, item_count: inv.invoice_line_ids.length }));
    }
}

InvoiceList.template = "employee_dashboard_v19.InvoiceList";
