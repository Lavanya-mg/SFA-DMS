/** @odoo-module **/

import { Component, useState, onMounted, onWillUpdateProps, onWillUnmount, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * LocationMapCard — Analytics Board widget for Employee 360
 *
 * Renders an interactive Leaflet map on the Analytics Board (Overview tab)
 * showing today's visit locations and the employee's check-in point.
 *
 * Marker colour legend:
 *   Purple  (#7209b7) — Employee check-in location
 *   Green   (#06d6a0) — Completed visits
 *   Amber   (#f77f00) — In-progress visits
 *   Blue    (#4361ee) — Planned visits
 *   Red     (#ef476f) — Cancelled visits
 */
export class LocationMapCard extends Component {
    static template = "employee_dashboard_v19.LocationMapCard";
    static props = {
        employeeId: { type: Number, optional: true },
    };

    setup() {
        this.orm       = useService("orm");
        this.mapRef    = useRef("mapContainer");
        this._leafletMap = null;

        this.state = useState({
            loading:  false,
            visits:   [],
            checkin:  null,
            isEmpty:  false,
            error:    null,
        });

        onMounted(async () => {
            if (this.props.employeeId) {
                await this.loadLocationData(this.props.employeeId);
            }
        });

        onWillUpdateProps(async (nextProps) => {
            if (nextProps.employeeId !== this.props.employeeId) {
                this._destroyMap();
                this.state.visits  = [];
                this.state.checkin = null;
                this.state.isEmpty = false;
                this.state.error   = null;
                if (nextProps.employeeId) {
                    await this.loadLocationData(nextProps.employeeId);
                }
            }
        });

        onWillUnmount(() => {
            this._destroyMap();
        });
    }

    // ── Map lifecycle ──────────────────────────────────────────────

    _destroyMap() {
        if (this._leafletMap) {
            this._leafletMap.remove();
            this._leafletMap = null;
        }
    }

    // ── Data loading ───────────────────────────────────────────────

    async loadLocationData(empId) {
        this.state.loading = true;
        this.state.error   = null;
        try {
            const today = new Date().toISOString().split("T")[0];

            // ── Today's visits ──────────────────────────────────────
            const visits = await this.orm.searchRead(
                "visit.model",
                [
                    ["employee_id",       "=",  empId],
                    ["actual_start_time", ">=", today + " 00:00:00"],
                    ["actual_start_time", "<=", today + " 23:59:59"],
                ],
                ["id", "partner_id", "status", "actual_start_time", "actual_end_time"],
                { limit: 100 }
            );

            // ── Partner GPS coordinates ─────────────────────────────
            const partnerIds = [...new Set(
                visits.map(v => v.partner_id && v.partner_id[0]).filter(Boolean)
            )];

            const partnerMap = {};
            if (partnerIds.length > 0) {
                const partners = await this.orm.searchRead(
                    "res.partner",
                    [["id", "in", partnerIds]],
                    ["id", "partner_latitude", "partner_longitude", "name"]
                );
                for (const p of partners) {
                    partnerMap[p.id] = p;
                }
            }

            // ── Today's check-in (hr.attendance) ───────────────────
            const attendances = await this.orm.searchRead(
                "hr.attendance",
                [
                    ["employee_id", "=",  empId],
                    ["check_in",    ">=", today + " 00:00:00"],
                    ["check_in",    "<=", today + " 23:59:59"],
                ],
                ["id", "check_in", "checkin_latitude", "checkin_longitude", "checkin_full_address"],
                { limit: 1, order: "check_in desc" }
            );

            // ── Enrich visits ───────────────────────────────────────
            this.state.visits = visits.map(v => {
                const pid     = v.partner_id ? v.partner_id[0] : null;
                const partner = pid ? partnerMap[pid] : null;
                return {
                    ...v,
                    partner_name: v.partner_id ? v.partner_id[1] : "Unknown",
                    lat: partner ? partner.partner_latitude  : null,
                    lng: partner ? partner.partner_longitude : null,
                };
            });

            this.state.checkin = attendances.length > 0 ? attendances[0] : null;
            this.state.isEmpty = this.state.visits.length === 0 && !this.state.checkin;

        } catch (e) {
            console.error("LocationMapCard.loadLocationData:", e);
            this.state.error = "Could not load location data.";
        } finally {
            this.state.loading = false;
            // Let OWL flush the DOM before touching Leaflet
            setTimeout(() => this._initMap(), 60);
        }
    }

    async refreshLocation() {
        const empId = this.props.employeeId;
        if (empId) {
            this._destroyMap();
            await this.loadLocationData(empId);
        }
    }

    // ── Map initialisation ─────────────────────────────────────────

    _initMap() {
        const L  = window.L;
        const el = this.mapRef && this.mapRef.el;
        if (!L || !el) return;

        this._destroyMap();

        this._leafletMap = L.map(el, {
            zoomControl:       true,
            scrollWheelZoom:   false,
            attributionControl: true,
        });

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
            attribution: "© <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a>",
            maxZoom: 19,
        }).addTo(this._leafletMap);

        const bounds = [];

        // ── Check-in marker (purple) ────────────────────────────────
        const ci = this.state.checkin;
        if (ci && ci.checkin_latitude && ci.checkin_longitude) {
            const lat = parseFloat(ci.checkin_latitude);
            const lng = parseFloat(ci.checkin_longitude);
            if (lat && lng) {
                const m = L.marker([lat, lng], { icon: this._makeIcon("#7209b7", "fa-user-circle") })
                    .addTo(this._leafletMap);
                m.bindPopup(this._checkinPopup(ci));
                bounds.push([lat, lng]);
            }
        }

        // ── Visit markers ───────────────────────────────────────────
        for (const v of this.state.visits) {
            const lat = v.lat ? parseFloat(v.lat) : null;
            const lng = v.lng ? parseFloat(v.lng) : null;
            if (!lat || !lng) continue;

            const color = this._statusColor(v.status);
            const icon  = this._statusFaIcon(v.status);
            const m = L.marker([lat, lng], { icon: this._makeIcon(color, icon) })
                .addTo(this._leafletMap);
            m.bindPopup(this._visitPopup(v, color));
            bounds.push([lat, lng]);
        }

        // ── Fit view ────────────────────────────────────────────────
        if (bounds.length === 1) {
            this._leafletMap.setView(bounds[0], 14);
        } else if (bounds.length > 1) {
            this._leafletMap.fitBounds(bounds, { padding: [36, 36], maxZoom: 16 });
        } else {
            // Default: India centroid
            this._leafletMap.setView([20.5937, 78.9629], 5);
        }
    }

    // ── Icon & popup helpers ───────────────────────────────────────

    _makeIcon(color, faClass) {
        const L = window.L;
        return L.divIcon({
            className: "",
            html: `
                <div style="
                    position:relative;
                    width:36px;height:36px;
                    background:${color};
                    border-radius:50% 50% 50% 0;
                    border:2.5px solid #fff;
                    transform:rotate(-45deg);
                    box-shadow:0 3px 10px rgba(0,0,0,.35);
                    display:flex;align-items:center;justify-content:center;
                ">
                    <i class="fa ${faClass}" style="
                        color:#fff;font-size:13px;
                        transform:rotate(45deg);
                        pointer-events:none;
                    "></i>
                </div>`,
            iconSize:    [36, 36],
            iconAnchor:  [18, 36],
            popupAnchor: [0, -38],
        });
    }

    _checkinPopup(ci) {
        return `
            <div style="min-width:190px;font-family:'Segoe UI',Arial,sans-serif;">
                <div style="
                    background:linear-gradient(135deg,#7209b7,#3a0ca3);
                    color:#fff;padding:8px 12px;border-radius:8px 8px 0 0;
                    font-weight:700;font-size:13px;
                    display:flex;align-items:center;gap:6px;">
                    <i class="fa fa-user-circle"></i> Check-in Location
                </div>
                <div style="padding:10px 12px;border:1px solid #ede9fe;border-top:none;border-radius:0 0 8px 8px;background:#faf5ff;">
                    <div style="font-size:11px;color:#6b7280;margin-bottom:2px;">
                        <i class="fa fa-clock-o me-1"></i>${ci.check_in ? new Date(ci.check_in).toLocaleTimeString("en-US",{hour:"2-digit",minute:"2-digit"}) : "--"}
                    </div>
                    <div style="font-size:11px;color:#374151;">
                        <i class="fa fa-map-marker me-1" style="color:#7209b7;"></i>
                        ${ci.checkin_full_address || "Check-in point"}
                    </div>
                </div>
            </div>`;
    }

    _visitPopup(v, color) {
        const statusLabel = this.statusLabel(v.status);
        const time = v.actual_start_time
            ? new Date(v.actual_start_time).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" })
            : "--";
        return `
            <div style="min-width:190px;font-family:'Segoe UI',Arial,sans-serif;">
                <div style="
                    background:linear-gradient(135deg,${color},${color}cc);
                    color:#fff;padding:8px 12px;border-radius:8px 8px 0 0;
                    font-weight:700;font-size:13px;
                    display:flex;align-items:center;gap:6px;">
                    <i class="fa fa-building"></i> ${v.partner_name}
                </div>
                <div style="padding:10px 12px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 8px 8px;background:#f9fafb;">
                    <div style="margin-bottom:4px;">
                        <span style="
                            background:${color}22;color:${color};
                            border:1px solid ${color}55;border-radius:20px;
                            padding:2px 8px;font-size:10px;font-weight:700;
                        ">${statusLabel}</span>
                    </div>
                    <div style="font-size:11px;color:#6b7280;">
                        <i class="fa fa-clock-o me-1"></i>${time}
                    </div>
                    <div style="font-size:10px;color:#9ca3af;margin-top:4px;">
                        <i class="fa fa-map-marker me-1"></i>
                        ${Number(v.lat).toFixed(4)}, ${Number(v.lng).toFixed(4)}
                    </div>
                </div>
            </div>`;
    }

    // ── Utility helpers ────────────────────────────────────────────

    _statusColor(status) {
        return {
            completed:   "#06d6a0",
            in_progress: "#f77f00",
            planned:     "#4361ee",
            cancelled:   "#ef476f",
        }[status] || "#9ca3af";
    }

    _statusFaIcon(status) {
        return {
            completed:   "fa-check",
            in_progress: "fa-spinner",
            planned:     "fa-calendar",
            cancelled:   "fa-times",
        }[status] || "fa-circle";
    }

    statusLabel(status) {
        return {
            completed:   "Completed",
            in_progress: "In Progress",
            planned:     "Planned",
            cancelled:   "Cancelled",
        }[status] || status;
    }

    statusBadgeStyle(status) {
        return {
            completed:   "background:#d1fae5;color:#065f46;border:1px solid #a7f3d0;",
            in_progress: "background:#fef3c7;color:#92400e;border:1px solid #fcd34d;",
            planned:     "background:#dbeafe;color:#1e40af;border:1px solid #bfdbfe;",
            cancelled:   "background:#fee2e2;color:#991b1b;border:1px solid #fca5a5;",
        }[status] || "background:#f3f4f6;color:#6b7280;border:1px solid #e5e7eb;";
    }

    markerDotStyle(status) {
        return `background:${this._statusColor(status)};`;
    }

    formatTime(dt) {
        if (!dt) return "-";
        return new Date(dt).toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    }

    formatCoord(val) {
        return Number(val).toFixed(4);
    }

    openGoogleMaps(lat, lng) {
        window.open(`https://www.google.com/maps?q=${lat},${lng}`, "_blank");
    }

    get hasMapPoints() {
        const ci = this.state.checkin;
        const hasCheckin = ci && ci.checkin_latitude && ci.checkin_longitude;
        const hasVisit = this.state.visits.some(v => v.lat && v.lng);
        return hasCheckin || hasVisit;
    }

    get visitStats() {
        const v = this.state.visits;
        return {
            total:       v.length,
            completed:   v.filter(x => x.status === "completed").length,
            in_progress: v.filter(x => x.status === "in_progress").length,
            planned:     v.filter(x => x.status === "planned").length,
            cancelled:   v.filter(x => x.status === "cancelled").length,
            withGps:     v.filter(x => x.lat && x.lng).length,
        };
    }
}
