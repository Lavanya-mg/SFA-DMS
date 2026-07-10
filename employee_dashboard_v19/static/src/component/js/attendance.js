/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { useBus } from "@web/core/utils/hooks";

export class AttendanceList extends Component {

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            attendanceRecords: [],
            attendanceFromDate: "",
            attendanceToDate: "",
        });

        useBus(this.env.bus, 'attendance-refresh', async () => {
            console.log("🔄 Received attendance-refresh event");
            await this.loadAttendanceData();
        });

        onWillStart(async () => {
            await this.loadAttendance();
        });

        onMounted(() => {
            this.refreshInterval = setInterval(async () => {
                const hasActiveAttendance = this.state.attendanceRecords.some(
                    record => record.status === 'In Progress'
                );
                if (hasActiveAttendance) {
                    console.log("Auto-refreshing attendance data...");
                    await this.loadAttendanceData();
                }
            }, 30000); 
        });

        onWillUnmount(() => {
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
            }
        });
    }

    convertUTCToLocal(utcDateString) {
        if (!utcDateString) return null;
        
        const utcDate = new Date(utcDateString + (utcDateString.includes('Z') ? '' : 'Z'));
        return utcDate;
    }

    
    formatLocalDate(date) {
        if (!date) return "";
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }


    formatLocalTime(date) {
        if (!date) return "";
        return date.toLocaleTimeString('en-US', { 
            hour: '2-digit', 
            minute: '2-digit', 
            hour12: true 
        });
    }

    async onAttendanceDateChange() {
        await this.loadAttendanceData();
    }

    async loadAttendance() {
        if (!this.props.employeeId) {
            this.state.loading = false;
            return;
        }

        try {
            const today = new Date();
            const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);
            const lastDay = new Date(today.getFullYear(), today.getMonth() + 1, 0);

            this.state.attendanceFromDate = this.formatLocalDate(firstDay);
            this.state.attendanceToDate = this.formatLocalDate(lastDay);

            await this.loadAttendanceData();
        } catch (error) {
            console.error("Error loading attendance:", error);
            this.state.loading = false;
        }
    }

    async loadAttendanceData() {
        if (!this.props.employeeId) {
            this.state.loading = false;
            return;
        }

        try {
            this.state.loading = true;

            const fromDate = this.state.attendanceFromDate || '';
            const toDate = this.state.attendanceToDate || '';

            const domain = [
                ["employee_id", "=", this.props.employeeId]
            ];

            if (fromDate) {
                domain.push(["check_in", ">=", fromDate + " 00:00:00"]);
            }
            if (toDate) {
                domain.push(["check_in", "<=", toDate + " 23:59:59"]);
            }

            console.log("Loading attendance with domain:", domain);

            const attendanceRecords = await this.orm.searchRead(
                "hr.attendance",
                domain,
                [
                    "check_in", 
                    "check_out", 
                    "worked_hours",
                    "checkin_latitude",
                    "checkin_longitude",
                    "checkin_accuracy",
                    "checkin_full_address",
                    "checkin_city",
                    "checkin_state",
                    "checkin_country",
                    "checkout_latitude",
                    "checkout_longitude",
                    "checkout_accuracy",
                    "checkout_full_address",
                    "checkout_city",
                    "checkout_state",
                    "checkout_country"
                ],
                { order: "check_in desc" }
            );

            console.log("Loaded attendance records:", attendanceRecords.length);

            this.state.attendanceRecords = attendanceRecords.map(record => {
                const checkInLocal = this.convertUTCToLocal(record.check_in);
                const checkOutLocal = record.check_out ? this.convertUTCToLocal(record.check_out) : null;

                console.log("Processing record:", {
                    id: record.id,
                    check_in: record.check_in,
                    check_out: record.check_out,
                    checkInLocal: checkInLocal,
                    checkOutLocal: checkOutLocal
                });

                let status = "Present";
                let startTime = "";
                let endTime = "";
                let totalWorkingHrs = "";
                let dateStr = "";

                if (checkInLocal) {
                    dateStr = this.formatLocalDate(checkInLocal);
                    startTime = this.formatLocalTime(checkInLocal);

                    const dayOfWeek = checkInLocal.getDay();
                    
                    const hasCheckedOut = record.check_out && record.check_out !== false;
                    
                    if (!hasCheckedOut) {
                        status = "In Progress";
                        endTime = "Not checked out yet";
                    } else {
                        
                        if (dayOfWeek === 0) {
                            status = "Holiday";
                        } else {
                            status = "Present";
                        }
                        endTime = this.formatLocalTime(checkOutLocal);
                    }

                    if (hasCheckedOut && record.worked_hours > 0) {
                        const hours = Math.floor(record.worked_hours);
                        const minutes = Math.round((record.worked_hours - hours) * 60);
                        totalWorkingHrs = `${hours} hrs ${minutes} min`;
                    } else if (!hasCheckedOut) {
                        const now = new Date();
                        const diffMs = now - checkInLocal;
                        const diffHours = diffMs / (1000 * 60 * 60);
                        const hours = Math.floor(diffHours);
                        const minutes = Math.round((diffHours - hours) * 60);
                        totalWorkingHrs = `${hours} hrs ${minutes} min (ongoing)`;
                    } else {
                        totalWorkingHrs = "0 hrs 0 min";
                    }

                    console.log("Processed status:", status, "endTime:", endTime);

                    return {
                        id: record.id,
                        date: dateStr,
                        status: status,
                        startTime: startTime,
                        endTime: endTime,
                        totalWorkingHrs: totalWorkingHrs,
                        
                        
                        checkinLatitude: record.checkin_latitude || null,
                        checkinLongitude: record.checkin_longitude || null,
                        checkinAccuracy: record.checkin_accuracy || null,
                        checkinAddress: record.checkin_full_address || null,
                        checkinCity: record.checkin_city || null,
                        checkinState: record.checkin_state || null,
                        checkinCountry: record.checkin_country || null,
                        
                        
                        checkoutLatitude: record.checkout_latitude || null,
                        checkoutLongitude: record.checkout_longitude || null,
                        checkoutAccuracy: record.checkout_accuracy || null,
                        checkoutAddress: record.checkout_full_address || null,
                        checkoutCity: record.checkout_city || null,
                        checkoutState: record.checkout_state || null,
                        checkoutCountry: record.checkout_country || null,
                    };
                }

                return null;
            }).filter(r => r !== null);

            console.log("Final attendance records:", this.state.attendanceRecords);

            this.state.loading = false;

        } catch (error) {
            console.error("Error loading attendance data:", error);
            this.state.attendanceRecords = [];
            this.state.loading = false;
            this.notification.add("Failed to load attendance records", { type: "danger" });
        }
    }

    async refresh() {
        console.log("🔄 External refresh triggered for attendance");
        await this.loadAttendanceData();
    }
}

AttendanceList.template = "employee_dashboard_v19.AttendanceList";
AttendanceList.props = {
    employeeId: { type: Number, optional: true },
    userId: { type: Number, optional: true },
};