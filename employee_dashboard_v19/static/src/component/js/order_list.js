/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class OrdersList extends Component {

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        const today = new Date();
        const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
        const fmt = d => d.toISOString().slice(0, 10);

        this.state = useState({
            loading: true,
            orders: [],
            partnerTypeMap: {},
            activeTab: "retailers",
            orderFilter: { customer: "", from_date: fmt(firstOfMonth), to_date: fmt(today), status: "" },
            expandedOrderId: null,
            expandedOrderLines: [],
        });

        onWillStart(async () => { await this._load(); });
    }

    _buildDomain() {
        const { customer, from_date, to_date, status } = this.state.orderFilter;
        const domain = [];
        if (customer)  domain.push(["partner_id.name", "ilike", customer]);
        if (from_date) domain.push(["date_order", ">=", from_date + " 00:00:00"]);
        if (to_date)   domain.push(["date_order", "<=", to_date   + " 23:59:59"]);
        if (status)    domain.push(["state", "=", status]);
        return domain;
    }

    async _load() {
        this.state.loading = true;
        try {
            const orderData = await this.orm.searchRead(
                "sale.order", this._buildDomain(),
                ["name", "partner_id", "date_order", "state", "amount_total", "order_line", "channel"],
                { order: "date_order desc", limit: 300 }
            );
            const orders = orderData.map(o => ({ ...o, item_count: o.order_line ? o.order_line.length : 0 }));
            this.state.orders = orders;

            this.state.partnerTypeMap = {};
        } catch (e) {
            console.error("[OrdersList]", e);
            this.notification.add("Failed to load orders", { type: "danger" });
            this.state.orders = [];
        } finally {
            this.state.loading = false;
            this.state.expandedOrderId = null;
            this.state.expandedOrderLines = [];
        }
    }

    async applyOrderFilters() { await this._load(); }

    async resetFilters() {
        const today = new Date();
        const firstOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
        const fmt = d => d.toISOString().slice(0, 10);
        this.state.orderFilter = { customer: "", from_date: fmt(firstOfMonth), to_date: fmt(today), status: "" };
        await this._load();
    }

    setTab(tab) { this.state.activeTab = tab; }

    get filteredOrders() {
        const orders = this.state.orders || [];
        const map = this.state.partnerTypeMap;
        const tab = this.state.activeTab;
        if (tab === "retailers")
            return orders.filter(o => { const t = map[o.partner_id?.[0]]; return !t || t === "retailer" || t === "modern_trade"; });
        if (tab === "distributors")
            return orders.filter(o => { const t = map[o.partner_id?.[0]]; return t === "distributor" || t === "super_stockist"; });
        return orders.filter(o => { const t = map[o.partner_id?.[0]]; return t && t !== "retailer" && t !== "modern_trade" && t !== "distributor" && t !== "super_stockist"; });
    }

    get tabCounts() {
        const orders = this.state.orders || [];
        const map = this.state.partnerTypeMap;
        let r = 0, d = 0, ot = 0;
        for (const o of orders) {
            const t = map[o.partner_id?.[0]];
            if (!t || t === "retailer" || t === "modern_trade") r++;
            else if (t === "distributor" || t === "super_stockist") d++;
            else ot++;
        }
        return { retailers: r, distributors: d, other: ot };
    }

    get uniqueRetailerCount() {
        return new Set(this.filteredOrders.map(o => o.partner_id?.[0]).filter(Boolean)).size;
    }

    get totalValue() {
        return this.filteredOrders.reduce((s, o) => s + (o.amount_total || 0), 0);
    }

    async toggleOrderDetails(orderId, lineIds) {
        if (this.state.expandedOrderId === orderId) {
            this.state.expandedOrderId = null; this.state.expandedOrderLines = []; return;
        }
        try {
            this.state.expandedOrderLines = lineIds && lineIds.length
                ? await this.orm.searchRead("sale.order.line", [["id", "in", lineIds]],
                    ["product_id", "product_uom_qty", "price_unit", "price_subtotal", "name"])
                : [];
            this.state.expandedOrderId = orderId;
        } catch (e) { this.notification.add("Failed to load order details", { type: "danger" }); }
    }

    openOrder(id) {
        this.action.doAction({ type: "ir.actions.act_window", res_model: "sale.order",
            res_id: id, views: [[false, "form"]], target: "current" });
    }
}

OrdersList.template = "employee_dashboard_v19.OrdersList";
