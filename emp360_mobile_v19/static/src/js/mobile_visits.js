/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE VISITS SCREEN
 * ALL read operations go through emp360.mobile helpers (sudo)
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class MobileVisits extends Component {
    static template = "employee_mobile_v19.MobileVisits";
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
        this.openDetail = this.openDetail.bind(this);
        this.closeDetail = this.closeDetail.bind(this);

        this.state = useState({
            loading: true, visits: [], filtered: [],
            filter: "all", statusFilter: "all", search: "",
            selectedVisit: null, showDetail: false,
            visitDetail: null, detailLoading: false,
        });
        onWillStart(async () => { await this._load(); });
    }

    get empId() { return this.props.employeeId; }
    get isManager() { return this.props.isManager; }

    async _load() {
        this.state.loading = true;
        try {
            const domain = this._buildDomainExtra();
            const visits = await this.orm.call("emp360.mobile", "get_visits",
                [this.empId, this.isManager || false, domain, 50]);
            this.state.visits = visits;
            this._applyFilters();
        } catch (e) { console.error("[Visits]", e); }
        finally { this.state.loading = false; }
    }

    _buildDomainExtra() {
        const domain = [];
        const now = new Date();
        const tStr = now.toISOString().slice(0, 10);
        switch (this.state.filter) {
            case "today":
                domain.push(["actual_start_time", ">=", tStr + " 00:00:00"]);
                domain.push(["actual_start_time", "<=", tStr + " 23:59:59"]);
                break;
            case "week": {
                const start = new Date(now); start.setDate(now.getDate() - now.getDay());
                domain.push(["actual_start_time", ">=", start.toISOString().slice(0, 10) + " 00:00:00"]);
                break;
            }
            case "month": {
                domain.push(["actual_start_time", ">=", `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,"0")}-01 00:00:00`]);
                break;
            }
        }
        if (this.state.statusFilter !== "all") domain.push(["status", "=", this.state.statusFilter]);
        return domain;
    }

    _applyFilters() {
        let list = [...this.state.visits];
        if (this.state.search) {
            const q = this.state.search.toLowerCase();
            list = list.filter(v => (v.partner_id?.[1]||"").toLowerCase().includes(q) || (v.name||"").toLowerCase().includes(q) || (v.beat_id?.[1]||"").toLowerCase().includes(q));
        }
        this.state.filtered = list;
    }

    async setFilter(f) { this.state.filter = f; await this._load(); }
    async setStatusFilter(s) { this.state.statusFilter = s; await this._load(); }
    onSearchInput(ev) { this.state.search = ev.target.value; this._applyFilters(); }

    async openDetail(visit) {
        this.state.selectedVisit = visit; this.state.showDetail = true; this.state.detailLoading = true;
        try {
            this.state.visitDetail = await this.orm.call("emp360.mobile", "get_visit_detail", [visit.id]);
        } catch (e) { console.error("[Visit Detail]", e); }
        finally { this.state.detailLoading = false; }
    }

    closeDetail() { this.state.showDetail = false; this.state.visitDetail = null; }

    fmtDate(dt) { if (!dt) return "—"; return new Date(dt).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }); }
    fmtTime(dt) { if (!dt) return "--:--"; return new Date(dt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }); }
    fmtMoney(v) { if (!v) return "₹0"; if (v>=100000) return `₹${(v/100000).toFixed(1)}L`; if (v>=1000) return `₹${(v/1000).toFixed(0)}K`; return `₹${Math.round(v).toLocaleString("en-IN")}`; }
    statusClass(s) { return ({completed:"success",in_progress:"warning",planned:"info",cancelled:"danger"})[s]||"muted"; }
    statusLabel(s) { return ({completed:"Completed",in_progress:"In Progress",planned:"Planned",cancelled:"Cancelled"})[s]||s; }
    statusIcon(s) { return ({completed:"fa-check-circle",in_progress:"fa-circle",planned:"fa-clock-o",cancelled:"fa-times-circle"})[s]||"fa-circle"; }
    getInitials(n) { return (n||"?").split(" ").slice(0,2).map(w=>w[0]||"").join("").toUpperCase(); }
    getAvatarGradient(s) { const g=["linear-gradient(135deg,#4361ee,#3a0ca3)","linear-gradient(135deg,#06d6a0,#019b72)","linear-gradient(135deg,#f72585,#b5179e)","linear-gradient(135deg,#f77f00,#d62828)","linear-gradient(135deg,#7209b7,#3a0ca3)","linear-gradient(135deg,#4cc9f0,#0077b6)"]; let h=0; for(let i=0;i<(s||"").length;i++) h=s.charCodeAt(i)+((h<<5)-h); return g[Math.abs(h)%g.length]; }
}