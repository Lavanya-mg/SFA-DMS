/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE ORDERS SCREEN
 * ALL read operations go through emp360.mobile helpers (sudo)
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MobileOrders extends Component {
    static template = "employee_mobile_v19.MobileOrders";
    static props = {
        employeeId: { type: [Number, { value: false }], optional: true },
        isManager: { type: Boolean, optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.setFilter = this.setFilter.bind(this);
        this.setStatusFilter = this.setStatusFilter.bind(this);
        this.onSearchInput = this.onSearchInput.bind(this);
        this.openOrderDetail = this.openOrderDetail.bind(this);
        this.closeOrderDetail = this.closeOrderDetail.bind(this);

        this.state = useState({
            loading: true, orders: [], filtered: [],
            filter: "month", statusFilter: "all", search: "",
            stats: { total: 0, confirmed: 0, draft: 0, amount: 0 },
            selectedOrder: null, showOrderDetail: false,
            orderLines: [], orderDetailBusy: false,
        });
        onWillStart(async () => { await this._load(); });
    }

    get empId() { return this.props.employeeId; }
    get isManager() { return this.props.isManager; }

    async _load() {
        this.state.loading = true;
        try {
            const domain = this._buildDomainExtra();
            const orders = await this.orm.call("emp360.mobile", "get_orders",
                [this.empId, this.isManager || false, domain, 100]);
            this.state.orders = orders;
            this._applyFilters();
            this._calcStats();
        } catch (e) { console.error("[Orders]", e); }
        finally { this.state.loading = false; }
    }

    _buildDomainExtra() {
        const domain = [];
        const now = new Date();
        switch (this.state.filter) {
            case "today": {
                const d = now.toISOString().slice(0, 10);
                domain.push(["date_order", ">=", d + " 00:00:00"]);
                domain.push(["date_order", "<=", d + " 23:59:59"]);
                break;
            }
            case "week": {
                const start = new Date(now); start.setDate(now.getDate() - now.getDay());
                domain.push(["date_order", ">=", start.toISOString().slice(0, 10) + " 00:00:00"]);
                break;
            }
            case "month": {
                domain.push(["date_order", ">=", `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-01 00:00:00`]);
                break;
            }
        }
        if (this.state.statusFilter !== "all") domain.push(["state", "=", this.state.statusFilter]);
        return domain;
    }

    _applyFilters() {
        let list = [...this.state.orders];
        if (this.state.search) {
            const q = this.state.search.toLowerCase();
            list = list.filter(o => (o.name||"").toLowerCase().includes(q) || (o.partner_id?.[1]||"").toLowerCase().includes(q));
        }
        this.state.filtered = list;
    }

    _calcStats() {
        const o = this.state.filtered;
        this.state.stats = {
            total: o.length,
            confirmed: o.filter(x => x.state === "sale" || x.state === "done").length,
            draft: o.filter(x => x.state === "draft").length,
            amount: o.reduce((s, x) => s + (x.amount_total || 0), 0),
        };
    }

    async setFilter(f) { this.state.filter = f; await this._load(); }
    async setStatusFilter(s) { this.state.statusFilter = s; this._applyFilters(); this._calcStats(); }
    onSearchInput(ev) { this.state.search = ev.target.value; this._applyFilters(); this._calcStats(); }

    async openOrderDetail(order) {
        this.state.selectedOrder = order; this.state.showOrderDetail = true;
        this.state.orderDetailBusy = true; this.state.orderLines = [];
        try {
            this.state.orderLines = await this.orm.call("emp360.mobile", "get_order_lines", [order.id]);
        } catch (e) { console.warn("[Order Lines]", e); }
        finally { this.state.orderDetailBusy = false; }
    }

    closeOrderDetail() { this.state.showOrderDetail = false; this.state.selectedOrder = null; this.state.orderLines = []; }

    fmtMoney(v) { if (!v) return "₹0"; if (v>=10000000) return `₹${(v/10000000).toFixed(1)}Cr`; if (v>=100000) return `₹${(v/100000).toFixed(1)}L`; if (v>=1000) return `₹${(v/1000).toFixed(0)}K`; return `₹${Math.round(v).toLocaleString("en-IN")}`; }
    fmtDate(dt) { if (!dt) return "—"; return new Date(dt).toLocaleDateString("en-IN", { day: "numeric", month: "short" }); }
    fmtDateTime(dt) { if (!dt) return "—"; const d = new Date(dt); return d.toLocaleDateString("en-IN", { day:"numeric", month:"short", year:"numeric" })+" "+d.toLocaleTimeString("en-IN", { hour:"2-digit", minute:"2-digit" }); }
    statusLabel(s) { return ({draft:"Draft",sent:"Sent",sale:"Confirmed",done:"Done",cancel:"Cancelled"})[s]||s; }
    statusClass(s) { return ({sale:"success",done:"success",draft:"warning",sent:"info",cancel:"danger"})[s]||"muted"; }
    getInitials(n) { return (n||"?").split(" ").slice(0,2).map(w=>w[0]||"").join("").toUpperCase(); }
    getAvatarGradient(s) { const g=["linear-gradient(135deg,#f72585,#b5179e)","linear-gradient(135deg,#4361ee,#3a0ca3)","linear-gradient(135deg,#06d6a0,#019b72)","linear-gradient(135deg,#f77f00,#d62828)"]; let h=0; for(let i=0;i<(s||"").length;i++) h=s.charCodeAt(i)+((h<<5)-h); return g[Math.abs(h)%g.length]; }
}