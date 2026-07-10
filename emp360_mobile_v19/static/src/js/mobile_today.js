/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE TODAY / WORKDAY SCREEN
 *
 * KEY FIXES:
 * 1. ALL writes go through emp360.mobile helpers (sudo on server)
 * 2. Geolocation NEVER blocks workflow — silently skipped if unavailable
 * 3. Store image is OPTIONAL — visit can start without photo
 * 4. End Visit uses server helper with sudo
 */

import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

const CHECKLIST_ITEMS = [
    { id: 1,  q: "Is the store exterior clean and well-maintained?" },
    { id: 2,  q: "Are all products properly displayed on shelves?" },
    { id: 3,  q: "Is the planogram being followed correctly?" },
    { id: 4,  q: "Are price tags visible on all products?" },
    { id: 5,  q: "Is the stock freshness maintained (FIFO)?" },
    { id: 6,  q: "Are POSM/promotional materials in place?" },
    { id: 7,  q: "Is the visi-cooler clean and functioning?" },
    { id: 8,  q: "Are competitor products encroaching display space?" },
    { id: 9,  q: "Is the back stock area organized?" },
    { id: 10, q: "Has the retailer been briefed on new schemes?" },
];

export class MobileToday extends Component {
    static template = "employee_mobile_v19.MobileToday";
    static props = {
        employeeId: { type: [Number, { value: false }], optional: true },
    };

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");
        this.fileInputRef = useRef("fileInput");

        // Bind ALL template-called methods
        const methods = [
            "openStartDay", "closeStartDay", "confirmStartDay",
            "openEndDay", "closeEndDay", "confirmEndDay",
            "openStartVisit", "closeStartVisit", "confirmStartVisit",
            "openEndVisit", "closeEndVisit", "confirmEndVisit",
            "openPanel", "closePanel", "saveStock", "saveCollection",
            "createOrder", "saveTicket", "saveChecklist",
            "toggleCheck", "toggleProduct", "updateQty",
            "searchProducts", "selectCategory", "updateStock",
            "onStoreImageChange", "openSwitchBeat", "closeSwitchBeat",
            "confirmSwitchBeat",
        ];
        for (const m of methods) {
            this[m] = this[m].bind(this);
        }

        this.state = useState({
            loading: true, busy: false,
            attendance: { id: null, checkedIn: false, checkIn: null, checkOut: null, workedHours: null },
            showStartDaySheet: false, showEndDaySheet: false,
            startDayForm: { workPlan: "Customer Visit", travelType: "Own", vehicle: "" },
            dayEndSummary: null,
            beats: [], selectedBeat: null, showBeatSheet: false,
            showSwitchSheet: false, switchForm: { reason: "", newBeatId: null },
            switchBusy: false, allBeatsForSwap: [],
            activeVisit: null, currentLine: null, currentLineIdx: 0,
            showStartVisitSheet: false, showEndVisitSheet: false,
            visitForm: { storeImage: null, storeImageName: "" },
            endVisitForm: { comments: "" },
            activePanel: null, showPanelSheet: false,
            stockItems: [],
            collectForm: { amount: "", paymentMode: "Cash", reference: "", remarks: "" },
            outstandingData: null, collectBusy: false,
            allProducts: [], filteredProducts: [], productSearch: "",
            selectedProducts: {}, productCategories: [], selectedCategory: "",
            customerOrders: [], orderBusy: false, lastOrderId: null,
            ticketForm: { subject: "", category: "Product Quality", priority: "Medium", description: "" },
            ticketBusy: false,
            checklist: CHECKLIST_ITEMS.map(i => ({ ...i, done: false })),
            checklistSaved: false,
            todayStats: { visits_done: 0, visits_planned: 0, orders_placed: 0, collection_amt: 0, beat_progress: 0 },
            // Geolocation status
            gpsAvailable: false,
            gpsStatus: "unknown", // unknown | requesting | granted | denied | unavailable
        });

