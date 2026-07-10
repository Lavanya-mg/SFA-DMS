/** @odoo-module **/
/**
 * EMPLOYEE 360 — MOBILE APPLICATION
 * Odoo 18 | PWA-ready Mobile App for Field Users & Managers
 * Covers: Attendance, Beats, Visits, Orders, KPI, Collections, Tickets
 */

import { registry }              from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService }            from "@web/core/utils/hooks";
import { MobileHome }            from "./mobile_home";
import { MobileToday }           from "./mobile_today";
import { MobileVisits }          from "./mobile_visits";
import { MobileOrders }          from "./mobile_orders";
import { MobileManager }         from "./mobile_manager";
import { MobileProfile }         from "./mobile_profile";
import { MobileSchemes }         from "./mobile_schemes";

// ─────────────────────────────────────────────────────────────────────────────
// Navigation configuration
// ─────────────────────────────────────────────────────────────────────────────
const USER_NAV = [
    { id: "home",    label: "Home",    icon: "fa-home",          gradient: "linear-gradient(135deg,#4361ee,#3a0ca3)" },
    { id: "today",   label: "Workday", icon: "fa-briefcase",     gradient: "linear-gradient(135deg,#06d6a0,#019b72)" },
    { id: "visits",  label: "Visits",  icon: "fa-map-marker",    gradient: "linear-gradient(135deg,#4cc9f0,#0077b6)" },
    { id: "orders",  label: "Orders",  icon: "fa-shopping-cart", gradient: "linear-gradient(135deg,#f72585,#b5179e)" },
    { id: "schemes", label: "Schemes", icon: "fa-tags",           gradient: "linear-gradient(135deg,#7209b7,#3a0ca3)" },
    { id: "profile", label: "More",    icon: "fa-ellipsis-h",    gradient: "linear-gradient(135deg,#7209b7,#3a0ca3)" },
];

const MANAGER_NAV = [
    { id: "home",    label: "Dashboard", icon: "fa-tachometer",    gradient: "linear-gradient(135deg,#4361ee,#3a0ca3)" },
    { id: "team",    label: "Team",      icon: "fa-users",          gradient: "linear-gradient(135deg,#06d6a0,#019b72)" },
    { id: "visits",  label: "Visits",    icon: "fa-map-marker",     gradient: "linear-gradient(135deg,#4cc9f0,#0077b6)" },
    { id: "orders",  label: "Orders",    icon: "fa-shopping-cart",  gradient: "linear-gradient(135deg,#f72585,#b5179e)" },
    { id: "profile", label: "More",      icon: "fa-ellipsis-h",     gradient: "linear-gradient(135deg,#7209b7,#3a0ca3)" },
];

const SCREEN_TITLES = {
    home:    "Employee 360",
    today:   "My Workday",
    visits:  "Visit History",
    orders:  "Sales Orders",
    schemes: "Schemes",
    team:    "My Team",
    profile: "More",
};

const SCREEN_GRADIENTS = {
    home:    "linear-gradient(135deg,#0d0d1f 0%,#1a1a3e 60%,#0f3460 100%)",
    today:   "linear-gradient(135deg,#06d6a0,#019b72)",
    visits:  "linear-gradient(135deg,#4cc9f0,#0077b6)",
    orders:  "linear-gradient(135deg,#f72585,#b5179e)",
    schemes: "linear-gradient(135deg,#7209b7,#3a0ca3)",
    team:    "linear-gradient(135deg,#4361ee,#3a0ca3)",
    profile: "linear-gradient(135deg,#7209b7,#3a0ca3)",
};

// ─────────────────────────────────────────────────────────────────────────────
// Main Mobile App Component
// ─────────────────────────────────────────────────────────────────────────────
export class MobileApp extends Component {
    static template = "employee_mobile_v19.MobileApp";
    static props = {};
    static components = { MobileHome, MobileToday, MobileVisits, MobileOrders, MobileManager, MobileProfile, MobileSchemes };

    setup() {
        this.orm          = useService("orm");
        this.notification = useService("notification");
        this.action       = useService("action");

        this.state = useState({
            // Auth
            isManager:            false,
            employeeId:           null,
            userId:               null,
            employeeName:         "",
            employeeDept:         "",
            employeeJob:          "",
            employeeAvatar:       null,

            // Navigation
            activeScreen:         "home",
            navHistory:           [],

            // Loading
            loading:              true,
            initError:            false,

            // Badge counts
            pendingVisits:        0,
            pendingOrders:        0,

            // Quick KPI for header
            todayCheckedIn:       false,
            activeVisitCount:     0,

            // Employee list for manager
            employees:            [],
            selectedEmpId:        null,
        });

        onWillStart(async () => {
            await this._init();
        });

        onMounted(() => {
            this._addViewportMeta();
        });
    }

