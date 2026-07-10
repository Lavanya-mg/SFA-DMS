/** @odoo-module **/

import { Component, useState, onWillStart, useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class VisitList extends Component {
    static template = "employee_dashboard_v19.VisitList";
    static props = {
        employeeId: { optional: true },
        userId: { optional: true },
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            visits: [],
            filterStatus: "",
            hasMore: false,
            limit: 50,
            offset: 0,
        });

        onWillStart(async () => {
            await this.loadVisits();
        });
    }

    getEmployeeId() {
        const empId = this.props.employeeId || this.props.userId;
        if (!empId) {
            return null;
        }
        return typeof empId === 'number' ? empId : parseInt(empId, 10);
    }

    async loadVisits() {
        const employeeId = this.getEmployeeId();
        
        if (!employeeId) {
            this.state.loading = false;
            return;
        }

        try {
            this.state.loading = true;

            const domain = [["employee_id", "=", employeeId]];
            
            if (this.state.filterStatus) {
                domain.push(["status", "=", this.state.filterStatus]);
            }


            const visits = await this.orm.searchRead(
                "visit.model",
                domain,
                [
                    "id",
                    "name",
                    "employee_id",
                    "partner_id",
                    "beat_id",
                    "actual_start_time",
                    "actual_end_time",
                    "duration_display",
                    "status",
                    "is_productive",
                    "productivity_reason",
                ],
                {
                    order: "actual_start_time desc",
                    limit: this.state.limit,
                    offset: this.state.offset,
                }
            );

            this.state.visits = visits;
            this.state.hasMore = visits.length === this.state.limit;
            this.state.loading = false;
        } catch (error) {
            console.error("Error loading visits:", error);
            this.notification.add("Failed to load visits", {
                type: "danger",
            });
            this.state.loading = false;
        }
    }

    async loadMoreVisits() {
        const employeeId = this.getEmployeeId();
        
        if (!employeeId) {
            return;
        }
        
        this.state.offset += this.state.limit;
        
        try {
            const domain = [["employee_id", "=", employeeId]];
            
            if (this.state.filterStatus) {
                domain.push(["status", "=", this.state.filterStatus]);
            }

            const moreVisits = await this.orm.searchRead(
                "visit.model",
                domain,
                [
                    "id",
                    "name",
                    "employee_id",
                    "partner_id",
                    "beat_id",
                    "actual_start_time",
                    "actual_end_time",
                    "duration_display",
                    "status",
                    "is_productive",
                    "productivity_reason",
                ],
                {
                    order: "actual_start_time desc",
                    limit: this.state.limit,
                    offset: this.state.offset,
                }
            );

            this.state.visits = [...this.state.visits, ...moreVisits];
            this.state.hasMore = moreVisits.length === this.state.limit;
        } catch (error) {
            console.error("Error loading more visits:", error);
            this.notification.add("Failed to load more visits", {
                type: "danger",
            });
        }
    }

    async refreshVisits() {
        this.state.offset = 0;
        await this.loadVisits();
        this.notification.add("Visits refreshed", {
            type: "info",
        });
    }

    formatDate(datetime) {
        if (!datetime) return "-";
        const date = new Date(datetime);
        return date.toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
        });
    }

    formatTime(datetime) {
        if (!datetime) return "-";
        const date = new Date(datetime);
        return date.toLocaleTimeString("en-US", {
            hour: "2-digit",
            minute: "2-digit",
        });
    }

    getStatusText(status) {
        const statusMap = {
            planned: "Planned",
            in_progress: "In Progress",
            completed: "Completed",
            cancelled: "Cancelled",
        };
        return statusMap[status] || status;
    }

    getStatusBadge(status) {
        const badgeMap = {
            planned: "bg-info",
            in_progress: "bg-warning",
            completed: "bg-success",
            cancelled: "bg-danger",
        };
        return badgeMap[status] || "bg-secondary";
    }

    getRowClass(visit) {
        if (visit.status === "completed") return "table-success";
        if (visit.status === "in_progress") return "table-warning";
        if (visit.status === "cancelled") return "table-danger";
        return "";
    }

    viewVisit(visitId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "visit.model",
            res_id: visitId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}