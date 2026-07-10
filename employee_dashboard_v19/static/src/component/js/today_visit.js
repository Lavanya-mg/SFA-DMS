/** @odoo-module **/

import { Component, useState, onWillStart, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class TodayVisit extends Component {

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        
        this.startDayFileInputRef = useRef("startDayFileInput");

        this.state = useState({
            loading: true,
            beats: [],
            allBeatsToday: [],  
            selectedBeat: null,
            showStartDayModal: false,
            showStartBeatModal: false,
            showStartVisitModal: false,
            showEndVisitModal: false,
            showEndBeatModal: false,
            showEndDayModal: false,
            showSwitchBeatModal: false,
            showVisitCommentsModal: false,
            activeVisit: null,
            dayStarted: false,
            dayEnded: false,
            beatStarted: false,
            currentBeatLine: null,
            currentBeatLineIndex: 0,
            currentAttendanceId: null,
            isProcessing: false,
            isCapturingLocation: false,

            showVisitListModal: false,
            visitListData: [],

            showSalesOrderListModal: false,
            salesOrderListData: [],

            showQuickOrder: false,
            customerSummary: null,
            quickOrderTab: 'orders',
            allProducts: [],
            filteredProducts: [],
            mustSellProducts: [],
            focusSellProducts: [],
            topSellProducts: [],
            productSearchText: "",
            selectedCategoryId: "",
            productCategories: [],
            selectedProducts: {},
            productData: {},
            selectedUoms: {},
            allUoms: [],          // all active UOMs from master, loaded once
            customerOrders: [],
            customerVisits: [],
            mustSellList: [],
            focusSellList: [],
            topSellingList: [],
            lastOrderDetails: null,
            
            startDayForm: {
                todayWorkPlan: "Customer Visit",
                travelType: "",
                vehicleUsed: "",
                uploadedFiles: [],
                locationData: null,
            },
            
            startVisitForm: {
                storeImage: null,
                storeImageName: "",
            },
            
            endVisitForm: {
                comments: "",
            },
            
            endDayForm: {
                locationData: null,
            },

            // Day-End Summary
            dayEndSummary: null,
            
            switchBeatForm: {
                reason: "",
                newBeat: null,
            },
            allBeatsForSwap: [],       
            switchBeatLoading: false,  

            visitCommentsForm: {
                comments: "",
            },

            todayKpi: null,          
            kpiLoading: false,

          
            beatSwitchHistory: [],
            showSwitchHistoryModal: false,

            // ── NEW: enhanced UI state ────────────────────────
            checkinTime: null,
            checkinStartTime: null,
            todayStats: null,
            visitLocations: [],
            attendanceLocation: null,

            // ── NEW: panel system ──────────────────────────────
            activePanel: null,   // 'stock' | 'outstanding' | 'collect' | 'ticket' | 'competitor' | 'retailer'

            // Stock Update
            stockItems: [],

            // Outstanding data
            outstandingData: null,

            // Collection form
            collectForm: {
                amount: '', paymentMode: 'Cash', reference: '', remarks: '',
                // Invoice Allocation
                invoice_id: false, invoice_name: '', receipt_number: '',
                is_on_account: false, allocation_type: 'against_invoice',
                // Payment Details
                cheque_number: '', cheque_date: '', upi_reference: '',
                transaction_reference: '', bank_name: '',
                // Assignment
                salesperson_id: false, salesperson_name: '',
                collected_by_id: false, collected_by_name: '',
            },
            // Invoice search state
            invoiceSearchResults: [],
            invoiceSearchQuery: '',

            // Ticket form
            ticketForm: { subject: '', category: 'Product Quality', priority: 'Low', description: '' },

            // Competitor info
            competitors: [{ id: 1, brand: '', product: '', shelfPct: 0, price: 0, remarks: '' }],

            // Accordion state for visit detail
            accordionOpen: { lastVisit: false, assets: false, currentVisit: false, checklist: false, brochures: false },

            // Visit checklist
            visitChecklist: [
                { id: 1, question: "Is the store exterior clean and well-maintained?", done: false },
                { id: 2, question: "Are all products properly displayed on shelves?", done: false },
                { id: 3, question: "Is the planogram being followed correctly?", done: false },
                { id: 4, question: "Are price tags visible on all products?", done: false },
                { id: 5, question: "Is the stock freshness maintained (FIFO)?", done: false },
                { id: 6, question: "Are POSM/promotional materials in place?", done: false },
                { id: 7, question: "Is the visi-cooler clean and functioning?", done: false },
                { id: 8, question: "Are competitor products encroaching display space?", done: false },
                { id: 9, question: "Is the back stock area organized?", done: false },
                { id: 10, question: "Has the retailer been briefed on new schemes?", done: false },
            ],

            // Brochures
            brochures: [
                { id: 1, name: "Summer 2026 Product Catalog", type: "product", fileSize: "2.4 MB" },
                { id: 2, name: "Festive Schemes & Offers", type: "promo", fileSize: "1.1 MB" },
                { id: 3, name: "New Dealer Scheme", type: "scheme", fileSize: "0.8 MB" },
            ],

            // Retailer orders panel
            retailerOrders: [],
            retailerOrderStats: { retailers: 0, orders: 0, totalValue: 0 },
            retailerTab: 'retailers',

            // ── Asset Management ──────────────────────────────────
            customerAssets: [],
            assetMasters: [],
            assetsLoading: false,
            assetSubView: 'list',    // 'list' | 'register' | 'issue'
            selectedAssetForIssue: null,
            assetForm: {
                assetMasterId: null,
                assetMasterName: '',
                serialNumber: '',
                notes: '',
            },
            assetIssueForm: {
                subject: '',
                caseType: 'maintenance',
                priority: 'Medium',
                description: '',
            },
        });

        onWillStart(async () => {
            await Promise.all([
                this.loadTodayBeats(),
                this.checkDayStatus(),
                this.loadTodayKpi(),
                this.loadBeatSwitchHistory(),
                this.loadAllUoms(),   // load UOM master early so Quick Order dropdown is ready
            ]);
        });
    }

    formatDateTimeForOdoo(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');
        const seconds = String(date.getSeconds()).padStart(2, '0');
        return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
    }

    getEmployeeId() {
        const empId = this.props.employeeId || this.props.userId;
        if (!empId) {
            return null;
        }
        return typeof empId === 'number' ? empId : parseInt(empId, 10);
    }

    async loadTodayBeats() {
        const employeeId = this.getEmployeeId();

        if (!employeeId) {
            this.state.loading = false;
            return;
        }

        try {
            // Use local date (not UTC) to avoid timezone mismatch with Odoo server
            const now = new Date();
            const today = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;

            // --- Primary: look up beats via pjp.item (PJP-scheduled beats) ---
            const pjpItems = await this.orm.searchRead(
                "pjp.item",
                [
                    ["pjp_id.employee_id", "=", employeeId],
                    ["date", "=", today]
                ],
                ["id", "assigned_beat_id", "approved_beat_id", "date", "status"]
            );

            const pjpBeatIds = pjpItems
                .map(item => (item.approved_beat_id && item.approved_beat_id[0]) || (item.assigned_beat_id && item.assigned_beat_id[0]))
                .filter(Boolean);

            // --- Fallback: beats with beat_date set directly ---
            const directBeats = await this.orm.searchRead(
                "beat.module",
                [
                    ["employee_id", "=", employeeId],
                    ["beat_date", "=", today]
                ],
                ["id", "name", "beat_number", "beat_date", "status", "swapped_from_beat_id", "swapped_to_beat_id"]
            );
            const directBeatIds = directBeats.map(b => b.id);

            // Merge unique beat IDs from both sources
            const allBeatIds = [...new Set([...pjpBeatIds, ...directBeatIds])];

            let beats = [];
            if (allBeatIds.length > 0) {
                beats = await this.orm.searchRead(
                    "beat.module",
                    [["id", "in", allBeatIds]],
                    ["id", "name", "beat_number", "beat_date", "status", "swapped_from_beat_id", "swapped_to_beat_id"]
                );
            }

            for (const beat of beats) {
                const beatLines = await this.orm.searchRead(
                    "beat.line",
                    [["beat_id", "=", beat.id]],
                    ["id", "partner_id", "partner_phone", "partner_email", "partner_street", "sequence"],
                    { order: "sequence asc" }
                );
                beat.beatLines = beatLines;
                beat.customerCount = beatLines.length;

                for (const line of beatLines) {
                    const visits = await this.orm.searchRead(
                        "visit.model",
                        [
                            ["beat_line_id", "=", line.id],
                            ["actual_start_time", ">=", today],
                            ["actual_start_time", "<=", today + " 23:59:59"]
                        ],
                        ["id", "status", "actual_start_time", "actual_end_time", "visit_comments"]
                    );
                    line.visitStatus = visits.length > 0 ? visits[0] : null;
                }
            }

            this.state.allBeatsToday = beats;

            this.state.beats = beats.filter(beat => {
                if (!beat.beatLines || beat.beatLines.length === 0) {
                    return true;
                }

                const allVisited = beat.beatLines.every(line =>
                    line.visitStatus && line.visitStatus.status === 'completed'
                );

                return !allVisited;
            });
            
            this.state.loading = false;
            // Compute today stats for the new UI
            this._computeTodayStats();
        } catch (error) {
            console.error("Error loading today's beats:", error);
            this.notification.add("Failed to load today's beats", { type: "danger" });
            this.state.loading = false;
        }
    }

    async checkDayStatus() {
        const employeeId = this.getEmployeeId();
        
        if (!employeeId) return;

        try {
            console.log("🔍 Checking day status for employee:", employeeId);

            const activeVisits = await this.orm.searchRead(
                "visit.model",
                [
                    ["employee_id", "=", employeeId],
                    ["actual_start_time", "!=", false],
                    ["actual_end_time", "=", false]
                ],
                ["id", "beat_id", "beat_line_id", "actual_start_time", "partner_id", "visit_comments", "order_count", "total_order_amount"]
            );

            if (activeVisits.length > 0) {
                console.log("✅ Active visit found:", activeVisits[0]);
                this.state.activeVisit = activeVisits[0];
                this.state.dayStarted = true;
                this.state.beatStarted = true;
                this.state.selectedBeat = this.state.beats.find(
                    b => b.id === activeVisits[0].beat_id[0]
                );
                
                if (this.state.selectedBeat) {
                    const lineIndex = this.state.selectedBeat.beatLines.findIndex(
                        line => line.id === activeVisits[0].beat_line_id[0]
                    );
                    if (lineIndex !== -1) {
                        this.state.currentBeatLine = this.state.selectedBeat.beatLines[lineIndex];
                        this.state.currentBeatLineIndex = lineIndex;
                    }
                }
                
                await this.loadCustomerSummary(activeVisits[0].partner_id[0]);
            } else {
                console.log("ℹ️ No active visit found");
                
                const _now = new Date();
                const today = `${_now.getFullYear()}-${String(_now.getMonth()+1).padStart(2,'0')}-${String(_now.getDate()).padStart(2,'0')}`;
                const activeBeats = await this.orm.searchRead(
                    "beat.module",
                    [
                        ["employee_id", "=", employeeId],
                        ["status", "=", "in_progress"]
                    ],
                    ["id", "name", "beat_number", "beat_date", "status"]
                );

                if (activeBeats.length > 0) {
                    console.log("✅ Active beat found (in_progress):", activeBeats[0]);
                    const activeBeat = this.state.beats.find(b => b.id === activeBeats[0].id);
                    if (activeBeat) {
                        this.state.selectedBeat = activeBeat;
                        this.state.beatStarted = true;
                        this.state.dayStarted = true;
                        console.log("✅ Beat state restored:", activeBeat.beat_number);
                    }
                }
            }
            const today = new Date().toISOString().slice(0, 10);
            
            const todayAttendance = await this.orm.searchRead(
                "hr.attendance",
                [
                    ["employee_id", "=", employeeId],
                    ["check_in", ">=", today + " 00:00:00"],
                    ["check_in", "<=", today + " 23:59:59"]
                ],
                ["id", "check_in", "check_out"],
                { order: "check_in desc", limit: 1 }
            );

            console.log("📋 Today's attendance records:", todayAttendance);

            if (todayAttendance.length > 0) {
                const attendance = todayAttendance[0];
                this.state.currentAttendanceId = attendance.id;
                
                console.log("📝 Attendance record:", {
                    id: attendance.id,
                    check_in: attendance.check_in,
                    check_out: attendance.check_out
                });

                const hasCheckedOut = attendance.check_out && attendance.check_out !== false;
                
                if (!hasCheckedOut) {
                    console.log("✅ Day is ACTIVE (no check-out)");
                    this.state.dayStarted = true;
                    this.state.dayEnded = false;
                } else {
                    console.log("❌ Day has ENDED (check-out exists)");
                    this.state.dayStarted = false;
                    this.state.dayEnded = true;
                    this.state.beatStarted = false;
                    this.state.currentAttendanceId = null;
                    this.state.activeVisit = null;
                    this.state.selectedBeat = null;
                    this.state.currentBeatLine = null;
                    this.state.customerSummary = null;
                }
            } else {
                console.log("ℹ️ No attendance record for today");
                this.state.dayStarted = false;
                this.state.dayEnded = false;
                this.state.beatStarted = false;
                this.state.currentAttendanceId = null;
                this.state.activeVisit = null;
                this.state.selectedBeat = null;
                this.state.currentBeatLine = null;
                this.state.customerSummary = null;
            }

            console.log("📊 Final day status:", {
                dayStarted: this.state.dayStarted,
                beatStarted: this.state.beatStarted,
                hasActiveVisit: !!this.state.activeVisit,
                hasActiveBeat: !!this.state.selectedBeat,
                attendanceId: this.state.currentAttendanceId
            });

        } catch (error) {
            console.error("❌ Error checking day status:", error);
        }
    }

    async refresh() {
        console.log("🔄 External refresh triggered for TodayVisit");
        await this.loadTodayBeats();
        await this.checkDayStatus();
    }

    openStartDayModal() {
        const employeeId = this.getEmployeeId();
        
        if (!employeeId) {
            this.notification.add("Please select an employee first", { type: "warning" });
            return;
        }

        if (this.state.beats.length === 0) {
            this.notification.add("No beats scheduled for today", { type: "warning" });
            return;
        }

        if (this.state.dayStarted) {
            this.notification.add("Day has already been started", { type: "warning" });
            return;
        }

        this.state.startDayForm = {
            todayWorkPlan: "Customer Visit",
            travelType: "",
            vehicleUsed: "",
            uploadedFiles: [],
            locationData: null,
        };

        this.state.showStartDayModal = true;
        
        this.captureStartDayLocation();
    }

    async captureStartDayLocation() {
        if (this.state.isCapturingLocation) return;
        
        this.state.isCapturingLocation = true;
        this.notification.add("📍 Capturing your location automatically...", { type: "info" });
        
        try {
            const locationData = await this.captureLocationWithAddress();
            
            if (locationData) {
                this.state.startDayForm.locationData = locationData;
                
                let message = `✅ Location captured successfully!\n\nAccuracy: ±${Math.round(locationData.accuracy)}m`;
                if (locationData.full_address) {
                    message += `\n\n📮 ${locationData.full_address}`;
                }
                
                this.notification.add(message, { 
                    type: "success",
                    sticky: false 
                });
            }
        } catch (error) {
            console.error("Location capture error:", error);
            this.notification.add("Failed to capture location: " + error.message, { 
                type: "danger",
                sticky: true 
            });
        } finally {
            this.state.isCapturingLocation = false;
        }
    }

    async captureLocationWithAddress() {
        return new Promise((resolve, reject) => {
            if (!navigator.geolocation) {
                reject(new Error("Geolocation is not supported by your browser"));
                return;
            }

            const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);

            console.log("🌍 Geolocation capture started");
            console.log(`📡 Device: ${isMobile ? "Mobile (GPS)" : "Desktop (WiFi/IP)"}`);

            const options = {
                enableHighAccuracy: true,
                timeout: isMobile ? 45000 : 30000,
                maximumAge: 0
            };

            let attempts = 0;
            const maxAttempts = isMobile ? 4 : 2;
            let bestPosition = null;
            let bestAccuracy = Infinity;
            let watchId = null;

            watchId = navigator.geolocation.watchPosition(
                async (position) => {
                    attempts++;
                    const coords = position.coords;
                    const accuracy = coords.accuracy;

                    console.log(`📍 Reading #${attempts}:`, {
                        lat: coords.latitude.toFixed(6),
                        lon: coords.longitude.toFixed(6),
                        accuracy: accuracy.toFixed(2) + "m"
                    });

                    if (coords.latitude < -90 || coords.latitude > 90 ||
                        coords.longitude < -180 || coords.longitude > 180) {
                        console.error("❌ Invalid coordinates!");
                        return;
                    }

                    if (accuracy < bestAccuracy) {
                        bestAccuracy = accuracy;
                        bestPosition = position;
                        console.log(`✅ New best accuracy: ${accuracy.toFixed(2)}m`);
                    }

                    const targetAccuracy = isMobile ? 50 : 200;
                    const hasGoodAccuracy = accuracy < targetAccuracy;
                    const reachedMaxAttempts = attempts >= maxAttempts;
                    const hasMinimumData = attempts >= 1 && bestPosition !== null;

                    if (hasGoodAccuracy || reachedMaxAttempts || (hasMinimumData && !isMobile)) {
                        if (watchId) {
                            navigator.geolocation.clearWatch(watchId);
                        }
                        
                        console.log(`\n🎯 Acquisition complete after ${attempts} reading(s)`);
                        console.log(`   Best accuracy: ${bestAccuracy.toFixed(2)}m`);

                        try {
                            const addressData = await this.reverseGeocode(
                                bestPosition.coords.latitude,
                                bestPosition.coords.longitude
                            );

                            const locationData = {
                                latitude: bestPosition.coords.latitude,
                                longitude: bestPosition.coords.longitude,
                                accuracy: bestPosition.coords.accuracy,
                                ...addressData
                            };

                            resolve(locationData);
                        } catch (error) {
                            console.error("Reverse geocoding failed:", error);
                            resolve({
                                latitude: bestPosition.coords.latitude,
                                longitude: bestPosition.coords.longitude,
                                accuracy: bestPosition.coords.accuracy,
                                full_address: "Address lookup failed"
                            });
                        }
                    }
                },
                (error) => {
                    if (watchId) {
                        navigator.geolocation.clearWatch(watchId);
                    }
                    
                    console.error("❌ Geolocation error:", error);
                    
                    let errorMessage = "";
                    switch(error.code) {
                        case error.PERMISSION_DENIED:
                            errorMessage = "Location permission denied. Please allow location access.";
                            break;
                        case error.POSITION_UNAVAILABLE:
                            errorMessage = "Location unavailable. Please enable GPS and try again.";
                            break;
                        case error.TIMEOUT:
                            errorMessage = "Location request timed out. Please try again.";
                            break;
                        default:
                            errorMessage = "Unknown location error";
                    }
                    
                    reject(new Error(errorMessage));
                },
                options
            );
        });
    }

    async reverseGeocode(latitude, longitude) {
        try {
            console.log("🔍 Reverse geocoding coordinates...");
            
            const url = `https://nominatim.openstreetmap.org/reverse?format=json&lat=${latitude}&lon=${longitude}&zoom=18&addressdetails=1`;
            
            const response = await fetch(url, {
                headers: {
                    'User-Agent': 'OdooAttendanceApp/1.0'
                }
            });

            if (!response.ok) {
                throw new Error("Geocoding service error");
            }

            const data = await response.json();
            
            if (!data || !data.address) {
                throw new Error("No address data returned");
            }

            const address = data.address;
            
            const house_number = address.house_number || '';
            const road = address.road || '';
            const suburb = address.suburb || address.neighbourhood || address.quarter || '';
            const city = address.city || address.town || address.village || address.municipality || '';
            const district = address.county || address.state_district || '';
            const state = address.state || '';
            const country = address.country || '';
            const postcode = address.postcode || '';

            const address_parts = [];
            if (house_number) address_parts.push(house_number);
            if (road) address_parts.push(road);
            if (suburb) address_parts.push(suburb);
            if (city) address_parts.push(city);
            if (district && district !== city) address_parts.push(district);
            if (state) address_parts.push(state);
            if (postcode) address_parts.push(postcode);
            if (country) address_parts.push(country);

            const full_address = address_parts.join(', ') || data.display_name;

            console.log("✅ Geocoded successfully:", full_address);

            return {
                full_address: full_address,
                house_number: house_number,
                road: road,
                suburb: suburb,
                city: city,
                district: district,
                state: state,
                country: country,
                postcode: postcode
            };

        } catch (error) {
            console.error("Reverse geocoding error:", error);
            throw error;
        }
    }

    
    async loadCustomerSummary(partnerId) {
        if (!partnerId) return;
        
        try {
            const [partner] = await this.orm.searchRead(
                "res.partner",
                [["id", "=", partnerId]],
                ["name", "phone", "email", "credit", "debit",
                 "category_id", "company_type", "street", "street2", "city",
                 "state_id", "zip", "country_id", "industry_id", "function"]
            );

            const allOrders = await this.orm.searchRead(
                "sale.order",
                [["partner_id", "=", partnerId]],
                ["id", "amount_total", "date_order", "state"],
                { order: "date_order desc" }
            );

           
            const confirmedOrders = allOrders.filter(o => 
                o.state === 'sale' || o.state === 'done'
            );

            const visits = await this.orm.searchRead(
                "visit.model",
                [["partner_id", "=", partnerId]],
                ["id", "actual_start_time"]
            );

            const outstanding = (partner.debit || 0) - (partner.credit || 0);
            
            const lastOrderDate = allOrders.length > 0 
                ? allOrders[0].date_order
                : null;

            const totalSales = confirmedOrders.reduce((sum, order) => sum + (order.amount_total || 0), 0);

            const addressParts = [];
            if (partner.street) addressParts.push(partner.street);
            if (partner.street2) addressParts.push(partner.street2);
            if (partner.city) addressParts.push(partner.city);
            if (partner.state_id) addressParts.push(partner.state_id[1]);
            if (partner.zip) addressParts.push(partner.zip);
            if (partner.country_id) addressParts.push(partner.country_id[1]);
            const fullAddress = addressParts.join(', ');

            const avgSales = confirmedOrders.length > 0 ? totalSales / confirmedOrders.length : 0;

            // Last visit info
            const lastVisitDate = visits.length > 0 ? visits[0].actual_start_time : null;
            const lastVisitOrders = lastVisitDate ? confirmedOrders.filter(o =>
                o.date_order && o.date_order.slice(0, 10) === (lastVisitDate || '').slice(0, 10)
            ).length : 0;
            const lastVisitAmount = lastVisitDate ? confirmedOrders
                .filter(o => o.date_order && o.date_order.slice(0, 10) === (lastVisitDate || '').slice(0, 10))
                .reduce((s, o) => s + (o.amount_total || 0), 0) : 0;

            this.state.customerSummary = {
                name: partner.name,
                phone: partner.phone || '',
                outstanding: outstanding,
                totalSales: totalSales,
                avgSales: avgSales,
                orderCount: confirmedOrders.length,
                visitCount: visits.length,
                lastOrderDate: lastOrderDate,
                lastVisitDate: lastVisitDate,
                lastVisitOrders: lastVisitOrders,
                lastVisitAmount: lastVisitAmount,
                category: partner.category_id && partner.category_id.length > 0
                    ? partner.category_id.map(c => c[1] || c).join(', ')
                    : '',
                companyType: partner.company_type === 'company' ? 'Company' : 'Individual',
                address: fullAddress,
                mobile: '',
                email: partner.email || '',
                businessType: partner.industry_id ? partner.industry_id[1] : '',
            };

        } catch (error) {
            console.error("Error loading customer summary:", error);
        }
    }

    async openVisitListView() {
        if (!this.state.activeVisit) {
            this.notification.add("Please start a visit first", { type: "warning" });
            return;
        }

        try {
            const visits = await this.orm.searchRead(
                "visit.model",
                [["partner_id", "=", this.state.activeVisit.partner_id[0]]],
                ["id", "name", "actual_start_time", "actual_end_time", "status", "visit_comments", "is_productive", "beat_id"],
                { order: "actual_start_time desc" }
            );

            for (const visit of visits) {
                try {
                    const orders = await this.orm.searchRead(
                        "sale.order",
                        [["visit_id", "=", visit.id]],
                        ["id"]
                    );
                    visit.order_count = orders.length;
                } catch (e) {
                    visit.order_count = 0;
                }
            }

            this.state.visitListData = visits;
            this.state.showVisitListModal = true;
        } catch (error) {
            console.error("Error loading visit list:", error);
            this.notification.add("Failed to load visit list", { type: "danger" });
        }
    }

    closeVisitListModal() {
        this.state.showVisitListModal = false;
        this.state.visitListData = [];
    }

    formatDateTime(datetime) {
        if (!datetime) return "-";
        let date;
        if (datetime.includes('T')) {
            date = new Date(datetime);
        } else {
            date = new Date(datetime.replace(' ', 'T') + 'Z');
        }
        
        return date.toLocaleString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hour12: true
        });
    }

    formatTime(datetime) {
        if (!datetime) return "-";
        let date;
        if (typeof datetime === 'string') {
            date = new Date(datetime.includes('T') ? datetime : datetime.replace(' ', 'T') + 'Z');
        } else { date = datetime; }
        return date.toLocaleTimeString("en-US", { hour: "2-digit", minute: "2-digit" });
    }

    formatDateOnly(datetime) {
        if (!datetime) return "-";
        
        let date;
        if (datetime.includes('T')) {
            date = new Date(datetime);
        } else {
            date = new Date(datetime.replace(' ', 'T') + 'Z');
        }
        
        return date.toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric"
        });
    }

    calculateDuration(startTime, endTime) {
        if (!startTime || !endTime) return "-";
        const start = new Date(startTime.replace(' ', 'T'));
        const end = new Date(endTime.replace(' ', 'T'));
        const diff = Math.floor((end - start) / 1000 / 60);
        const hours = Math.floor(diff / 60);
        const minutes = diff % 60;
        return `${hours}h ${minutes}m`;
    }

    async viewVisitDetails(visitId) {
        try {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "visit.model",
                res_id: visitId,
                name: "Visit Details",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
            });
        } catch (error) {
            console.error("Error opening visit details:", error);
            this.notification.add("Failed to open visit details", { type: "danger" });
        }
    }

    async loadMustSellProducts() {
        try {
            if (!this.state.allProducts || this.state.allProducts.length === 0) {
                await this.loadProducts(); 
            }
            const mustSell = await this.orm.searchRead(
                "must.sell.product",
                [["active", "=", true]],
                ["id", "product_id", "min_qty", "notes"],
                { limit: 50 }
            );
            

            // Auto-add Must Sell products to cart
            for (const ms of mustSell) {
                if (!this.state.selectedProducts[ms.product_id[0]]) {
                    this.onQuantityChange(ms.product_id[0], ms.min_qty);
                }
            }
        } catch (e) {
            console.error("Error loading Must Sell:", e);
        }
    }

    async openSalesOrderList() {
        if (!this.state.activeVisit) {
            this.notification.add("Please start a visit first", { type: "warning" });
            return;
        }

        try {
            const orders = await this.orm.searchRead(
                "sale.order",
                [["partner_id", "=", this.state.activeVisit.partner_id[0]]],
                ["id", "name", "date_order", "amount_total", "state", "order_line"],
                { order: "date_order desc" }
            );

            for (const order of orders) {
                if (order.order_line && order.order_line.length > 0) {
                    const orderLines = await this.orm.searchRead(
                        "sale.order.line",
                        [["id", "in", order.order_line]],
                        ["product_id", "product_uom_qty", "price_unit", "price_subtotal", "name"]
                    );
                    order.lines = orderLines;
                } else {
                    order.lines = [];
                }
            }

            this.state.salesOrderListData = orders;
            this.state.showSalesOrderListModal = true;
        } catch (error) {
            console.error("Error loading sales order list:", error);
            this.notification.add("Failed to load sales orders", { type: "danger" });
        }
    }

    closeSalesOrderListModal() {
        this.state.showSalesOrderListModal = false;
        this.state.salesOrderListData = [];
    }

    async viewSalesOrderDetails(orderId) {
        try {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "sale.order",
                res_id: orderId,
                name: "Sales Order Details",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
            });
        } catch (error) {
            console.error("Error opening sales order:", error);
            this.notification.add("Failed to open sales order", { type: "danger" });
        }
    }

    getOrderStateBadge(state) {
        const badgeMap = {
            draft: "bg-secondary",
            sent: "bg-info",
            sale: "bg-success",
            done: "bg-success",
            cancel: "bg-danger",
        };
        return badgeMap[state] || "bg-secondary";
    }

    getOrderStateText(state) {
        const stateMap = {
            draft: "Quotation",
            sent: "Quotation Sent",
            sale: "Sales Order",
            done: "Locked",
            cancel: "Cancelled",
        };
        return stateMap[state] || state;
    }

    async openQuickOrder() {
        if (!this.state.activeVisit) {
            this.notification.add("Please start a visit first", { type: "warning" });
            return;
        }

        this.state.showQuickOrder = true;
        this.state.quickOrderTab = 'orders';
        this.state.selectedCategoryId = "";
        this.state.mustSellList = [];
        this.state.focusSellList = [];

        await Promise.all([
            this.loadProducts(),
            this.loadAllUoms(),
            this.loadProductCategories(),
            this.loadCustomerOrders(),
            this.loadCustomerVisits(),
            this.loadLastOrderDetails(),
        ]);

        // Load must sell list, auto-add to cart, and populate product objects for rich UI
        try {
            const mustSellData = await this.orm.call("priority.sell.config", "get_must_sell_products", []);
            this.state.mustSellList = mustSellData;
            this.state.mustSellProducts = mustSellData
                .map(ms => this.state.allProducts.find(p => p.id === ms.product_id))
                .filter(Boolean);
            for (const ms of mustSellData) {
                if (ms.product_id) {
                    this.onQuantityChange(ms.product_id, ms.min_qty || 1);
                }
            }
        } catch (e) {
            console.error("Failed to load Must Sell data", e);
        }

        // Load focus sell list and populate product objects for rich UI
        try {
            const focusSellData = await this.orm.call("priority.sell.config", "get_priority_sell_products", ["focused_sell"]);
            this.state.focusSellList = focusSellData;
            this.state.focusSellProducts = focusSellData
                .map(fs => this.state.allProducts.find(p => p.id === fs.product_id))
                .filter(Boolean);
        } catch (e) {
            console.error("Failed to load Focus Sell data", e);
        }
    }

    closeQuickOrder() {
        this.state.showQuickOrder = false;
        this.state.selectedProducts = {};
        this.state.selectedUoms = {};
        this.state.productSearchText = "";
        this.state.selectedCategoryId = "";
    }

    async loadAllUoms() {
        if (this.state.allUoms && this.state.allUoms.length > 0) return;
        try {
            // Odoo 19's uom.uom dropped the old factor/category_id fields — request only
            // id/name so this doesn't 500. The per-product pData.uoms (built from conversion
            // rules) is the real source for conversions; allUoms is just a name fallback.
            const uoms = await this.orm.searchRead(
                "uom.uom",
                [["active", "=", true]],
                ["id", "name"],
                { order: "name asc" }
            );
            console.log("UOMs loaded:", uoms.length, uoms);
            if (uoms && uoms.length > 0) {
                this.state.allUoms = uoms.map(u => ({
                    id: u.id,
                    name: u.name,
                    factor: 1,
                    category_id: false,
                    category_name: '',
                }));
            }
        } catch (e) {
            console.error("loadAllUoms failed:", e);
            // Fallback: build UOM list from product data already loaded
            this._buildUomsFromProductData();
        }
    }

    _buildUomsFromProductData() {
        const seen = {};
        const list = [];
        // Collect UOMs from pData (per-product backend data)
        for (const pData of Object.values(this.state.productData || {})) {
            for (const u of (pData.uoms || [])) {
                if (!seen[u.id]) {
                    seen[u.id] = true;
                    list.push(u);
                }
            }
        }
        // Also collect from allProducts uom_id
        for (const p of (this.state.allProducts || [])) {
            if (p.uom_id && !seen[p.uom_id[0]]) {
                seen[p.uom_id[0]] = true;
                list.push({ id: p.uom_id[0], name: p.uom_id[1], factor: 1, category_id: false, category_name: '' });
            }
        }
        list.sort((a, b) => a.name.localeCompare(b.name));
        if (list.length > 0) {
            this.state.allUoms = list;
        }
    }

    // Returns the UOM list for Quick Order dropdowns.
    getUomList(productId) {
        // Prefer the per-product list: it carries conversion data (price_multiplier /
        // has_rule / compatible) so each option can show the UOM and its conversion.
        const pData = this.state.productData[productId] || {};
        if (pData.uoms && pData.uoms.length > 0) return pData.uoms;
        if (this.state.allUoms && this.state.allUoms.length > 0) {
            return this.state.allUoms;
        }
        // Last resort: just the product's own UOM
        const product = this.state.allProducts.find(p => p.id === productId);
        if (product && product.uom_id) {
            return [{ id: product.uom_id[0], name: product.uom_id[1], factor: 1, category_id: false }];
        }
        return [];
    }

    // Dropdown label combining the UOM name with its conversion to the product's base UOM.
    // Base UOM shows plainly (e.g. "Units"); a converted UOM shows e.g. "box (= 12 Units)".
    getUomLabel(productId, uom) {
        if (!uom) return "";
        const pData = this.state.productData[productId] || {};
        const product = this.state.allProducts.find(p => p.id === productId);
        const defaultUomId = pData.default_uom_id ||
                             (product && product.uom_id ? product.uom_id[0] : false);
        const defaultUomName = pData.default_uom_name ||
                               (product && product.uom_id ? product.uom_id[1] : "Unit");

        // Base UOM: nothing to convert.
        if (uom.id === defaultUomId) return uom.name;

        // Annotate only when a real conversion exists (custom rule or same-category compatibility).
        const mult = uom.price_multiplier;
        if ((uom.has_rule || uom.compatible) && mult && mult > 0) {
            return `${uom.name} (= ${this._fmtFactor(mult)} ${defaultUomName})`;
        }
        return uom.name;
    }

    _fmtFactor(n) {
        // Trim trailing zeros: 12.0000 → "12", 0.0833 → "0.0833".
        return String(parseFloat(Number(n).toFixed(4)));
    }

    // Configured conversions for a product (from uom.conversion.rule), for on-card display.
    // Returns [{name, factor}] e.g. [{name:'box', factor:'12'}, {name:'g', factor:'10'}].
    getUomConversions(productId) {
        const pData = this.state.productData[productId] || {};
        const product = this.state.allProducts.find(p => p.id === productId);
        const defaultUomId = pData.default_uom_id ||
                             (product && product.uom_id ? product.uom_id[0] : false);
        const list = (pData.uoms && pData.uoms.length > 0) ? pData.uoms : [];
        return list
            .filter(u => u.has_rule && u.id !== defaultUomId && u.price_multiplier > 0)
            .map(u => ({ name: u.name, factor: this._fmtFactor(u.price_multiplier) }));
    }

    getSelectedUomId(product) {
        return this.state.selectedUoms[product.id] ||
               (product.uom_id ? product.uom_id[0] : false);
    }

    async loadProducts() {
        try {
            const products = await this.orm.searchRead(
                "product.product",
                [["sale_ok", "=", true]],
                ["id", "name", "list_price", "default_code", "categ_id", "taxes_id", "uom_id"]
            );

            this.state.allProducts = products;
            this.state.filteredProducts = products;

            // Load price book prices, schemes and UOMs for each product
            const partnerId = this.state.activeVisit?.partner_id?.[0] || false;
            if (products.length > 0) {
                try {
                    const productIds = products.map(p => p.id);
                    const productData = await this.orm.call(
                        "sale.order",
                        "get_quick_order_product_data",
                        [partnerId, productIds]
                    );
                    this.state.productData = productData;
                } catch (e) {
                    console.warn("Could not load product data:", e);
                    this.state.productData = {};
                }
            }
            // If UOM master fetch failed earlier, try building from product data now
            if (!this.state.allUoms || this.state.allUoms.length === 0) {
                await this.loadAllUoms();
                if (!this.state.allUoms || this.state.allUoms.length === 0) {
                    this._buildUomsFromProductData();
                }
            }
        } catch (error) {
            console.error("Error loading products:", error);
            this.notification.add("Failed to load products", { type: "danger" });
        }
    }

    async loadProductCategories() {
        try {
            const categories = await this.orm.searchRead(
                "product.category",
                [],
                ["id", "name", "complete_name"],
                { order: "complete_name asc" }
            );
            this.state.productCategories = categories;
        } catch (error) {
            console.error("Error loading product categories:", error);
            this.state.productCategories = [];
        }
    }

    onProductSearchChange(ev) {
        this.state.productSearchText = ev.target.value.toLowerCase();
        this.filterProducts();
    }

    onCategoryChange(ev) {
        this.state.selectedCategoryId = ev.target.value;
        this.filterProducts();
    }

    filterProducts() {
        let filtered = [...this.state.allProducts]; 
        if (this.state.selectedCategoryId) {
            const categId = parseInt(this.state.selectedCategoryId);
            filtered = filtered.filter(product =>
                product.categ_id && product.categ_id[0] === categId
            );
        }

        if (this.state.productSearchText) {
            filtered = filtered.filter(product =>
                product.name.toLowerCase().includes(this.state.productSearchText) ||
                (product.default_code && product.default_code.toLowerCase().includes(this.state.productSearchText))
            );
        }

        this.state.filteredProducts = filtered;
    }

    onQuantityChange(productId, quantity) {
        const product = this.state.allProducts.find(p => p.id === productId);
        if (!product) return;

        const qty = parseInt(quantity) || 0;
        const pData = this.state.productData[productId] || {};
        const basePrice = pData.price !== undefined ? pData.price : product.list_price;

        // Resolve selected UOM
        const defaultUomId = product.uom_id ? product.uom_id[0] : false;
        const selectedUomId = this.state.selectedUoms[productId] || defaultUomId;

        // Use per-product UOM list from backend (has price_multiplier), fallback to global allUoms
        const pUomList = (pData.uoms && pData.uoms.length > 0) ? pData.uoms : null;
        const selectedUom = pUomList ? pUomList.find(u => u.id === selectedUomId) : null;
        const isCompatible = selectedUom ? selectedUom.compatible : true;

        // price_multiplier is pre-computed per product: accounts for custom conversion rules
        // (e.g. Units→box factor=12 means 1 box costs 12× unit price)
        let priceMultiplier = 1.0;
        if (selectedUom && selectedUom.price_multiplier !== undefined) {
            priceMultiplier = selectedUom.price_multiplier;
        } else if (!pUomList) {
            // Fallback: use global allUoms standard Odoo factor ratio
            const globalUomList = this.state.allUoms;
            const selU = globalUomList.find(u => u.id === selectedUomId);
            const defU = globalUomList.find(u => u.id === defaultUomId);
            if (selU && defU && selU.factor && defU.factor) {
                priceMultiplier = defU.factor / selU.factor;
            }
        }
        const unitPrice = basePrice * priceMultiplier;

        if (qty > 0) {
            const grossSubtotal = unitPrice * qty;

            // Auto-calculate scheme benefit based on qty
            let discountPct = 0;
            let discountAmount = 0;
            let freeQty = 0;
            let freeProductName = '';
            let schemeBadge = '';
            let schemeId = false;

            if (pData.schemes && pData.schemes.length > 0) {
                for (const scheme of pData.schemes) {
                    if (!scheme.min_qty || qty >= scheme.min_qty) {
                        schemeId = scheme.scheme_id;
                        schemeBadge = scheme.badge;
                        if (scheme.benefit_type === 'percent_discount') {
                            discountPct = scheme.discount_pct;
                            discountAmount = grossSubtotal * (discountPct / 100);
                        } else if (scheme.benefit_type === 'free_product') {
                            // Scale free qty: every multiple of min_qty earns free_qty
                            const multiples = scheme.min_qty ? Math.floor(qty / scheme.min_qty) : 1;
                            freeQty = (scheme.free_qty || 1) * multiples;
                            freeProductName = scheme.free_product_name;
                        }
                        break;
                    }
                }
            }

            const netSubtotal = grossSubtotal - discountAmount;
            const taxRate = 0.18;
            const taxAmount = netSubtotal * taxRate;
            const uomName = selectedUom ? selectedUom.name : (product.uom_id ? product.uom_id[1] : 'Unit');

            const defaultUomName = pData.default_uom_name || (product.uom_id ? product.uom_id[1] : 'Unit');
            const baseQty = (selectedUomId !== defaultUomId && priceMultiplier > 1)
                ? qty * priceMultiplier
                : null;
            const baseQtyDisplay = baseQty ? `= ${Math.round(baseQty)} ${defaultUomName}` : null;
            const stockQty = pData.stock !== undefined ? pData.stock : null;

            this.state.selectedProducts[productId] = {
                id: productId,
                name: product.name,
                quantity: qty,
                price: unitPrice,
                price_source: pData.price_source || 'list',
                uom_id: selectedUomId,
                uom_name: uomName,
                uom_compatible: isCompatible !== false,
                subtotal: grossSubtotal,
                discount_pct: discountPct,
                discount_amount: discountAmount,
                free_qty: freeQty,
                free_product_name: freeProductName,
                scheme_badge: schemeBadge,
                scheme_id: schemeId,
                net_subtotal: netSubtotal,
                tax: taxAmount,
                total: netSubtotal + taxAmount,
                base_qty_display: baseQtyDisplay,
                stock: stockQty,
                default_code: product.default_code || '',
            };
        } else {
            delete this.state.selectedProducts[productId];
        }
    }

    isProductAdded(productId) {
        return !!this.state.selectedProducts[productId];
    }

    onUomChange(productId, uomId) {
        const parsedId = parseInt(uomId) || false;
        this.state.selectedUoms[productId] = parsedId;

        // Warn if selected UOM is from a different category (no conversion rule)
        const pData = this.state.productData[productId] || {};
        const product = this.state.allProducts.find(p => p.id === productId);
        if (parsedId && product) {
            const uomList = (pData.uoms && pData.uoms.length > 0) ? pData.uoms : this.state.allUoms;
            const selectedUom = uomList.find(u => u.id === parsedId);
            const defaultUomId = product.uom_id ? product.uom_id[0] : false;
            // compatible = same Odoo category OR has a custom conversion rule
            const hasConversion = selectedUom && (selectedUom.compatible || selectedUom.has_rule);
            if (selectedUom && parsedId !== defaultUomId && !hasConversion) {
                const defaultName = pData.default_uom_name || (product.uom_id ? product.uom_id[1] : 'default UOM');
                this.notification.add(
                    `No conversion rule from ${selectedUom.name} to ${defaultName} for ${product.name}. Price may be inaccurate.`,
                    { type: "warning", sticky: false }
                );
            }
        }

        const sel = this.state.selectedProducts[productId];
        if (sel) {
            this.onQuantityChange(productId, sel.quantity);
        }
    }

    getCartItems() {
        return Object.values(this.state.selectedProducts).map((p, idx) => ({
            ...p,
            index: idx + 1,
        }));
    }

    getProductUomList(productId) {
        return this.getUomList(productId);
    }

    getOrderSummary() {
        const products = Object.values(this.state.selectedProducts);
        const subtotal = products.reduce((sum, p) => sum + p.subtotal, 0);
        const totalDiscount = products.reduce((sum, p) => sum + (p.discount_amount || 0), 0);
        const netSubtotal = subtotal - totalDiscount;
        const tax = products.reduce((sum, p) => sum + p.tax, 0);
        const total = netSubtotal + tax;
        const freeItems = products.filter(p => p.free_qty > 0).map(p => ({
            name: p.name,
            free_product_name: p.free_product_name,
            free_qty: p.free_qty,
        }));
        return { subtotal, totalDiscount, netSubtotal, tax, total, itemCount: products.length, freeItems };
    }

    async saveQuickOrder() {
        const summary = this.getOrderSummary();
        
        if (summary.itemCount === 0) {
            this.notification.add("Please select at least one product", { type: "warning" });
            return;
        }
        
        // Safety check: use raw mustSellList which has product_id, min_qty, product_name
        const mustSell = Array.isArray(this.state.mustSellList) ? this.state.mustSellList : [];

        // 1. Check all Must Sell configs
        for (const ms of mustSell) {
            const pid = ms.product_id;
            if (!pid) continue;
            const item = this.state.selectedProducts[pid];
            const minQty = ms.min_qty || 1;
            const productName = ms.product_name || ms.name || `Product ${pid}`;
            if (!item || item.quantity < minQty) {
                this.notification.add(
                    `Missing Must Sell: ${productName}. Min Qty: ${minQty}`,
                    { type: "danger" }
                );
                return;
            }
        }

        try {
            const employeeId = this.getEmployeeId();

            let userId = false;
            try {
                const [emp] = await this.orm.searchRead(
                    "hr.employee",
                    [["id", "=", employeeId]],
                    ["user_id"]
                );
                if (emp && emp.user_id) {
                    userId = emp.user_id[0];
                }
            } catch (e) {
                console.warn("Could not fetch employee user_id:", e);
            }

            const orderData = {
                partner_id: this.state.activeVisit.partner_id[0],
                visit_id: this.state.activeVisit.id,
            };
            if (userId) {
                orderData.user_id = userId;
            }

            const orderIds = await this.orm.create("sale.order", [orderData]);
            const orderId = orderIds[0];

            for (const product of Object.values(this.state.selectedProducts)) {
                const lineVals = {
                    order_id: orderId,
                    product_id: product.id,
                    product_uom_qty: product.quantity,
                    price_unit: product.price,
                };
                if (product.uom_id) {
                    lineVals.product_uom_id = product.uom_id;
                }
                await this.orm.create("sale.order.line", [lineVals]);
            }
            // Task 8: Apply schemes after all lines are created (stores scheme usage)
            try {
                await this.orm.call("sale.order", "action_apply_schemes", [[orderId]]);
            } catch (e) {
                console.warn("Scheme application skipped:", e);
            }

            // Confirm the order so it counts toward KPI actuals (state → 'sale').
            // Draft orders are excluded from all KPI computations.
            try {
                await this.orm.call("sale.order", "action_confirm", [[orderId]]);
            } catch (e) {
                console.warn("Could not auto-confirm sale order:", e);
            }

            if (this.state.activeVisit && this.state.activeVisit.id) {
                await this.orm.write("visit.model", [this.state.activeVisit.id], {
                    is_productive: true,
                });

                // Re-read the visit from DB to get the updated order_count and
                // total_order_amount (the stored computed field is refreshed by
                // the sale.order write/confirm trigger on the backend).
                try {
                    const [updatedVisit] = await this.orm.searchRead(
                        "visit.model",
                        [["id", "=", this.state.activeVisit.id]],
                        ["order_count", "total_order_amount"]
                    );
                    if (updatedVisit) {
                        this.state.activeVisit.order_count = updatedVisit.order_count;
                        this.state.activeVisit.total_order_amount = updatedVisit.total_order_amount;
                    }
                } catch (e) {
                    this.state.activeVisit.order_count = (this.state.activeVisit.order_count || 0) + 1;
                }
                this.state.activeVisit.is_productive = true;
            }

            this.notification.add(`Order created successfully! Total: ₹${summary.total.toFixed(2)}`, {
                type: "success",
            });

            await this.loadLastOrderDetails();

            this.closeQuickOrder();
            await this.loadTodayBeats();
            await this.loadTodayKpi();

            if (this.state.activeVisit) {
                await this.loadCustomerSummary(this.state.activeVisit.partner_id[0]);
                await this.loadCustomerOrders();
            }

        } catch (error) {
            console.error("Error creating order:", error);

            let errorMsg = "Failed to create order";
            if (error.data && error.data.message) {
                errorMsg += ": " + error.data.message;
            } else if (error.message) {
                errorMsg += ": " + error.message;
            }

            this.notification.add(errorMsg, { type: "danger" });
        }
    }

    async switchQuickOrderTab(tab) {
        this.state.quickOrderTab = tab;
        if (tab === 'must_sell') {
            try {
                // 1. Fetch exact Must Sell configuration
                const mustSellData = await this.orm.call("priority.sell.config", "get_must_sell_products", []);
                this.state.mustSellList = mustSellData;
                this.state.mustSellProducts = mustSellData
                    .map(ms => this.state.allProducts.find(p => p.id === ms.product_id))
                    .filter(Boolean);
                for (const msItem of mustSellData) {
                    const product = this.state.allProducts.find(p => p.id === msItem.product_id);
                    if (product) {
                        this.onQuantityChange(product.id, msItem.min_qty);
                    }
                }
            } catch (error) {
                console.error("Must Sell Load Error:", error);
            }
        }

        if (tab === 'focus_sell') {
            const focusSellData = await this.orm.call("priority.sell.config", "get_priority_sell_products", ['focused_sell']);
            this.state.focusSellList = focusSellData;
            this.state.focusSellProducts = focusSellData
                .map(fs => this.state.allProducts.find(p => p.id === fs.product_id))
                .filter(Boolean);
            // keep old assignment below removed
        }

        if (tab === 'top_selling') {
            try {
                // Pass the partner_id from your activeVisit
                const partnerId = this.state.activeVisit.partner_id[0];
                const data = await this.orm.call("sale.order", "get_top_selling_products", [partnerId, 10]);
                this.state.topSellingList = data;
            } catch (error) {
                console.error("Error loading Top Selling:", error);
                this.notification.add("Failed to load top selling products", { type: "danger" });
            }
        }
    }

    async loadCustomerOrders() {
        if (!this.state.activeVisit) return;
        
        try {
            const orders = await this.orm.searchRead(
                "sale.order",
                [["partner_id", "=", this.state.activeVisit.partner_id[0]]],
                ["id", "name", "date_order", "amount_total", "state", "order_line"],
                { order: "date_order desc", limit: 20 }
            );
            
            for (const order of orders) {
                if (order.order_line && order.order_line.length > 0) {
                    const orderLines = await this.orm.searchRead(
                        "sale.order.line",
                        [["id", "in", order.order_line]],
                        ["product_id", "product_uom_qty", "price_unit", "price_subtotal", "name"]
                    );
                    order.lines = orderLines;
                } else {
                    order.lines = [];
                }
            }
            
            this.state.customerOrders = orders;
        } catch (error) {
            console.error("Error loading customer orders:", error);
            this.state.customerOrders = [];
        }
    }

    async loadCustomerVisits() {
        if (!this.state.activeVisit) return;

        try {
            const visits = await this.orm.searchRead(
                "visit.model",
                [["partner_id", "=", this.state.activeVisit.partner_id[0]]],
                ["id", "actual_start_time", "actual_end_time", "status", "visit_comments", "is_productive"],
                { order: "actual_start_time desc", limit: 20 }
            );

            for (const visit of visits) {
                try {
                    const orders = await this.orm.searchRead(
                        "sale.order",
                        [["visit_id", "=", visit.id]],
                        ["id"]
                    );
                    visit.order_count = orders.length;
                } catch (e) {
                    visit.order_count = 0;
                }
            }

            this.state.customerVisits = visits;
        } catch (error) {
            console.error("Error loading customer visits:", error);
            this.state.customerVisits = [];
        }
    }

    async loadLastOrderDetails() {
        if (!this.state.activeVisit) return;
        
        try {
            const orders = await this.orm.searchRead(
                "sale.order",
                [
                    ["partner_id", "=", this.state.activeVisit.partner_id[0]]
                ],
                ["id", "name", "date_order", "amount_total", "state", "order_line"],
                { order: "date_order desc", limit: 1 }
            );
            
            if (orders.length > 0) {
                const lastOrder = orders[0];
                
                if (lastOrder.order_line && lastOrder.order_line.length > 0) {
                    const orderLines = await this.orm.searchRead(
                        "sale.order.line",
                        [["id", "in", lastOrder.order_line]],
                        ["product_id", "product_uom_qty", "price_unit", "price_subtotal", "name"]
                    );
                    lastOrder.lines = orderLines;
                } else {
                    lastOrder.lines = [];
                }
                
                this.state.lastOrderDetails = lastOrder;
                console.log("✅ Last order loaded:", lastOrder);
            } else {
                this.state.lastOrderDetails = null;
                console.log("ℹ️ No orders found for this customer");
            }
        } catch (error) {
            console.error("Error loading last order details:", error);
            this.state.lastOrderDetails = null;
        }
    }

    async viewOrderDetails(orderId) {
        try {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "sale.order",
                res_id: orderId,
                name: "Order Details",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
            });
        } catch (error) {
            console.error("Error opening order:", error);
            this.notification.add("Failed to open order", { type: "danger" });
        }
    }

    closeStartDayModal() {
        this.state.showStartDayModal = false;
        this.state.startDayForm = {
            todayWorkPlan: "Customer Visit",
            travelType: "",
            vehicleUsed: "",
            uploadedFiles: [],
            locationData: null,
        };
    }

    triggerFileUpload() {
        if (this.startDayFileInputRef.el) {
            this.startDayFileInputRef.el.click();
        }
    }

    handleStartDayFileUpload(event) {
        const files = Array.from(event.target.files);
        if (files.length === 0) return;

        for (const file of files) {
            const reader = new FileReader();
            reader.onload = (e) => {
                this.state.startDayForm.uploadedFiles.push({
                    name: file.name,
                    data: e.target.result.split(",")[1],
                });
            };
            reader.readAsDataURL(file);
        }
        
        this.notification.add("Files uploaded successfully!", { type: "success" });
    }

    async saveStartDay() {
        if (this.state.isProcessing) return;

        const form = this.state.startDayForm;

        if (!form.todayWorkPlan || !form.travelType || !form.vehicleUsed) {
            this.notification.add("Please fill all required fields", { type: "warning" });
            return;
        }

        if (!form.locationData) {
            this.notification.add("Please capture your location first", { type: "warning" });
            return;
        }

        try {
            this.state.isProcessing = true;
            const employeeId = this.getEmployeeId();

            const result = await this.orm.call(
                "hr.employee",
                "create_attendance_checkin",
                [employeeId, form.todayWorkPlan, form.travelType, form.vehicleUsed, form.locationData]
            );

            if (result.success) {
                this.state.currentAttendanceId = result.attendance_id;
                this.state.dayStarted = true;
                this.state.showStartDayModal = false;
                
                this.state.startDayForm = {
                    todayWorkPlan: "Customer Visit",
                    travelType: "",
                    vehicleUsed: "",
                    uploadedFiles: [],
                    locationData: null,
                };
                
                this.notification.add(result.message || "Day started successfully!", { type: "success" });
                
                this.env.bus.trigger('attendance-refresh');
                
                await this.checkDayStatus();
            } else {
                throw new Error(result.error || "Failed to record attendance");
            }

        } catch (error) {
            console.error("Error starting day:", error);
            this.notification.add("Failed to start day: " + (error.message || "Unknown error"), { type: "danger" });
        } finally {
            this.state.isProcessing = false;
        }
    }

    
    openStartVisitModal(beatLine, index) {
        if (!this.state.beatStarted) {
            this.notification.add("Please start a beat first", { type: "warning" });
            return;
        }

        if (this.state.activeVisit) {
            this.notification.add("Please end current visit first", { type: "warning" });
            return;
        }

        if (beatLine.visitStatus && beatLine.visitStatus.status === 'completed') {
            this.notification.add("This customer has already been visited today", { type: "warning" });
            return;
        }

        this.state.currentBeatLine = beatLine;
        this.state.currentBeatLineIndex = index;
        this.state.showStartVisitModal = true;
    }

    closeStartVisitModal() {
        this.state.showStartVisitModal = false;
        this.state.startVisitForm = {
            storeImage: null,
            storeImageName: "",
        };
    }

    handleImageUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
            this.state.startVisitForm.storeImage = e.target.result.split(",")[1];
            this.state.startVisitForm.storeImageName = file.name;
        };
        reader.readAsDataURL(file);
    }

    async saveStartVisit() {
        if (!this.state.currentBeatLine) {
            this.notification.add("Please select a customer", { type: "warning" });
            return;
        }

        if (!this.state.startVisitForm.storeImage) {
            this.notification.add("Store Image is required to start a visit", { type: "warning" });
            return;
        }

        try {
            const employeeId = this.getEmployeeId();
            const now = new Date();
            const formattedNow = this.formatDateTimeForOdoo(now);
            const partnerId = this.state.currentBeatLine.partner_id[0];

            // ── Geo-fence validation ──────────────────────────────────────
            let geoValid = true;
            let geoDistance = 0;
            if (this.state.startDayForm.locationData) {
                try {
                    const loc = this.state.startDayForm.locationData;
                    const geoResult = await this.orm.call(
                        "geo.fence.config",
                        "validate_checkin",
                        [partnerId, loc.latitude, loc.longitude]
                    );
                    if (!geoResult.valid) {
                        // Warn but allow (soft geo-fence)
                        this.notification.add(
                            `⚠️ Geo-fence Warning: ${geoResult.message}`,
                            { type: "warning", sticky: true }
                        );
                        geoValid = false;
                    }
                    geoDistance = geoResult.distance || 0;
                } catch (geoErr) {
                    console.warn("Geo-fence check failed:", geoErr);
                }
            }

            const visitData = {
                employee_id: employeeId,
                beat_id: this.state.selectedBeat.id,
                beat_line_id: this.state.currentBeatLine.id,
                partner_id: partnerId,
                planned_start_time: formattedNow,
                actual_start_time: formattedNow,
                status: "in_progress",
                visit_for: "Secondary Customer",
                today_work_plan: this.state.startDayForm.todayWorkPlan,
                travel_type: this.state.startDayForm.travelType,
                vehicle_used: this.state.startDayForm.vehicleUsed,
                is_productive: true,
                geofence_valid: geoValid,
                geofence_distance: geoDistance,
            };

            // Save GPS co-ordinates captured at day start
            if (this.state.startDayForm.locationData) {
                visitData.checkin_latitude = this.state.startDayForm.locationData.latitude;
                visitData.checkin_longitude = this.state.startDayForm.locationData.longitude;
                visitData.checkin_accuracy = this.state.startDayForm.locationData.accuracy;
            }

            if (this.state.startVisitForm.storeImage) {
                visitData.store_image = this.state.startVisitForm.storeImage;
                visitData.store_image_filename = this.state.startVisitForm.storeImageName;
            }

            const visitIds = await this.orm.create("visit.model", [visitData]);

            this.state.activeVisit = {
                id: visitIds[0],
                beat_id: [this.state.selectedBeat.id, this.state.selectedBeat.name],
                beat_line_id: [this.state.currentBeatLine.id],
                partner_id: [partnerId, this.state.currentBeatLine.partner_id[1]],
                actual_start_time: formattedNow,
                visit_comments: "",
                order_count: 0,
                total_order_amount: 0.0,
            };

            // Pre-load checklist from admin template
            await this._loadChecklist();

            this.notification.add("✅ Visit started successfully!", { type: "success" });

            this.closeStartVisitModal();
            await this.loadTodayBeats();
            await this.loadCustomerSummary(partnerId);
        } catch (error) {
            console.error("Error starting visit:", error);
            this.notification.add("Failed to start visit: " + (error.message || "Unknown error"), { type: "danger" });
        }
    }

    
    openEndVisitModal() {
        if (!this.state.activeVisit) {
            this.notification.add("No active visit to end", { type: "warning" });
            return;
        }

        this.state.endVisitForm.comments = this.state.activeVisit.visit_comments || "";
        this.state.showEndVisitModal = true;
    }

    closeEndVisitModal() {
        this.state.showEndVisitModal = false;
        this.state.endVisitForm = {
            comments: "",
        };
    }

    async saveEndVisit() {
        try {
            const now = new Date();
            const formattedNow = this.formatDateTimeForOdoo(now);

            const updateData = {
                actual_end_time: formattedNow,
                status: "completed",
                is_productive: true,
            };

            if (this.state.endVisitForm.comments) {
                updateData.visit_comments = this.state.endVisitForm.comments;
            }

            await this.orm.write("visit.model", [this.state.activeVisit.id], updateData);

            this.notification.add("Visit ended successfully!", { type: "success" });

            this.state.activeVisit = null;
            this.state.currentBeatLine = null;
            this.state.customerSummary = null;
            this.closeEndVisitModal();

            await this.loadTodayBeats();
            await this.loadTodayKpi();
        } catch (error) {
            console.error("Error ending visit:", error);
            this.notification.add("Failed to end visit", { type: "danger" });
        }
    }

    
    initiateSwitchBeat(newBeat) {
        if (!this.state.beatStarted) {
            this.notification.add("No active beat to switch", { type: "warning" });
            return;
        }

        if (this.state.activeVisit) {
            this.notification.add("Please end the current visit before switching beats", { type: "warning" });
            return;
        }

        
        this.state.switchBeatForm.newBeat = newBeat;
        this.state.switchBeatForm.reason = "";
        this.state.showSwitchBeatModal = true;
    }
    
    closeSwitchBeatModal() {  
        this.state.showSwitchBeatModal = false;
        this.state.switchBeatForm = {
            reason: "",
            newBeat: null,
        };
    }

    selectBeatForSwitch(beatId) { 
        this.state.switchBeatForm.selectedNewBeat = beatId;
    }
    
    async openSwitchBeatSelection() {
        if (this.state.activeVisit) {
            this.notification.add("Please end the current visit before switching beats", { type: "warning" });
            return;
        }

        this.state.switchBeatForm = {
            reason: "",
            newBeat: null,
        };
        this.state.allBeatsForSwap = [];
        this.state.showSwitchBeatModal = true;

        // Load all eligible beats for the swap modal
        await this.loadBeatsForSwap();
    }

    async loadBeatsForSwap() {
        const employeeId = this.getEmployeeId();
        if (!employeeId) return;

        this.state.switchBeatLoading = true;
        try {
            const today = new Date().toISOString().slice(0, 10);

            const beats = await this.orm.searchRead(
                "beat.module",
                [
                    ["employee_id", "=", employeeId],
                    ["status", "in", ["pending", "draft"]],
                    ["id", "!=", this.state.selectedBeat?.id || 0],
                ],
                ["id", "name", "beat_number", "beat_date", "status"]
            );

            for (const beat of beats) {
                const beatLines = await this.orm.searchRead(
                    "beat.line",
                    [["beat_id", "=", beat.id]],
                    ["id", "partner_id", "partner_phone", "partner_email", "partner_street", "sequence"],
                    { order: "sequence asc" }
                );
                beat.beatLines = beatLines;
                beat.customerCount = beatLines.length;

                for (const line of beatLines) {
                    const visits = await this.orm.searchRead(
                        "visit.model",
                        [
                            ["beat_line_id", "=", line.id],
                            ["actual_start_time", ">=", today],
                            ["actual_start_time", "<=", today + " 23:59:59"],
                        ],
                        ["id", "status", "actual_start_time", "actual_end_time"]
                    );
                    line.visitStatus = visits.length > 0 ? visits[0] : null;
                }
            }

            this.state.allBeatsForSwap = beats;
        } catch (error) {
            console.error("Error loading beats for swap:", error);
            this.notification.add("Failed to load available beats", { type: "danger" });
        } finally {
            this.state.switchBeatLoading = false;
        }
    }

    selectNewBeat(beat) {
        this.state.switchBeatForm.newBeat = beat;
    }
    

    getAvailableBeatsForSwitch() {

        return (this.state.allBeatsForSwap || []).filter(b => {
            if (b.id === this.state.selectedBeat?.id) return false;

            if (!b.beatLines || b.beatLines.length === 0) return false;
            const hasIncompleteVisits = b.beatLines.some(line =>
                !line.visitStatus || line.visitStatus.status !== 'completed'
            );

            return hasIncompleteVisits;
        });
    }

    async saveSwitchBeat() {
        if (!this.state.switchBeatForm.reason || !this.state.switchBeatForm.reason.trim()) {
            this.notification.add("Please provide a reason for switching the beat", { type: "warning" });
            return;
        }

        if (!this.state.switchBeatForm.newBeat) {
            this.notification.add("No beat selected for switch", { type: "warning" });
            return;
        }

        try {
            const oldBeatId = this.state.selectedBeat.id;
            const newBeatId = this.state.switchBeatForm.newBeat.id;
            const reason = this.state.switchBeatForm.reason;

            console.log("🔄 Starting beat switch...");
            console.log("Old beat:", oldBeatId, this.state.selectedBeat.beat_number);
            console.log("New beat:", newBeatId, this.state.switchBeatForm.newBeat.beat_number);
            console.log("Reason:", reason);

            const result = await this.orm.call(
                "beat.module",
                "action_swap_beat",  
                [[oldBeatId], newBeatId, reason]
            );

            console.log("✅ Switch result:", result);

            if (result.success) {
  
                await this.loadTodayBeats();
                
                const newBeat = this.state.beats.find(b => b.id === newBeatId);
                
                if (newBeat) {
                    this.state.selectedBeat = newBeat;
                    this.state.currentBeatLineIndex = 0;
                    this.state.beatStarted = true; 
                    this.state.currentBeatLine = null;
                    
                    this.notification.add(
                        `Beat switched successfully! Now working on ${newBeat.beat_number} - ${newBeat.name}`,
                        { type: "success" }
                    );

                    this.closeSwitchBeatModal();
                    await this.loadBeatSwitchHistory();
                } else {
                    throw new Error("Could not find the new beat after switch");
                }
            } else {
                throw new Error(result.error || "Failed to switch beat");
            }

        } catch (error) {
            console.error("❌ Error switching beat:", error);
            this.notification.add("Failed to switch beat: " + (error.message || "Unknown error"), { 
                type: "danger" 
            });
        }
    }

    openStartBeatModal(beat) {
        if (!this.state.dayStarted) {
            this.notification.add("Please start your day first", { type: "warning" });
            return;
        }

        if (this.state.beatStarted) {
            this.notification.add("A beat is already active. Please end it first.", { type: "warning" });
            return;
        }

        if (!beat.beatLines || beat.beatLines.length === 0) {
            this.notification.add("No customers found in this beat", { type: "warning" });
            return;
        }

        this.state.selectedBeat = beat;
        this.state.currentBeatLineIndex = 0;
        this.state.showStartBeatModal = true;
    }

    closeStartBeatModal() {
        this.state.showStartBeatModal = false;
    }

    async saveStartBeat() {
        try {
            console.log("🚀 Starting beat:", this.state.selectedBeat.beat_number);
            
            
            const result = await this.orm.call(
                "beat.module",
                "action_start_beat",
                [[this.state.selectedBeat.id]]
            );

            console.log("✅ Beat start result:", result);

            this.state.beatStarted = true;
            this.state.showStartBeatModal = false;
            
            this.notification.add(`Beat ${this.state.selectedBeat.beat_number} started!`, { type: "success" });
            
            await this.loadTodayBeats();
        } catch (error) {
            console.error("Error starting beat:", error);
            this.notification.add("Failed to start beat: " + (error.message || "Unknown error"), { type: "danger" });
        }
    }

    openEndBeatModal() {
        if (!this.state.beatStarted) {
            this.notification.add("No beat is currently active", { type: "warning" });
            return;
        }

        if (this.state.activeVisit) {
            this.notification.add("Please end the current visit first", { type: "warning" });
            return;
        }

        this.state.showEndBeatModal = true;
    }

    closeEndBeatModal() {
        this.state.showEndBeatModal = false;
    }

    async saveEndBeat() {
        if (!this.state.selectedBeat) {
            this.notification.add("No active beat to end.", { type: "warning" });
            this.state.showEndBeatModal = false;
            return;
        }
        try {
            console.log("🛑 Ending beat:", this.state.selectedBeat.beat_number);


            const result = await this.orm.call(
                "beat.module",
                "action_complete_beat",
                [[this.state.selectedBeat.id]]
            );

            console.log("✅ Beat end result:", result);

            this.state.beatStarted = false;
            this.state.selectedBeat = null;
            this.state.currentBeatLine = null;
            this.state.currentBeatLineIndex = 0;
            this.state.showEndBeatModal = false;

            this.notification.add("Beat ended successfully!", { type: "success" });
            await this.loadTodayBeats();
        } catch (error) {
            console.error("Error ending beat:", error);
            this.notification.add("Failed to end beat: " + (error.message || "Unknown error"), { type: "danger" });
        }
    }
    


    async _buildDayEndSummary() {
        try {
            const employeeId = this.getEmployeeId();
            const now = new Date();
            const pad = n => String(n).padStart(2, '0');
            const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
            const todayStart = today + ' 00:00:00';
            const todayEnd = today + ' 23:59:59';

            const [visits, orders, collections] = await Promise.all([
                this.orm.searchRead(
                    "visit.model",
                    [["employee_id", "=", employeeId],
                     ["actual_start_time", ">=", todayStart],
                     ["actual_start_time", "<=", todayEnd]],
                    ["id", "status", "partner_id", "total_order_amount", "total_collected"]
                ),
                this.orm.searchRead(
                    "sale.order",
                    [["user_id.employee_ids", "in", [employeeId]],
                     ["date_order", ">=", todayStart],
                     ["date_order", "<=", todayEnd],
                     ["state", "in", ["sale", "done"]]],
                    ["id", "name", "partner_id", "amount_total"]
                ),
                this.orm.searchRead(
                    "visit.collection",
                    [["employee_id", "=", employeeId],
                     ["date", "=", today],
                     ["state", "=", "confirmed"]],
                    ["id", "amount", "payment_mode"]
                ),
            ]);

            const completed = visits.filter(v => v.status === 'completed').length;
            const missed = visits.filter(v => v.status === 'planned').length;
            const totalOrderAmt = orders.reduce((s, o) => s + (o.amount_total || 0), 0);
            const totalCollected = collections.reduce((s, c) => s + (c.amount || 0), 0);

            this.state.dayEndSummary = {
                totalVisits: visits.length,
                completedVisits: completed,
                missedVisits: missed,
                totalOrders: orders.length,
                totalOrderAmount: totalOrderAmt,
                totalCollected: totalCollected,
                orderList: orders.slice(0, 10),
            };
        } catch (e) {
            console.warn("Could not build day-end summary:", e);
            this.state.dayEndSummary = null;
        }
    }

    async openEndDayModal() {
        if (this.state.activeVisit) {
            this.notification.add("❌ Please end the current visit before ending the day", { type: "warning" });
            return;
        }

        if (this.state.beatStarted) {
            this.notification.add("❌ Please end the current beat before ending the day", { type: "warning" });
            return;
        }

        if (!this.state.dayStarted) {
            this.notification.add("No day is currently active", { type: "warning" });
            return;
        }

        if (this.state.isProcessing) {
            console.log("⚠️ Already processing end day, ignoring duplicate click");
            return;
        }

        // Build Day-End Summary before confirming
        await this._buildDayEndSummary();
        this.state.isProcessing = true;

        try {
            this.notification.add("📍 Capturing location and ending day...", { type: "info" });

            const locationData = await this.captureLocationWithAddress();

            if (!locationData) {
                throw new Error("Failed to capture location");
            }

            let message = `✅ Location captured!\nAccuracy: ±${Math.round(locationData.accuracy)}m`;
            if (locationData.full_address) {
                message += `\n📮 ${locationData.full_address}`;
            }
            this.notification.add(message, { type: "success", sticky: false });

            console.log("=== Starting End Day Process ===");
            console.log("Location data:", locationData);
            console.log("Current attendance ID:", this.state.currentAttendanceId);

            const employeeId = this.getEmployeeId();

            if (!employeeId) {
                throw new Error("Employee ID not found");
            }

            console.log("Employee ID:", employeeId);

            let attendanceId = this.state.currentAttendanceId;
            
            if (!attendanceId) {
                console.log("No attendance ID found, fetching from today's records...");
                
                const attendanceResult = await this.orm.call(
                    "hr.employee",
                    "get_today_attendance",
                    [employeeId]
                );
                
                console.log("Get today attendance result:", attendanceResult);
                
                if (attendanceResult.success && attendanceResult.attendance_id) {
                    attendanceId = attendanceResult.attendance_id;
                    console.log("Found attendance ID:", attendanceId);
                } else {
                    throw new Error("No active attendance found for today");
                }
            }

            console.log("Using attendance ID:", attendanceId);
            console.log("Calling create_attendance_checkout...");

            const result = await this.orm.call(
                "hr.employee",
                "create_attendance_checkout",
                [employeeId, attendanceId, locationData]
            );

            console.log("Checkout result:", result);

            if (result.success) {
                console.log("✅ Checkout successful! Resetting all state...");
                
                this.state.dayStarted = false;
                this.state.dayEnded = true;
                this.state.beatStarted = false;
                this.state.activeVisit = null;
                this.state.selectedBeat = null;
                this.state.currentBeatLine = null;
                this.state.currentBeatLineIndex = 0;
                this.state.currentAttendanceId = null;
                this.state.customerSummary = null;
                this.state.endDayForm = {
                    locationData: null,
                };
                this.state.isCapturingLocation = false;

                this.notification.add(result.message || "Day ended successfully! ✅", { 
                    type: "success",
                    sticky: false
                });

                this.env.bus.trigger('attendance-refresh');

                console.log("Reloading data in background...");
                setTimeout(async () => {
                    await this.loadTodayBeats();
                    await this.checkDayStatus();
                }, 100);
                
                console.log("✅ End Day Complete!");
                
            } else {
                throw new Error(result.error || "Failed to record check-out");
            }

        } catch (error) {
            console.error("❌ Error ending day:", error);
            this.notification.add("Failed to end day: " + (error.message || "Unknown error"), { 
                type: "danger",
                sticky: true 
            });
        } finally {
            this.state.isProcessing = false;
            console.log("=== End Day Process Complete ===");
        }
    }

    getVisitDuration() {
        if (!this.state.activeVisit) return "0:00";
        
        const start = new Date(this.state.activeVisit.actual_start_time.replace(' ', 'T'));
        const now = new Date();
        const diff = Math.floor((now - start) / 1000 / 60);
        const hours = Math.floor(diff / 60);
        const minutes = diff % 60;
        
        return `${hours}:${minutes.toString().padStart(2, "0")}`;
    }

    getBeatProgress(beat) {
        if (!beat.beatLines || beat.beatLines.length === 0) return "0/0";

        const completed = beat.beatLines.filter(line =>
            line.visitStatus && line.visitStatus.status === 'completed'
        ).length;

        return `${completed}/${beat.beatLines.length}`;
    }

    getBeatProgressPct(beat) {
        if (!beat.beatLines || beat.beatLines.length === 0) return 0;
        const completed = beat.beatLines.filter(line =>
            line.visitStatus && line.visitStatus.status === 'completed'
        ).length;
        return Math.round((completed / beat.beatLines.length) * 100);
    }

    getCustomerVisitStatus(beatLine) {
        if (!beatLine.visitStatus) {
            return { text: "Pending", badge: "bg-secondary", icon: "fa-hourglass-start" };
        }
        
        const status = beatLine.visitStatus.status;
        
        if (status === 'completed') {
            return { text: "Completed", badge: "bg-success", icon: "fa-check" };
        } else if (status === 'in_progress') {
            return { text: "In Progress", badge: "bg-warning", icon: "fa-clock-o" };
        } else {
            return { text: "Pending", badge: "bg-secondary", icon: "fa-hourglass-start" };
        }
    }

    getBeatStatusBadge(beat) {
        if (!beat || !beat.status) {
            return { text: "Pending", class: "bg-secondary" };
        }

        const statusMap = {
            draft: { text: "Draft", class: "bg-secondary" },
            pending: { text: "Pending", class: "bg-warning" },
            in_progress: { text: "In Progress", class: "bg-primary" },
            completed: { text: "Completed", class: "bg-success bg-opacity-50" },
            swapped: { text: "Switched", class: "bg-info bg-opacity-50" },
        };

        return statusMap[beat.status] || { text: beat.status, class: "bg-secondary" };
    }


    async loadTodayKpi() {
        const employeeId = this.getEmployeeId();
        if (!employeeId) return;

        this.state.kpiLoading = true;
        try {
            // Use local date (not UTC) so the filter matches the user's timezone.
            const now = new Date();
            const pad = n => String(n).padStart(2, '0');
            const today = `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
            const todayStart = today + ' 00:00:00';
            const todayEnd = today + ' 23:59:59';

            const completedVisits = await this.orm.searchRead(
                "visit.model",
                [
                    ["employee_id", "=", employeeId],
                    ["status", "=", "completed"],
                    ["actual_start_time", ">=", todayStart],
                    ["actual_start_time", "<=", todayEnd],
                ],
                ["id"]
            );

            let actualOrdersToday = 0;
            let targetVisits = 0;
            let targetOrders = 0;
            let periodActualVisits = 0;
            let periodActualOrders = 0;
            let amountToday = 0.0;
            let amountPeriod = 0.0;
            try {
                const kpiTargets = await this.orm.searchRead(
                    "kpi.target",
                    [["employee_id", "=", employeeId]],
                    ["id", "target_visits", "target_orders", "period_id"],
                    { order: "id desc", limit: 1 }
                );
                if (kpiTargets.length > 0) {
                    targetVisits = kpiTargets[0].target_visits || 0;
                    targetOrders = kpiTargets[0].target_orders || 0;

                    let periodFrom = null;
                    let periodTo = null;
                    if (kpiTargets[0].period_id) {
                        const periodId = Array.isArray(kpiTargets[0].period_id)
                            ? kpiTargets[0].period_id[0]
                            : kpiTargets[0].period_id;
                        const periods = await this.orm.searchRead(
                            "kpi.target.period",
                            [["id", "=", periodId]],
                            ["date_from", "date_to"]
                        );
                        if (periods.length > 0 && periods[0].date_from && periods[0].date_to) {
                            periodFrom = periods[0].date_from + ' 00:00:00';
                            periodTo = periods[0].date_to + ' 23:59:59';

                            const periodVisits = await this.orm.searchRead(
                                "visit.model",
                                [
                                    ["employee_id", "=", employeeId],
                                    ["status", "=", "completed"],
                                    ["actual_start_time", ">=", periodFrom],
                                    ["actual_start_time", "<=", periodTo],
                                ],
                                ["id"]
                            );
                            periodActualVisits = periodVisits.length;
                        }
                    }

                    // Use backend method with sudo() to bypass sale.order record rules
                    try {
                        const orderStats = await this.orm.call(
                            "employee.dashboard",
                            "get_employee_order_stats",
                            [employeeId, todayStart, todayEnd, periodFrom, periodTo]
                        );
                        actualOrdersToday = orderStats.orders_today || 0;
                        periodActualOrders = orderStats.orders_period || 0;
                        amountToday = orderStats.amount_today || 0.0;
                        amountPeriod = orderStats.amount_period || 0.0;
                    } catch (e) {
                        console.warn("Could not load today's orders for KPI:", e);
                    }
                }
            } catch (e) {
                console.warn("Could not load KPI targets:", e);
            }

            const actualVisitsToday = completedVisits.length;

            this.state.todayKpi = {
                actualVisitsToday: actualVisitsToday,
                actualOrdersToday: actualOrdersToday,
                amountToday: amountToday,
                amountPeriod: amountPeriod,
                targetVisits: targetVisits,
                targetOrders: targetOrders,
                periodActualVisits: periodActualVisits,
                periodActualOrders: periodActualOrders,
                remainingVisits: Math.max(0, targetVisits - periodActualVisits),
                remainingOrders: Math.max(0, targetOrders - periodActualOrders),

                visitPct: targetVisits > 0 ? Math.min(100, Math.round((periodActualVisits / targetVisits) * 100)) : 0,
                orderPct: targetOrders > 0 ? Math.min(100, Math.round((periodActualOrders / targetOrders) * 100)) : 0,
            };
        } catch (error) {
            console.error("Error loading today's KPI:", error);
        } finally {
            this.state.kpiLoading = false;
        }
    }

    async loadBeatSwitchHistory() {
        const employeeId = this.getEmployeeId();
        if (!employeeId) return;
        try {
            const today = new Date().toISOString().slice(0, 10);
            const history = await this.orm.call(
                "beat.switch.history",
                "get_history_for_employee",
                [employeeId, today]
            );
            this.state.beatSwitchHistory = history || [];
        } catch (error) {
            console.error("Error loading beat switch history:", error);
            this.state.beatSwitchHistory = [];
        }
    }

    openSwitchHistoryModal() {
        this.state.showSwitchHistoryModal = true;
    }

    closeSwitchHistoryModal() {
        this.state.showSwitchHistoryModal = false;
    }

    // ── NEW: UI helpers for redesigned template ───────────────
    formatAmount(val) {
        if (!val) return "0";
        if (val >= 10000000) return (val / 10000000).toFixed(1) + "Cr";
        if (val >= 100000)   return (val / 100000).toFixed(1) + "L";
        if (val >= 1000)     return (val / 1000).toFixed(0) + "K";
        return Number(val).toFixed(0);
    }

    formatAmountLarge(val) {
        if (!val) return "₹0";
        if (val >= 10000000) return "₹" + (val / 10000000).toFixed(1) + "Cr";
        if (val >= 100000)   return "₹" + (val / 100000).toFixed(1) + "L";
        if (val >= 1000)     return "₹" + (val / 1000).toFixed(0) + "K";
        return "₹" + Number(val).toFixed(0);
    }

    // ── Greeting helpers for the user hero ──────────────────────
    greeting() {
        const h = new Date().getHours();
        if (h < 12) return "Good Morning";
        if (h < 17) return "Good Afternoon";
        return "Good Evening";
    }

    greetingIcon() {
        const h = new Date().getHours();
        if (h < 12) return "fa-sun-o";
        if (h < 17) return "fa-cloud-o";
        return "fa-moon-o";
    }

    userFirstName() {
        const name = this.props.employeeName;
        if (!name) return "there";
        return name.split(" ")[0];
    }

    // Compute todayStats from existing state data (called after beat load)
    _computeTodayStats() {
        if (!this.state.dayStarted) return;
        const beats = this.state.beats || [];
        let total = 0, done = 0, planned = 0, missed = 0, orders = 0, value = 0;

        for (const beat of beats) {
            for (const line of (beat.beatLines || [])) {
                total++;
                const vs = line.visitStatus;
                if (vs) {
                    if (vs.status === 'completed') done++;
                    else if (vs.status === 'planned') planned++;
                    else if (vs.status === 'cancelled') missed++;
                    else planned++;
                } else {
                    planned++;
                }
                if (vs && vs.order_count) orders += vs.order_count;
            }
        }

        const now = new Date();
        const checkin = this.state.currentAttendanceId ? this.state.checkinStartTime : null;
        let workingTime = "0m";
        if (checkin) {
            const mins = Math.round((now - checkin) / 60000);
            workingTime = mins >= 60 ? Math.floor(mins / 60) + "h " + (mins % 60) + "m" : mins + "m";
        }

        const visitPct = total > 0 ? Math.round((done / total) * 100) : 0;

        this.state.todayStats = {
            total, done, planned, missed,
            ordersCount: orders,
            totalValue: value,
            visitPct,
            workingTime,
            avgVisitTime: done > 0 ? "~" + Math.round(30 / done) + "m" : "0m",
        };

        // Set check-in time
        const h = now.getHours();
        const m = String(now.getMinutes()).padStart(2, "0");
        const ampm = h >= 12 ? "pm" : "am";
        this.state.checkinTime = (h % 12 || 12) + ":" + m + " " + ampm;
    }

    // ── NEW: Panel state helpers ──────────────────────────────────

    openPanel(panelName) {
        this.state.activePanel = panelName;
        if (panelName === 'stock') this._initStockPanel();
        if (panelName === 'outstanding') this._loadOutstanding();
        if (panelName === 'retailer') this._loadRetailerOrders();
        if (panelName === 'assets') this._loadCustomerAssets();
        if (panelName === 'collect') this._initCollectPanel();
    }

    _initCollectPanel() {
        // Pre-fill current user as salesperson and collector
        const user = this.env.session || {};
        const userId = user.uid || false;
        const userName = user.name || '';
        if (!this.state.collectForm.salesperson_id) {
            this.state.collectForm.salesperson_id = userId;
            this.state.collectForm.salesperson_name = userName;
        }
        if (!this.state.collectForm.collected_by_id) {
            this.state.collectForm.collected_by_id = userId;
            this.state.collectForm.collected_by_name = userName;
        }
        this._loadOutstanding();
    }

    closePanel() {
        this.state.activePanel = null;
    }

    _initStockPanel() {
        if (!this.state.stockItems || this.state.stockItems.length === 0) {
            this.state.stockItems = [{ id: Date.now(), productId: null, productName: '', price: 0, opening: 0, closing: 0, damaged: 0, suggestions: [], showSuggestions: false }];
        }
    }

    addStockRow() {
        this.state.stockItems.push({ id: Date.now(), productId: null, productName: '', price: 0, opening: 0, closing: 0, damaged: 0, suggestions: [], showSuggestions: false });
    }

    removeStockRow(id) {
        this.state.stockItems = this.state.stockItems.filter(r => r.id !== id);
    }

    async onStockProductChange(ev, rowId) {
        const row = this.state.stockItems.find(r => r.id === rowId);
        if (!row) return;
        const text = ev.target.value;
        row.productName = text;
        row.productId = null;
        row.price = 0;
        row.showSuggestions = false;
        row.suggestions = [];

        if (text.length >= 2) {
            try {
                const products = await this.orm.searchRead(
                    "product.product",
                    [["name", "ilike", text], ["sale_ok", "=", true]],
                    ["id", "name", "list_price", "categ_id"],
                    { limit: 8 }
                );
                row.suggestions = products;
                row.showSuggestions = products.length > 0;
            } catch (e) {
                row.suggestions = [];
                row.showSuggestions = false;
            }
        }
    }

    selectStockProduct(rowId, product) {
        const row = this.state.stockItems.find(r => r.id === rowId);
        if (row) {
            row.productId = product.id;
            row.productName = product.name;
            row.price = product.list_price || 0;
            row.suggestions = [];
            row.showSuggestions = false;
        }
    }

    onStockFieldChange(ev, rowId, field) {
        const row = this.state.stockItems.find(r => r.id === rowId);
        if (row) row[field] = parseFloat(ev.target.value) || 0;
    }

    async saveStockUpdate() {
        const validItems = this.state.stockItems.filter(r => r.productId && r.productName && r.productName.trim());
        if (validItems.length === 0) {
            this.notification.add("Please add at least one product with a valid selection", { type: "warning" });
            return;
        }
        if (!this.state.activeVisit) {
            this.notification.add("No active visit – cannot save stock", { type: "warning" });
            return;
        }
        this.state.isProcessing = true;
        try {
            const visitId = this.state.activeVisit.id;
            const stockLines = validItems.map(item => ({
                product_id: item.productId,
                opening_stock: parseFloat(item.opening) || 0,
                closing_stock: parseFloat(item.closing) || 0,
                damaged_stock: parseFloat(item.damaged) || 0,
            }));
            // Use backend method which handles unlink+create with sudo
            const result = await this.orm.call(
                "visit.stock.ledger",
                "save_stock_from_visit",
                [visitId, stockLines]
            );
            const saved = result && result.saved ? result.saved : validItems.length;
            this.notification.add(
                `Stock updated for ${saved} product(s)!`,
                { type: "success" }
            );
            this.state.stockItems = [];
            this.closePanel();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add("Failed to save stock: " + msg, { type: "danger" });
        } finally {
            this.state.isProcessing = false;
        }
    }

    async _loadOutstanding() {
        if (!this.state.activeVisit) return;
        try {
            const partnerId = this.state.activeVisit.partner_id[0];
            // Use backend method for accurate credit limit + overdue data
            const result = await this.orm.call(
                "visit.collection",
                "get_customer_outstanding",
                [partnerId]
            );
            const cs = this.state.customerSummary;
            this.state.outstandingData = {
                total: result.total || 0,
                totalSales: cs ? cs.totalSales || 0 : 0,
                creditLimit: result.credit_limit || 0,
                overdue: result.overdue || 0,
                lastPayment: result.last_payment || "--",
                lastPaymentAmount: result.last_payment_amount || 0,
            };
        } catch (e) {
            this.state.outstandingData = {
                total: 0, totalSales: 0, creditLimit: 0,
                overdue: 0, lastPayment: "--", lastPaymentAmount: 0
            };
        }
    }

    onCollectFieldChange(field, ev) {
        this.state.collectForm[field] = ev.target.value;
    }

    async searchInvoices(ev) {
        const query = ev.target.value || '';
        this.state.invoiceSearchQuery = query;
        if (!query || query.length < 2) {
            this.state.invoiceSearchResults = [];
            return;
        }
        const partnerId = this.state.activeVisit && this.state.activeVisit.partner_id
            ? this.state.activeVisit.partner_id[0] : false;
        const domain = [
            ['move_type', '=', 'out_invoice'],
            ['state', '=', 'posted'],
            ['payment_state', 'not in', ['paid', 'reversed']],
            ['name', 'ilike', query],
        ];
        if (partnerId) domain.push(['partner_id', '=', partnerId]);
        const results = await this.orm.searchRead('account.move', domain,
            ['id', 'name', 'amount_residual', 'invoice_date_due'], { limit: 8 });
        this.state.invoiceSearchResults = results;
    }

    selectInvoice(inv) {
        this.state.collectForm.invoice_id = inv.id;
        this.state.collectForm.invoice_name = inv.name;
        this.state.collectForm.allocation_type = 'against_invoice';
        this.state.collectForm.is_on_account = false;
        this.state.invoiceSearchResults = [];
        this.state.invoiceSearchQuery = inv.name;
    }

    clearInvoice() {
        this.state.collectForm.invoice_id = false;
        this.state.collectForm.invoice_name = '';
        this.state.invoiceSearchResults = [];
        this.state.invoiceSearchQuery = '';
    }

    async saveCollection() {
        if (!this.state.collectForm.amount || parseFloat(this.state.collectForm.amount) <= 0) {
            this.notification.add("Please enter a valid amount", { type: "warning" });
            return;
        }
        if (!this.state.activeVisit) {
            this.notification.add("No active visit – cannot save collection", { type: "warning" });
            return;
        }
        this.state.isProcessing = true;
        try {
            const visitId = this.state.activeVisit.id;
            const today = new Date().toISOString().slice(0, 10);
            // orm.create returns integer ID or array; normalise to array
            const cf = this.state.collectForm;
            const baseVals = {
                visit_id: visitId,
                date: today,
                amount: parseFloat(cf.amount),
                payment_mode: cf.paymentMode || 'Cash',
                reference: cf.reference || '',
                remarks: cf.remarks || '',
            };
            // Extended fields (require module upgrade to exist in DB)
            const extendedVals = { ...baseVals,
                allocation_type: cf.allocation_type || 'against_invoice',
                is_on_account: cf.is_on_account || false,
            };
            if (cf.invoice_id) extendedVals.invoice_id = cf.invoice_id;
            if (cf.receipt_number) extendedVals.receipt_number = cf.receipt_number;
            if (cf.paymentMode === 'Cheque') {
                if (cf.cheque_number) extendedVals.cheque_number = cf.cheque_number;
                if (cf.cheque_date) extendedVals.cheque_date = cf.cheque_date;
                if (cf.bank_name) extendedVals.bank_name = cf.bank_name;
            } else if (cf.paymentMode === 'UPI') {
                if (cf.upi_reference) extendedVals.upi_reference = cf.upi_reference;
            } else if (cf.paymentMode === 'NEFT') {
                if (cf.transaction_reference) extendedVals.transaction_reference = cf.transaction_reference;
                if (cf.bank_name) extendedVals.bank_name = cf.bank_name;
            }
            if (cf.salesperson_id) extendedVals.salesperson_id = cf.salesperson_id;
            if (cf.collected_by_id) extendedVals.collected_by_id = cf.collected_by_id;

            let createdResult;
            try {
                createdResult = await this.orm.create("visit.collection", [extendedVals]);
            } catch (extErr) {
                const extMsg = (extErr.data && extErr.data.message) || extErr.message || '';
                if (extMsg.includes('does not exist') || extMsg.includes('column')) {
                    // DB not upgraded yet — fall back to base fields only
                    console.warn("Extended collection fields not in DB yet, saving base fields:", extMsg);
                    createdResult = await this.orm.create("visit.collection", [baseVals]);
                } else {
                    throw extErr;
                }
            }
            const ids = Array.isArray(createdResult) ? createdResult : [createdResult];

            // Auto-confirm to create accounting entry; if confirm fails just keep draft
            try {
                await this.orm.call("visit.collection", "action_confirm", [ids]);
            } catch (confirmErr) {
                const cMsg = (confirmErr.data && confirmErr.data.message) || confirmErr.message || String(confirmErr);
                console.warn("Could not auto-confirm collection (saved as draft):", cMsg);
                this.notification.add(
                    `Payment saved as draft (auto-confirm skipped: ${cMsg})`,
                    { type: "warning" }
                );
            }

            this.notification.add(
                `Payment of ₹${parseFloat(this.state.collectForm.amount).toFixed(2)} recorded!`,
                { type: "success" }
            );
            this.state.collectForm = {
                amount: '', paymentMode: 'Cash', reference: '', remarks: '',
                invoice_id: false, invoice_name: '', receipt_number: '',
                is_on_account: false, allocation_type: 'against_invoice',
                cheque_number: '', cheque_date: '', upi_reference: '',
                transaction_reference: '', bank_name: '',
                salesperson_id: false, salesperson_name: '',
                collected_by_id: false, collected_by_name: '',
            };
            this.state.invoiceSearchResults = [];
            this.state.invoiceSearchQuery = '';
            await this._loadOutstanding();
            this.closePanel();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add("Failed to save collection: " + msg, { type: "danger" });
        } finally {
            this.state.isProcessing = false;
        }
    }

    onTicketFieldChange(field, ev) {
        this.state.ticketForm[field] = ev.target.value;
    }

    async saveTicket() {
        if (!this.state.ticketForm.subject) {
            this.notification.add("Please enter a subject", { type: "warning" });
            return;
        }
        if (!this.state.activeVisit) {
            this.notification.add("No active visit – cannot raise ticket", { type: "warning" });
            return;
        }
        try {
            const visitId = this.state.activeVisit.id;
            const today = new Date().toISOString().slice(0, 10);
            await this.orm.create("visit.ticket", [{
                visit_id: visitId,
                date: today,
                subject: this.state.ticketForm.subject,
                category: this.state.ticketForm.category || 'Product Quality',
                priority: this.state.ticketForm.priority || 'Low',
                description: this.state.ticketForm.description || '',
            }]);
            this.notification.add("✅ Support ticket raised successfully!", { type: "success" });
            this.state.ticketForm = { subject: '', category: 'Product Quality', priority: 'Low', description: '' };
            this.closePanel();
        } catch (e) {
            this.notification.add("Failed to raise ticket: " + (e.message || e), { type: "danger" });
        }
    }

    addCompetitor() {
        this.state.competitors.push({ id: Date.now(), brand: '', product: '', shelfPct: 0, price: 0, remarks: '' });
    }

    removeCompetitor(id) {
        this.state.competitors = this.state.competitors.filter(c => c.id !== id);
    }

    onCompetitorFieldChange(ev, id, field) {
        const c = this.state.competitors.find(x => x.id === id);
        if (c) c[field] = ev.target.value;
    }

    async saveCompetitorInfo() {
        const validEntries = this.state.competitors.filter(c => c.brand && c.brand.trim());
        if (validEntries.length === 0) {
            this.notification.add("Please add at least one competitor entry", { type: "warning" });
            return;
        }
        if (!this.state.activeVisit) {
            this.notification.add("No active visit – cannot save competitor info", { type: "warning" });
            return;
        }
        try {
            const visitId = this.state.activeVisit.id;
            // Delete existing competitor entries for this visit and re-create
            const existing = await this.orm.searchRead(
                "visit.competitor",
                [["visit_id", "=", visitId]],
                ["id"]
            );
            if (existing.length) {
                await this.orm.unlink("visit.competitor", existing.map(r => r.id));
            }
            for (const entry of validEntries) {
                await this.orm.create("visit.competitor", [{
                    visit_id: visitId,
                    brand_name: entry.brand,
                    product_name: entry.product || '',
                    shelf_share_pct: parseFloat(entry.shelfPct) || 0,
                    price: parseFloat(entry.price) || 0,
                    remarks: entry.remarks || '',
                }]);
            }
            this.notification.add(`✅ Competitor info saved (${validEntries.length} entries)!`, { type: "success" });
            this.closePanel();
        } catch (e) {
            this.notification.add("Failed to save competitor info: " + (e.message || e), { type: "danger" });
        }
    }

    toggleAccordion(key) {
        this.state.accordionOpen[key] = !this.state.accordionOpen[key];
    }

    toggleChecklistItem(id) {
        const item = this.state.visitChecklist.find(i => i.id === id);
        if (item) item.done = !item.done;
    }

    async saveChecklist() {
        if (!this.state.activeVisit) return;
        try {
            const visitId = this.state.activeVisit.id;
            const responses = this.state.visitChecklist
                .filter(i => typeof i.dbId !== 'undefined')
                .map(i => ({ id: i.dbId, answer: i.done, remarks: i.remarks || '' }));
            if (responses.length) {
                await this.orm.call("visit.checklist", "save_responses", [visitId, responses]);
            }
            this.notification.add("✅ Checklist saved!", { type: "success" });
        } catch (e) {
            this.notification.add("Failed to save checklist: " + (e.message || e), { type: "danger" });
        }
    }

    async _loadChecklist() {
        if (!this.state.activeVisit) return;
        try {
            const visitId = this.state.activeVisit.id;
            let items = await this.orm.call("visit.checklist", "get_for_visit", [visitId]);
            if (!items || items.length === 0) {
                // Create from template if none exist
                await this.orm.call("visit.checklist", "create_from_template", [visitId]);
                items = await this.orm.call("visit.checklist", "get_for_visit", [visitId]);
            }
            if (items && items.length > 0) {
                this.state.visitChecklist = items.map(i => ({
                    id: i.id,
                    dbId: i.id,
                    question: i.question,
                    done: i.answer,
                    requiresPhoto: i.requires_photo,
                    remarks: i.remarks || '',
                }));
            }
        } catch (e) {
            console.error("Error loading checklist:", e);
        }
    }

    get checklistDone() {
        return this.state.visitChecklist.filter(i => i.done).length;
    }

    openRetailerOrders() {
        this.state.activePanel = 'retailer';
        this._loadRetailerOrders();
    }

    async _loadRetailerOrders() {
        try {
            const employeeId = this.getEmployeeId();
            const today = new Date().toISOString().slice(0, 10);
            const firstDay = today.slice(0, 8) + '01';

            const orders = await this.orm.searchRead(
                "sale.order",
                [["user_id.employee_ids", "in", [employeeId]], ["date_order", ">=", firstDay]],
                ["id", "name", "partner_id", "amount_total", "state", "order_line", "date_order"],
                { limit: 200, order: "date_order desc" }
            );

            // Group by partner
            const byPartner = {};
            for (const o of orders) {
                const pid = o.partner_id ? o.partner_id[0] : 0;
                const pname = o.partner_id ? o.partner_id[1] : "Unknown";
                if (!byPartner[pid]) byPartner[pid] = { id: pid, name: pname, orders: [], total: 0, expanded: false };
                byPartner[pid].orders.push(o);
                byPartner[pid].total += o.amount_total || 0;
            }

            this.state.retailerOrders = Object.values(byPartner);
            this.state.retailerOrderStats = {
                retailers: Object.keys(byPartner).length,
                orders: orders.length,
                totalValue: orders.reduce((s, o) => s + (o.amount_total || 0), 0),
            };
            this.state.retailerTab = 'retailers';
        } catch (e) {
            this.state.retailerOrders = [];
            this.state.retailerOrderStats = { retailers: 0, orders: 0, totalValue: 0 };
        }
    }

    // ══════════════════════════════════════════════════════════════
    //  ASSET MANAGEMENT PANEL
    // ══════════════════════════════════════════════════════════════

    async _loadCustomerAssets() {
        if (!this.state.activeVisit) return;
        this.state.assetsLoading = true;
        try {
            const partnerId = this.state.activeVisit.partner_id[0];
            const [assets, masters] = await Promise.all([
                this.orm.call('customer.asset', 'get_assets_for_partner', [partnerId]),
                this.orm.call('customer.asset', 'get_asset_masters', []),
            ]);
            this.state.customerAssets = assets || [];
            this.state.assetMasters = masters || [];
            this.state.assetSubView = 'list';
        } catch (e) {
            console.error('Error loading customer assets:', e);
            this.state.customerAssets = [];
            this.state.assetMasters = [];
        } finally {
            this.state.assetsLoading = false;
        }
    }

    openRegisterAsset() {
        this.state.assetForm = {
            assetMasterId: null,
            assetMasterName: '',
            serialNumber: '',
            notes: '',
        };
        this.state.assetSubView = 'register';
    }

    onAssetMasterChange(ev) {
        const masterId = parseInt(ev.target.value) || null;
        const master = this.state.assetMasters.find(m => m.id === masterId);
        this.state.assetForm.assetMasterId = masterId;
        this.state.assetForm.assetMasterName = master ? master.name : '';
    }

    onAssetFormFieldChange(field, ev) {
        this.state.assetForm[field] = ev.target.value;
    }

    async saveAsset() {
        if (!this.state.assetForm.assetMasterId) {
            this.notification.add('Please select an asset type', { type: 'warning' });
            return;
        }
        if (!this.state.activeVisit) {
            this.notification.add('No active visit – cannot register asset', { type: 'warning' });
            return;
        }
        this.state.isProcessing = true;
        try {
            const employeeId = this.getEmployeeId();
            const today = new Date().toISOString().slice(0, 10);
            await this.orm.create('customer.asset', [{
                partner_id: this.state.activeVisit.partner_id[0],
                asset_master_id: this.state.assetForm.assetMasterId,
                serial_number: this.state.assetForm.serialNumber || '',
                installation_date: today,
                employee_id: employeeId || false,
                visit_id: this.state.activeVisit.id,
                notes: this.state.assetForm.notes || '',
                state: 'assigned',
            }]);
            this.notification.add('✅ Asset registered successfully!', { type: 'success' });
            // Reload asset list
            await this._loadCustomerAssets();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add('Failed to register asset: ' + msg, { type: 'danger' });
        } finally {
            this.state.isProcessing = false;
        }
    }

    openRaiseAssetIssue(asset) {
        this.state.selectedAssetForIssue = asset;
        this.state.assetIssueForm = {
            subject: '',
            caseType: 'maintenance',
            priority: 'Medium',
            description: '',
        };
        this.state.assetSubView = 'issue';
    }

    onAssetIssueFieldChange(field, ev) {
        this.state.assetIssueForm[field] = ev.target.value;
    }

    async saveAssetIssue() {
        if (!this.state.assetIssueForm.subject || !this.state.assetIssueForm.subject.trim()) {
            this.notification.add('Please enter an issue subject', { type: 'warning' });
            return;
        }
        if (!this.state.selectedAssetForIssue) {
            this.notification.add('No asset selected for the issue', { type: 'warning' });
            return;
        }
        this.state.isProcessing = true;
        try {
            const employeeId = this.getEmployeeId();
            const today = new Date().toISOString().slice(0, 10);
            await this.orm.create('asset.issue', [{
                customer_asset_id: this.state.selectedAssetForIssue.id,
                employee_id: employeeId || false,
                visit_id: this.state.activeVisit ? this.state.activeVisit.id : false,
                date: today,
                subject: this.state.assetIssueForm.subject.trim(),
                case_type: this.state.assetIssueForm.caseType || 'maintenance',
                priority: this.state.assetIssueForm.priority || 'Medium',
                description: this.state.assetIssueForm.description || '',
                state: 'open',
            }]);
            this.notification.add('✅ Asset issue logged successfully!', { type: 'success' });
            await this._loadCustomerAssets();
        } catch (e) {
            const msg = (e.data && e.data.message) || e.message || String(e);
            this.notification.add('Failed to log asset issue: ' + msg, { type: 'danger' });
        } finally {
            this.state.isProcessing = false;
        }
    }

    backToAssetList() {
        this.state.assetSubView = 'list';
        this.state.selectedAssetForIssue = null;
    }

    getAssetStateClass(state) {
        const map = {
            assigned: 'emp360-asset-state-assigned',
            returned: 'emp360-asset-state-returned',
            damaged:  'emp360-asset-state-damaged',
            lost:     'emp360-asset-state-lost',
        };
        return map[state] || 'emp360-asset-state-assigned';
    }

    getAssetTypeIcon(assetType) {
        const map = {
            freezer:       'fa-snowflake-o',
            hoarding:      'fa-image',
            vehicle:       'fa-truck',
            display_stand: 'fa-th-large',
            posm:          'fa-sign',
            other:         'fa-archive',
        };
        return map[assetType] || 'fa-archive';
    }

    getAssetTypeGradient(assetType) {
        const map = {
            freezer:       'linear-gradient(135deg,#4cc9f0,#0077b6)',
            hoarding:      'linear-gradient(135deg,#f77f00,#d62828)',
            vehicle:       'linear-gradient(135deg,#06d6a0,#019b72)',
            display_stand: 'linear-gradient(135deg,#7209b7,#560bad)',
            posm:          'linear-gradient(135deg,#f59e0b,#d97706)',
            other:         'linear-gradient(135deg,#4361ee,#3a0ca3)',
        };
        return map[assetType] || 'linear-gradient(135deg,#4361ee,#3a0ca3)';
    }

    getIssuePriorityClass(priority) {
        const map = {
            Critical: 'emp360-badge-danger',
            High:     'emp360-badge-warning',
            Medium:   'emp360-badge-info',
            Low:      'emp360-badge-secondary',
        };
        return map[priority] || 'emp360-badge-secondary';
    }

    getIssueStateClass(state) {
        const map = {
            open:        'emp360-badge-danger',
            in_progress: 'emp360-badge-warning',
            resolved:    'emp360-badge-success',
            closed:      'emp360-badge-secondary',
        };
        return map[state] || 'emp360-badge-secondary';
    }

    toggleRetailerExpand(id) {
        const r = this.state.retailerOrders.find(x => x.id === id);
        if (r) r.expanded = !r.expanded;
    }

    formatAmt(val) {
        return "Rs. " + (parseFloat(val) || 0).toFixed(2);
    }

    getBrochureTypeClass(type) {
        const map = { 'product': 'emp360-badge-info', 'promo': 'emp360-badge-success', 'scheme': 'emp360-badge-warning' };
        return map[type] || 'emp360-badge-secondary';
    }

    // ── Brochure functionality ────────────────────────────────────

    openAddBrochure() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = '.pdf,.doc,.docx,.ppt,.pptx,.jpg,.jpeg,.png';
        input.multiple = false;
        input.onchange = (ev) => {
            const file = ev.target.files[0];
            if (!file) return;
            const sizeMB = (file.size / (1024 * 1024)).toFixed(1) + ' MB';
            const ext = file.name.split('.').pop().toLowerCase();
            let type = 'product';
            if (file.name.toLowerCase().includes('promo') || file.name.toLowerCase().includes('offer') || file.name.toLowerCase().includes('scheme')) {
                type = 'promo';
            } else if (file.name.toLowerCase().includes('dealer') || file.name.toLowerCase().includes('scheme')) {
                type = 'scheme';
            }
            const newBrochure = {
                id: Date.now(),
                name: file.name.replace(/\.[^/.]+$/, ''), // remove extension
                type: type,
                fileSize: sizeMB,
                fileData: null,
                fileName: file.name,
                ext: ext,
            };
            // Read as data URL for sharing
            const reader = new FileReader();
            reader.onload = (e) => {
                newBrochure.fileData = e.target.result;
            };
            reader.readAsDataURL(file);
            this.state.brochures.push(newBrochure);
            this.notification.add(`Brochure "${newBrochure.name}" added successfully!`, { type: "success" });
        };
        input.click();
    }

    shareBrochure(brochure) {
        if (!brochure) return;
        // Build share message for WhatsApp
        const visitName = this.state.customerSummary ? this.state.customerSummary.name : 'Customer';
        const msg = `Hi, please find the brochure: *${brochure.name}* (${brochure.type}) - ${brochure.fileSize}`;

        if (brochure.fileData) {
            // If file is loaded, offer download
            const a = document.createElement('a');
            a.href = brochure.fileData;
            a.download = brochure.fileName || (brochure.name + '.pdf');
            a.click();
            this.notification.add(`Downloading "${brochure.name}"...`, { type: "info" });
        } else {
            // Share via WhatsApp
            const encoded = encodeURIComponent(msg);
            window.open(`https://wa.me/?text=${encoded}`, '_blank');
        }
    }

    downloadBrochure(brochure) {
        if (!brochure) return;
        if (brochure.fileData) {
            const a = document.createElement('a');
            a.href = brochure.fileData;
            a.download = brochure.fileName || (brochure.name + '.pdf');
            a.click();
        } else {
            // Share as text via WhatsApp if no file data
            const msg = `Brochure: *${brochure.name}* (${brochure.type})\nSize: ${brochure.fileSize}`;
            const encoded = encodeURIComponent(msg);
            window.open(`https://wa.me/?text=${encoded}`, '_blank');
        }
    }

    shareAllBrochures() {
        if (!this.state.brochures || this.state.brochures.length === 0) {
            this.notification.add("No brochures to share", { type: "warning" });
            return;
        }
        const visitName = this.state.customerSummary ? this.state.customerSummary.name : 'Customer';
        let msg = `Hi *${visitName}*,\n\nPlease find our latest brochures:\n\n`;
        for (const b of this.state.brochures) {
            const typeEmoji = b.type === 'product' ? '📦' : b.type === 'promo' ? '🎉' : '📋';
            msg += `${typeEmoji} *${b.name}* (${b.fileSize})\n`;
        }
        msg += `\nFor more information, contact us.`;
        const encoded = encodeURIComponent(msg);
        window.open(`https://wa.me/?text=${encoded}`, '_blank');
    }
}

TodayVisit.template = "employee_dashboard_v19.TodayVisit";
TodayVisit.props = {
    employeeId:   { type: Number, optional: true },
    userId:       { type: Number, optional: true },
    employeeName: { type: String, optional: true },
    isManager:    { type: Boolean, optional: true },
};