    // ── Initialization ───────────────────────────────────────────────────────
    async _init() {
        try {
            // 1. Get user access info
            const info = await this.orm.call("emp360.mobile", "get_user_access_info", []);
            this.state.isManager   = info.is_manager;
            this.state.employeeId  = info.employee_id;
            this.state.userId      = info.user_id;

            // 2. Load employee details
            if (this.state.employeeId) {
                const rows = await this.orm.searchRead(
                    "hr.employee",
                    [["id", "=", this.state.employeeId]],
                    ["name", "department_id", "job_id"]
                );
                if (rows.length) {
                    this.state.employeeName = rows[0].name || "";
                    this.state.employeeDept = rows[0].department_id?.[1] || "";
                    this.state.employeeJob  = rows[0].job_id?.[1]        || "";
                }
            }

            // 3. Load employees for manager
            if (this.state.isManager) {
                this.state.employees = await this.orm.call(
                    "emp360.mobile", "get_accessible_employees", []
                );
                this.state.selectedEmpId = this.state.employeeId;
                // Managers start on home (dashboard)
                this.state.activeScreen = "home";
            } else {
                // Field users start on workday
                this.state.activeScreen = "home";
            }

            // 4. Load badge counts
            await this._loadBadges();
            this.state.loading = false;

        } catch (e) {
            console.error("[MobileApp] init error:", e);
            this.state.initError = true;
            this.state.loading = false;
        }
    }

    async _loadBadges() {
        if (!this.state.employeeId) return;
        try {
            const today = new Date().toISOString().slice(0, 10);

            // Pending planned visits today
            const pendingV = await this.orm.searchRead(
                "visit.model",
                [
                    ["employee_id", "=", this.state.employeeId],
                    ["status", "in", ["planned", "in_progress"]],
                    ["planned_start_time", ">=", today + " 00:00:00"],
                    ["planned_start_time", "<=", today + " 23:59:59"],
                ],
                ["id"],
                { limit: 10 }
            );
            this.state.pendingVisits = pendingV.length;

            // Active visits
            const active = pendingV.filter ? pendingV : [];
            this.state.activeVisitCount = active.length;

            // Today's attendance
            const att = await this.orm.call(
                "hr.attendance", "get_today_attendance", [this.state.employeeId]
            );
            this.state.todayCheckedIn = att && att.check_in && !att.check_out;

        } catch (e) {
            console.warn("[MobileApp] badge load error:", e);
        }
    }

    _addViewportMeta() {
        // Ensure proper mobile viewport
        let meta = document.querySelector('meta[name="viewport"]');
        if (!meta) {
            meta = document.createElement("meta");
            meta.name = "viewport";
            document.head.appendChild(meta);
        }
        meta.content = "width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover";

        // Add theme color
        let theme = document.querySelector('meta[name="theme-color"]');
        if (!theme) {
            theme = document.createElement("meta");
            theme.name = "theme-color";
            document.head.appendChild(theme);
        }
        theme.content = "#0d0d1f";
    }

    // ── Navigation ───────────────────────────────────────────────────────────
    navigate(screenId) {
        if (screenId === this.state.activeScreen) return;

        // Field users can only access: home, today, visits, orders, profile
        if (!this.state.isManager && screenId === "team") return;

        this.state.navHistory.push(this.state.activeScreen);
        this.state.activeScreen = screenId;
        window.scrollTo(0, 0);

        // Reload badges when navigating
        this._loadBadges();
    }

    goBack() {
        if (this.state.navHistory.length > 0) {
            this.state.activeScreen = this.state.navHistory.pop();
        }
    }

    // ── Computed Properties ──────────────────────────────────────────────────
    get navItems() {
        return this.state.isManager ? MANAGER_NAV : USER_NAV;
    }

    currentTitle() {
        return SCREEN_TITLES[this.state.activeScreen] || "Employee 360";
    }

    topbarGradient() {
        return SCREEN_GRADIENTS[this.state.activeScreen] || SCREEN_GRADIENTS.home;
    }

    get canGoBack() {
        return this.state.navHistory.length > 0;
    }

    get todayDate() {
        return new Date().toLocaleDateString("en-IN", {
            weekday: "short", day: "numeric", month: "short"
        });
    }

    get greeting() {
        const h = new Date().getHours();
        if (h < 12) return "Good Morning";
        if (h < 17) return "Good Afternoon";
        return "Good Evening";
    }

    get greetingIcon() {
        const h = new Date().getHours();
        if (h < 12) return "fa-sun-o";
        if (h < 17) return "fa-cloud";
        return "fa-moon-o";
    }

    get employeeInitials() {
        return this.state.employeeName
            .split(" ").slice(0, 2).map(w => w[0] || "").join("").toUpperCase() || "U";
    }

    // Badge for nav items
    getBadge(navId) {
        if (navId === "visits" && this.state.pendingVisits > 0) return this.state.pendingVisits;
        if (navId === "today" && this.state.todayCheckedIn) return null;
        return null;
    }

    // ── Event Handlers ───────────────────────────────────────────────────────
    onNavigate(screenId) {
        this.navigate(screenId);
    }

    async onRefresh() {
        await this._loadBadges();
        this.notification.add("Refreshed", { type: "info" });
    }

    selectEmployee(ev) {
        const id = parseInt(ev.target.value);
        this.state.selectedEmpId = id || this.state.employeeId;
    }
}
MobileApp.props = {
    // Keep your own custom props here if you have any, then add:
    action: { type: Object, optional: true },
    actionId: { type: Number, optional: true },
    updateActionState: { type: Function, optional: true },
    className: { type: String, optional: true },
};

registry.category("actions").add("employee_mobile_app_v19", MobileApp);