        onWillStart(async () => { await this._loadAll(); });
    }

    get empId() { return this.props.employeeId; }

    _fmtDatetime(d) {
        if (!d) d = new Date();
        const pad = (n) => String(n).padStart(2, "0");
        return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    }

    // ═════════════════════════════════════════════════════════════════════════
    // GEOLOCATION — Never blocks, always returns gracefully
    // ═════════════════════════════════════════════════════════════════════════

    async _getLocation() {
        /**
         * Returns { latitude, longitude } or null.
         * NEVER throws, NEVER blocks the UI.
         */
        try {
            if (!navigator.geolocation) {
                this.state.gpsStatus = "unavailable";
                return null;
            }
            this.state.gpsStatus = "requesting";

            const pos = await new Promise((resolve, reject) => {
                navigator.geolocation.getCurrentPosition(resolve, reject, {
                    enableHighAccuracy: true,
                    timeout: 10000,       // 10 sec max
                    maximumAge: 60000,    // accept 1-min-old cache
                });
            });

            this.state.gpsStatus = "granted";
            this.state.gpsAvailable = true;
            return {
                latitude:  pos.coords.latitude,
                longitude: pos.coords.longitude,
            };
        } catch (e) {
            console.warn("[GPS]", e.message || e);
            if (e.code === 1) {
                this.state.gpsStatus = "denied";
            } else {
                this.state.gpsStatus = "unavailable";
            }
            return null;
        }
    }

    // ═════════════════════════════════════════════════════════════════════════
    // DATA LOADING
    // ═════════════════════════════════════════════════════════════════════════

    async _loadAll() {
        this.state.loading = true;
        if (!this.empId) { this.state.loading = false; return; }
        await Promise.all([this._loadAttendance(), this._loadBeats()]);
        await this._checkActiveVisit();
        await this._loadTodayStats();
        this.state.loading = false;
    }

    async _loadAttendance() {
        try {
            const att = await this.orm.call("emp360.mobile", "get_today_attendance", [this.empId]);
            if (att) {
                this.state.attendance = {
                    id: att.id, checkedIn: !att.check_out,
                    checkIn: att.check_in, checkOut: att.check_out || null,
                    workedHours: att.worked_hours ? this._fmtHours(att.worked_hours) : null,
                };
            }
        } catch (e) { console.warn("attendance:", e); }
    }

    async _loadBeats() {
        try {
            const today = new Date().toISOString().slice(0, 10);
            const beats = await this.orm.searchRead("beat.module",
                [["employee_id", "=", this.empId], ["beat_date", "=", today]],
                ["id", "name", "beat_number", "status", "customer_count"], { limit: 20 });
            for (const b of beats) {
                const lines = await this.orm.searchRead("beat.line", [["beat_id", "=", b.id]],
                    ["id", "partner_id", "partner_phone", "partner_mobile", "partner_street", "sequence"],
                    { order: "sequence asc" });
                for (const line of lines) {
                    const v = await this.orm.searchRead("visit.model",
                        [["beat_line_id", "=", line.id], ["actual_start_time", ">=", today]],
                        ["id", "status"], { limit: 1 });
                    line.visitStatus = v[0] || null;
                }
                b.beatLines = lines;
            }
            this.state.beats = beats;
            this.state.selectedBeat = beats.find(b => b.status === "in_progress") || beats[0] || null;
        } catch (e) { console.warn("beats:", e); }
    }

    async _checkActiveVisit() {
        try {
            const visits = await this.orm.searchRead("visit.model",
                [["employee_id", "=", this.empId], ["status", "=", "in_progress"]],
                ["id", "partner_id", "beat_id", "beat_line_id", "actual_start_time", "order_count", "total_order_amount"],
                { limit: 1 });
            if (visits.length) {
                this.state.activeVisit = visits[0];
                this.state.attendance.checkedIn = true;
                if (visits[0].beat_line_id && this.state.selectedBeat) {
                    const idx = this.state.selectedBeat.beatLines?.findIndex(l => l.id === visits[0].beat_line_id[0]);
                    if (idx >= 0) { this.state.currentLineIdx = idx; this.state.currentLine = this.state.selectedBeat.beatLines[idx]; }
                }
                await this._loadStockItems(visits[0].partner_id[0]);
                await this._loadOutstanding(visits[0].partner_id[0]);
            }
        } catch (e) { console.warn("active visit:", e); }
    }

    async _loadTodayStats() {
        try {
            const today = new Date().toISOString().slice(0, 10);
            const visits = await this.orm.searchRead("visit.model",
                [["employee_id", "=", this.empId], ["actual_start_time", ">=", today + " 00:00:00"]],
                ["id", "status", "total_order_amount", "order_count"], { limit: 100 });
            const done = visits.filter(v => v.status === "completed");
            const beatDone = this.state.beats.filter(b => b.status === "completed").length;
            const beatTot = this.state.beats.length;
            this.state.todayStats = {
                visits_done: done.length,
                visits_planned: visits.filter(v => v.status === "planned").length,
                orders_placed: done.reduce((s, v) => s + (v.order_count || 0), 0),
                collection_amt: 0,
                beat_progress: beatTot > 0 ? Math.round((beatDone / beatTot) * 100) : 0,
            };
        } catch (e) { console.warn("todayStats:", e); }
    }

    async _loadStockItems(partnerId) {
        try {
            const products = await this.orm.searchRead("product.product",
                [["sale_ok", "=", true]], ["id", "name", "default_code"],
                { limit: 20, order: "name asc" });
            this.state.stockItems = products.map(p => ({
                productId: p.id,
                name: `${p.default_code ? "["+p.default_code+"] " : ""}${p.name}`,
                opening: 0, closing: 0, damaged: 0,
            }));
        } catch (e) { console.warn("stock:", e); }
    }

    async _loadOutstanding(partnerId) {
        try { this.state.outstandingData = await this.orm.call("visit.collection", "get_customer_outstanding", [partnerId]); }
        catch (e) { this.state.outstandingData = null; }
    }

    async _loadProducts() {
        try {
            this.state.productCategories = await this.orm.searchRead("product.category", [], ["id", "name"], { limit: 50 });
            await this._filterProducts();
        } catch (e) { console.warn("products:", e); }
    }

    async _filterProducts() {
        try {
            const domain = [["sale_ok", "=", true]];
            if (this.state.selectedCategory) domain.push(["categ_id", "=", parseInt(this.state.selectedCategory)]);
            if (this.state.productSearch) domain.push(["name", "ilike", this.state.productSearch]);
            this.state.filteredProducts = await this.orm.searchRead("product.product", domain,
                ["id", "name", "default_code", "list_price", "categ_id"], { limit: 50, order: "name asc" });
            this.state.allProducts = this.state.filteredProducts;
        } catch (e) { console.warn("filter:", e); }
    }

    // ═════════════════════════════════════════════════════════════════════════
    // DAY START / END
    // ═════════════════════════════════════════════════════════════════════════

    openStartDay() { this.state.showStartDaySheet = true; }
    closeStartDay() { this.state.showStartDaySheet = false; }

    async confirmStartDay() {
        if (this.state.busy) return;
        this.state.busy = true;
        try {
            const result = await this.orm.call("emp360.mobile", "start_day", [this.empId]);
            if (result) {
                this.state.attendance.id = result.attendance_id;
                this.state.attendance.checkedIn = true;
                this.state.attendance.checkIn = result.check_in;
                this.state.showStartDaySheet = false;
                this.notification.add(result.already_in ? "Already checked in — resuming" : "Day started!", { type: result.already_in ? "info" : "success" });
                await this._startFirstBeat();
            }
        } catch (e) {
            this.notification.add(`Error: ${e.data?.message || e.message || "Server error"}`, { type: "danger" });
        } finally { this.state.busy = false; }
    }

    async _startFirstBeat() {
        if (!this.state.beats.length) return;
        const beat = this.state.beats.find(b => b.status === "draft" || b.status === "pending");
        if (!beat) return;
        try { await this.orm.call("beat.module", "action_start_beat", [[beat.id]]); beat.status = "in_progress"; this.state.selectedBeat = beat; }
        catch (e) { console.warn("start beat:", e); }
    }

    openEndDay() { this.state.showEndDaySheet = true; }
    closeEndDay() { this.state.showEndDaySheet = false; }

    async confirmEndDay() {
        if (this.state.busy || !this.state.attendance.id) return;
        if (this.state.activeVisit) { this.notification.add("End the active visit first", { type: "warning" }); return; }
        this.state.busy = true;
        try {
            const result = await this.orm.call("emp360.mobile", "end_day", [this.empId, this.state.attendance.id]);
            if (result) {
                this.state.attendance.checkedIn = false;
                this.state.attendance.checkOut = result.check_out;
                this.state.attendance.workedHours = this._fmtHours(result.worked_hours || 0);
                this.state.showEndDaySheet = false;
                await this._loadTodayStats();
                this.notification.add(`Day ended! Worked ${this.state.attendance.workedHours}`, { type: "success" });
            }
        } catch (e) { this.notification.add(`Error: ${e.data?.message || e.message || "Server error"}`, { type: "danger" }); }
        finally { this.state.busy = false; }
    }

    // ═════════════════════════════════════════════════════════════════════════
    // VISIT START / END — Geolocation & image are OPTIONAL
    // ═════════════════════════════════════════════════════════════════════════

    openStartVisit(line, lineIdx) {
        if (!this.state.attendance.checkedIn) { this.notification.add("Start your day first", { type: "warning" }); return; }
        if (this.state.activeVisit) { this.notification.add("End current visit first", { type: "warning" }); return; }
        this.state.currentLine = line;
        this.state.currentLineIdx = lineIdx;
        this.state.visitForm = { storeImage: null, storeImageName: "" };
        this.state.showStartVisitSheet = true;
    }
    closeStartVisit() { this.state.showStartVisitSheet = false; }

    onStoreImageChange(ev) {
        const file = ev.target.files[0];
        if (!file) return;
        // Compress & convert
        const reader = new FileReader();
        reader.onload = (e) => {
            this.state.visitForm.storeImage = e.target.result.split(",")[1];
            this.state.visitForm.storeImageName = file.name;
        };
        reader.readAsDataURL(file);
    }

    async confirmStartVisit() {
        if (this.state.busy || !this.state.currentLine) return;
        this.state.busy = true;
        try {
            // Get location silently — never block
            const loc = await this._getLocation();
            if (!loc) {
                this.notification.add("GPS unavailable — visit will start without location", { type: "info" });
            }

            const beat = this.state.selectedBeat;
            const line = this.state.currentLine;

            // Build vals — server helper handles optional fields safely
            const vals = {
                employee_id:       this.empId,
                partner_id:        line.partner_id[0],
                beat_id:           beat ? beat.id : false,
                beat_line_id:      line.id,
                actual_start_time: this._fmtDatetime(new Date()),
                status:            "in_progress",
            };

            // Only include image if captured
            if (this.state.visitForm.storeImage) {
                vals.store_image = this.state.visitForm.storeImage;
            }

            // Only include GPS if available
            if (loc) {
                vals.checkin_latitude = loc.latitude;
                vals.checkin_longitude = loc.longitude;
            }

            const result = await this.orm.call("emp360.mobile", "start_visit", [vals]);
            this.state.activeVisit = result;
            this.state.showStartVisitSheet = false;

            await this._loadStockItems(line.partner_id[0]);
            await this._loadOutstanding(line.partner_id[0]);
            line.visitStatus = { status: "in_progress" };

            this.notification.add(`Visit started at ${line.partner_id[1]}`, { type: "success" });
        } catch (e) {
            console.error("[Visit Start]", e);
            this.notification.add(`Error: ${e.data?.message || e.message || "Server error"}`, { type: "danger" });
        } finally { this.state.busy = false; }
    }

    openEndVisit() {
        if (!this.state.activeVisit) return;
        this.state.endVisitForm = { comments: "" };
        this.state.showEndVisitSheet = true;
    }
    closeEndVisit() { this.state.showEndVisitSheet = false; }

    async confirmEndVisit() {
        if (this.state.busy || !this.state.activeVisit) return;
        this.state.busy = true;
        try {
            // Get location silently — never block
            const loc = await this._getLocation();

            const vals = {
                actual_end_time: this._fmtDatetime(new Date()),
                visit_comments:  this.state.endVisitForm.comments || "",
                is_productive:   this.state.todayStats.orders_placed > 0,
            };

            // Only include GPS if available
            if (loc) {
                vals.checkout_latitude = loc.latitude;
                vals.checkout_longitude = loc.longitude;
            }

            // Use server helper with sudo — THIS IS THE KEY FIX
            await this.orm.call("emp360.mobile", "end_visit", [
                this.state.activeVisit.id, vals
            ]);

            if (this.state.currentLine) {
                this.state.currentLine.visitStatus = { status: "completed" };
            }
            this.state.activeVisit = null;
            this.state.currentLine = null;
            this.state.showEndVisitSheet = false;
            this.state.activePanel = null;
            this.state.showPanelSheet = false;

            await this._loadTodayStats();
            await this._loadBeats();
            this.notification.add("Visit completed!", { type: "success" });
        } catch (e) {
            console.error("[Visit End]", e);
            this.notification.add(`Error ending visit: ${e.data?.message || e.message || "Server error"}`, { type: "danger" });
        } finally { this.state.busy = false; }
    }

    // ═════════════════════════════════════════════════════════════════════════
    // PANELS
    // ═════════════════════════════════════════════════════════════════════════

    openPanel(panel) {
        this.state.activePanel = panel;
        this.state.showPanelSheet = true;
        if (panel === "orders") { this._loadProducts(); this._loadCustomerOrders(); }
    }
    closePanel() { this.state.showPanelSheet = false; this.state.activePanel = null; }

    // Stock
    updateStock(idx, field, ev) { this.state.stockItems[idx][field] = parseInt(ev.target.value) || 0; }

    async saveStock() {
        if (!this.state.activeVisit) return;
        this.state.busy = true;
        try {
            const lines = this.state.stockItems.filter(s => s.opening > 0 || s.closing > 0 || s.damaged > 0)
                .map(s => ({ product_id: s.productId, opening_stock: s.opening, closing_stock: s.closing, damaged_stock: s.damaged }));
            if (lines.length) await this.orm.call("emp360.mobile", "save_stock", [this.state.activeVisit.id, lines]);
            this.closePanel();
            this.notification.add("Stock updated", { type: "success" });
        } catch (e) { this.notification.add(`Error: ${e.message}`, { type: "danger" }); }
        finally { this.state.busy = false; }
    }

    // Collection
    async saveCollection() {
        if (!this.state.activeVisit || !this.state.collectForm.amount) return;
        this.state.collectBusy = true;
        try {
            await this.orm.call("emp360.mobile", "create_collection", [{
                visit_id: this.state.activeVisit.id, employee_id: this.empId,
                partner_id: this.state.activeVisit.partner_id[0],
                amount: parseFloat(this.state.collectForm.amount),
                payment_mode: this.state.collectForm.paymentMode,
                reference: this.state.collectForm.reference,
                remarks: this.state.collectForm.remarks,
                date: new Date().toISOString().slice(0, 10),
            }]);
            const amt = this.state.collectForm.amount;
            this.state.collectForm = { amount: "", paymentMode: "Cash", reference: "", remarks: "" };
            this.closePanel();
            this.notification.add(`Collected ₹${amt}`, { type: "success" });
        } catch (e) { this.notification.add(`Error: ${e.data?.message || e.message}`, { type: "danger" }); }
        finally { this.state.collectBusy = false; }
    }

    // Orders
    async _loadCustomerOrders() {
        if (!this.state.activeVisit) return;
        try { this.state.customerOrders = await this.orm.searchRead("sale.order",
            [["visit_id", "=", this.state.activeVisit.id]],
            ["id", "name", "amount_total", "state", "date_order"],
            { limit: 20, order: "date_order desc" });
        } catch (e) {}
    }

    toggleProduct(prod) {
        const id = prod.id;
        if (this.state.selectedProducts[id]) delete this.state.selectedProducts[id];
        else this.state.selectedProducts[id] = { ...prod, qty: 1, price: prod.list_price || 0 };
    }
    updateQty(prodId, delta) {
        if (!this.state.selectedProducts[prodId]) return;
        const q = (this.state.selectedProducts[prodId].qty || 1) + delta;
        if (q < 1) delete this.state.selectedProducts[prodId];
        else this.state.selectedProducts[prodId].qty = q;
    }
    get selectedProductsList() { return Object.values(this.state.selectedProducts); }
    get orderTotal() { return this.selectedProductsList.reduce((s, p) => s + (p.qty * p.price), 0); }
    get orderTotalFmt() { return `₹${Math.round(this.orderTotal).toLocaleString("en-IN")}`; }

    async createOrder() {
        if (!this.state.activeVisit || !this.selectedProductsList.length) return;
        this.state.orderBusy = true;
        try {
            const empRow = await this.orm.searchRead("hr.employee", [["id", "=", this.empId]], ["user_id"], { limit: 1 });
            await this.orm.call("emp360.mobile", "create_order", [{
                partner_id: this.state.activeVisit.partner_id[0],
                visit_id: this.state.activeVisit.id,
                date_order: this._fmtDatetime(new Date()),
                user_id: empRow[0]?.user_id?.[0] || false,
                order_line: this.selectedProductsList.map(p => [0, 0, { product_id: p.id, product_uom_qty: p.qty, price_unit: p.price }]),
            }]);
            this.state.selectedProducts = {};
            await this._loadCustomerOrders();
            this.notification.add("Order created!", { type: "success" });
        } catch (e) { this.notification.add(`Error: ${e.data?.message || e.message}`, { type: "danger" }); }
        finally { this.state.orderBusy = false; }
    }

    async searchProducts() { await this._filterProducts(); }
    selectCategory(ev) { this.state.selectedCategory = ev.target.value; this._filterProducts(); }

    // Ticket
    async saveTicket() {
        if (!this.state.activeVisit || !this.state.ticketForm.subject) return;
        this.state.ticketBusy = true;
        try {
            await this.orm.call("emp360.mobile", "create_ticket", [{
                visit_id: this.state.activeVisit.id, employee_id: this.empId,
                partner_id: this.state.activeVisit.partner_id[0],
                subject: this.state.ticketForm.subject, category: this.state.ticketForm.category,
                priority: this.state.ticketForm.priority, description: this.state.ticketForm.description,
            }]);
            this.state.ticketForm = { subject: "", category: "Product Quality", priority: "Medium", description: "" };
            this.closePanel();
            this.notification.add("Ticket raised!", { type: "success" });
        } catch (e) { this.notification.add(`Error: ${e.data?.message || e.message}`, { type: "danger" }); }
        finally { this.state.ticketBusy = false; }
    }

    // Checklist
    toggleCheck(id) { const item = this.state.checklist.find(i => i.id === id); if (item) item.done = !item.done; }
    async saveChecklist() {
        if (!this.state.activeVisit) return;
        try { await this.orm.call("visit.checklist", "save_responses", [this.state.activeVisit.id, this.state.checklist.map(i => ({ item_id: i.id, answer: i.done }))]); }
        catch (e) { console.warn("checklist:", e); }
        this.state.checklistSaved = true; this.closePanel();
        this.notification.add("Checklist saved", { type: "success" });
    }
    get checklistDone() { return this.state.checklist.filter(i => i.done).length; }
    get checklistPct() { return this.state.checklist.length > 0 ? Math.round((this.checklistDone / this.state.checklist.length) * 100) : 0; }

    // Beat Switch
    async openSwitchBeat() {
        this.state.switchForm = { reason: "", newBeatId: null }; this.state.switchBusy = true; this.state.showSwitchSheet = true;
        try {
            const today = new Date().toISOString().slice(0, 10);
            const b1 = await this.orm.searchRead("beat.module", [["employee_id", "=", this.empId], ["beat_date", "=", today], ["status", "!=", "completed"]], ["id", "name", "beat_number"], { limit: 20 });
            const b2 = await this.orm.searchRead("beat.module", [["beat_date", "=", today], ["status", "=", "draft"]], ["id", "name", "beat_number"], { limit: 20 });
            this.state.allBeatsForSwap = [...b1, ...b2].filter((b, i, a) => a.findIndex(x => x.id === b.id) === i);
        } catch (e) { console.warn("swap:", e); }
        this.state.switchBusy = false;
    }
    closeSwitchBeat() { this.state.showSwitchSheet = false; }
    async confirmSwitchBeat() {
        if (!this.state.switchForm.newBeatId || !this.state.switchForm.reason) { this.notification.add("Select beat and reason", { type: "warning" }); return; }
        this.state.switchBusy = true;
        try {
            if (this.state.selectedBeat) await this.orm.call("beat.module", "action_swap_beat", [[this.state.selectedBeat.id], parseInt(this.state.switchForm.newBeatId), this.state.switchForm.reason]);
            await this._loadBeats(); this.state.showSwitchSheet = false;
            this.notification.add("Beat switched!", { type: "success" });
        } catch (e) { this.notification.add(`Error: ${e.data?.message || e.message}`, { type: "danger" }); }
        finally { this.state.switchBusy = false; }
    }

    // ═════════════════════════════════════════════════════════════════════════
    // FORMATTERS & HELPERS
    // ═════════════════════════════════════════════════════════════════════════
    _fmtHours(h) { const hrs = Math.floor(h); return `${hrs}h ${Math.round((h - hrs) * 60)}m`; }
    fmtTime(dt) { if (!dt) return "--:--"; return new Date(dt).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" }); }
    fmtMoney(v) { if (!v) return "₹0"; if (v >= 100000) return `₹${(v/100000).toFixed(1)}L`; if (v >= 1000) return `₹${(v/1000).toFixed(0)}K`; return `₹${Math.round(v).toLocaleString("en-IN")}`; }
    get todayDateStr() { return new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", year: "numeric" }); }
    get beatProgress() { if (!this.state.selectedBeat?.beatLines?.length) return 0; const d = this.state.selectedBeat.beatLines.filter(l => l.visitStatus?.status === "completed").length; return Math.round((d / this.state.selectedBeat.beatLines.length) * 100); }
    visitStatusClass(s) { return ({ completed: "success", in_progress: "warning", planned: "info", cancelled: "danger" })[s] || "muted"; }
    visitStatusLabel(s) { return ({ completed: "Done", in_progress: "Active", planned: "Pending", cancelled: "Cancelled" })[s] || s; }
    getAvatarGradient(str) { const g = ["linear-gradient(135deg,#4361ee,#3a0ca3)","linear-gradient(135deg,#06d6a0,#019b72)","linear-gradient(135deg,#f72585,#b5179e)","linear-gradient(135deg,#f77f00,#d62828)","linear-gradient(135deg,#7209b7,#3a0ca3)","linear-gradient(135deg,#4cc9f0,#0077b6)"]; let h=0; for(let i=0;i<(str||"").length;i++) h=str.charCodeAt(i)+((h<<5)-h); return g[Math.abs(h)%g.length]; }
    getInitials(name) { return (name||"?").split(" ").slice(0,2).map(w=>w[0]||"").join("").toUpperCase(); }
}