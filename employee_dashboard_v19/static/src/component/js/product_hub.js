/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ProductHubComponent extends Component {

    setup() {
        this.orm          = useService("orm");
        this.action       = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            activeTab: "dashboard",
            parentOpen: true,

            stats: { totalProducts:0, activeProducts:0, categories:0, activePriceLists:0, activeBatches:0, nearExpiryBatches:0, expiredBatches:0, prioritySellConfigs:0, activeUoms:0, conversionRules:0 },

            categories: [],
            uomList: [],
            uomConversions: [],
            products: [],
            priceBook: [],
            pbPriority: [],
            batches: [],
            prioritySell: [],
            priceChangeLogs: [],
            customerCategories: [],
            employeeCategoryMappings: [],
            customerCategoryMappings: [],
            categoryProducts: [],

            catSearch: "", uomSearch: "", convSearch: "",
            productSearch: "", pbSearch: "", pbTypeFilter: "all",
            batchSearch: "", batchStatus: "all",
            psSearch: "", psClass: "all",
            logSearch: "",
            custCatSearch: "",
            empCatSearch: "", empCatFilter: "all",
            custCatMapSearch: "", custCatMapFilter: "all",
            catProdCategoryId: false, catProdSearch: "", catProdIncludeSub: false,
        });

        onWillStart(async () => { await this.loadStats(); });
    }

    // ── Stats ──────────────────────────────────────────────────────
    async loadStats() {
        try {
            const [tp, ap, cat, pb, uoms, conv, activeBatches, nearExp, expiredBatches, psConfigs] = await Promise.all([
                this.orm.searchCount("product.template", []),
                this.orm.searchCount("product.template", [["active","=",true]]),
                this.orm.searchCount("product.category", []),
                this.orm.searchCount("price.book", [["active","=",true]]),
                this.orm.searchCount("uom.uom", [["active","=",true]]),
                this.orm.searchCount("uom.conversion.rule", [["active","=",true]]),
                this.orm.searchCount("product.batch", [["status","=","active"]]),
                this.orm.searchCount("product.batch", [["status","=","near_expiry"]]),
                this.orm.searchCount("product.batch", [["status","=","expired"]]),
                this.orm.searchCount("priority.sell.config", [["active","=",true]]),
            ]);
            this.state.stats = {
                totalProducts: tp, activeProducts: ap, categories: cat,
                activePriceLists: pb, activeBatches, nearExpiryBatches: nearExp,
                expiredBatches, prioritySellConfigs: psConfigs, activeUoms: uoms, conversionRules: conv
            };
        } catch(e) { console.error("Stats error:", e); }
    }

    // ── Loaders ────────────────────────────────────────────────────
    async loadCategories() {
        const data = await this.orm.searchRead("product.category", [], ["id","complete_name","parent_id"], {limit:200});
        this.state.categories = data;
    }
    async loadUoms() {
        const data = await this.orm.searchRead("uom.uom", [], ["id","name","uom_type","factor","active"], {limit:200});
        this.state.uomList = data;
    }
    async loadConversions() {
        const data = await this.orm.searchRead("uom.conversion.rule", [], ["id","from_uom_id","to_uom_id","factor","is_global","product_id","active"], {limit:200});
        this.state.uomConversions = data;
    }
    async loadProducts() {
        const data = await this.orm.searchRead("product.template", [["active","=",true]], ["id","name","categ_id","list_price","uom_id","default_code"], {limit:200});
        this.state.products = data;
    }
    async loadPriceBook() {
        const [entries, priority] = await Promise.all([
            this.orm.searchRead("price.book", [["active","=",true]],
                ["id","name","price_type","product_id","customer_id","category_id","territory","channel","unit_price","date_from","date_to"], {limit:300}),
            this.orm.searchRead("price.book.priority", [],
                ["id","sequence","price_type","dimensions_display","active"], {order:"sequence asc"}),
        ]);
        this.state.priceBook = entries;
        this.state.pbPriority = priority;
    }
    async loadPbPriority() {
        const data = await this.orm.searchRead("price.book.priority", [],
            ["id","sequence","price_type","dimensions_display","has_customer","has_category","has_territory","has_channel","active"],
            {order:"sequence asc"});
        this.state.pbPriority = data;
    }
    async loadBatches() {
        const data = await this.orm.searchRead("product.batch", [],
            ["id","batch_number","product_id","mfg_date","expiry_date","qty_manufactured","shelf_life","status","near_expiry","active"], {limit:300});
        this.state.batches = data;
    }
    async loadPrioritySell() {
        const data = await this.orm.searchRead("priority.sell.config", [["active","=",true]],
            ["id","product_id","default_code","classification","channel","customer_type","territory","date_from","date_to","min_qty"], {limit:300});
        this.state.prioritySell = data;
    }
    async loadPriceChangeLogs() {
        const data = await this.orm.searchRead("price.change.log", [],
            ["id","product_id","default_code","price_type","old_price","new_price","change_date","changed_by","customer_id","territory","channel","reason"], {limit:300});
        this.state.priceChangeLogs = data;
    }
    async loadCustomerCategories() {
        const data = await this.orm.searchRead("res.partner.category", [],
            ["id","name","parent_id","color"], {limit:200});
        this.state.customerCategories = data;
    }
    async loadEmployeeCategoryMappings() {
        const data = await this.orm.searchRead("employee.category.mapping", [["active","=",true]],
            ["id","employee_id","category_id","level","responsibility","date_from","date_to","assigned_by"], {limit:500});
        this.state.employeeCategoryMappings = data;
    }
    async loadCustomerCategoryMappings() {
        const data = await this.orm.searchRead("customer.category.mapping", [["active","=",true]],
            ["id","partner_id","category_id","level","date_from","date_to","assigned_by"], {limit:500});
        this.state.customerCategoryMappings = data;
    }
    async loadCategoryProducts() {
        const domain = [["active","=",true]];
        if (this.state.catProdCategoryId) {
            domain.push(["categ_id","=",this.state.catProdCategoryId]);
        }
        const data = await this.orm.searchRead("product.template", domain,
            ["id","name","categ_id","list_price","uom_id","default_code","active"], {limit:300});
        this.state.categoryProducts = data;
    }

    // ── Tab switch ─────────────────────────────────────────────────
    async changeTab(tab) {
        this.state.activeTab = tab;
        const loaders = {
            dashboard:               () => this.loadStats(),
            categories:              () => this.loadCategories(),
            uom:                     () => this.loadUoms(),
            uom_conversion:          () => this.loadConversions(),
            products:                () => this.loadProducts(),
            price_lists:             () => this.loadPriceBook(),
            pricebook_config:        () => this.loadPbPriority(),
            batch_master:            () => this.loadBatches(),
            priority_sell:           () => this.loadPrioritySell(),
            price_change_logs:       () => this.loadPriceChangeLogs(),
            customer_categories:     () => this.loadCustomerCategories(),
            employee_categories:     () => Promise.all([this.loadEmployeeCategoryMappings(), this.loadCategories()]),
            customer_cat_mappings:   () => Promise.all([this.loadCustomerCategoryMappings(), this.loadCategories()]),
            category_products:       () => Promise.all([this.loadCategories(), this.loadCategoryProducts()]),
        };
        if (loaders[tab]) await loaders[tab]();
    }

    // ── Category Products filter ──────────────────────────────────
    async selectCategoryForProducts(catId) {
        this.state.catProdCategoryId = catId || false;
        await this.loadCategoryProducts();
    }

    // ── Navigation ────────────────────────────────────────────────
    goBackToDashboard() {
        this.action.doAction(
            "employee_dashboard_v19.action_employee_component",
            { clearBreadcrumbs: true }
        );
    }

    // ── Open forms ─────────────────────────────────────────────────
    openForm(model, resId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: model,
            res_id: resId || false,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ── Priority label helper ──────────────────────────────────────
    getPriorityLabel(priceType) {
        const found = this.state.pbPriority.find(p => p.price_type === priceType);
        return found ? `${found.sequence}${this._ordinal(found.sequence)} - ${found.price_type}` : priceType;
    }
    _ordinal(n) { return n === 1 ? 'st' : n === 2 ? 'nd' : n === 3 ? 'rd' : 'th'; }

    // ── Computed filtered lists ────────────────────────────────────
    get filteredCategories() {
        const q = (this.state.catSearch||"").toLowerCase();
        return q ? this.state.categories.filter(c => c.complete_name.toLowerCase().includes(q)) : this.state.categories;
    }
    get filteredUoms() {
        const q = (this.state.uomSearch||"").toLowerCase();
        return q ? this.state.uomList.filter(u => u.name.toLowerCase().includes(q)) : this.state.uomList;
    }
    get filteredConversions() {
        const q = (this.state.convSearch||"").toLowerCase();
        return q ? this.state.uomConversions.filter(c =>
            (c.from_uom_id&&c.from_uom_id[1]||"").toLowerCase().includes(q) ||
            (c.to_uom_id&&c.to_uom_id[1]||"").toLowerCase().includes(q)
        ) : this.state.uomConversions;
    }
    get filteredProducts() {
        const q = (this.state.productSearch||"").toLowerCase();
        return q ? this.state.products.filter(p =>
            p.name.toLowerCase().includes(q)||(p.default_code||"").toLowerCase().includes(q)
        ) : this.state.products;
    }
    get filteredPriceBook() {
        let data = this.state.priceBook;
        if (this.state.pbTypeFilter !== "all") data = data.filter(p => p.price_type === this.state.pbTypeFilter);
        const q = (this.state.pbSearch||"").toLowerCase();
        if (q) data = data.filter(p => p.name.toLowerCase().includes(q));
        return data;
    }
    get filteredBatches() {
        let data = this.state.batches;
        if (this.state.batchStatus !== "all") data = data.filter(b => b.status === this.state.batchStatus);
        const q = (this.state.batchSearch||"").toLowerCase();
        if (q) data = data.filter(b =>
            b.batch_number.toLowerCase().includes(q)||(b.product_id&&b.product_id[1]||"").toLowerCase().includes(q)
        );
        return data;
    }
    get filteredPrioritySell() {
        let data = this.state.prioritySell;
        if (this.state.psClass !== "all") data = data.filter(p => p.classification === this.state.psClass);
        const q = (this.state.psSearch||"").toLowerCase();
        if (q) data = data.filter(p =>
            (p.product_id&&p.product_id[1]||"").toLowerCase().includes(q)||(p.default_code||"").toLowerCase().includes(q)
        );
        return data;
    }
    get filteredPriceChangeLogs() {
        const q = (this.state.logSearch||"").toLowerCase();
        return q ? this.state.priceChangeLogs.filter(l =>
            (l.product_id&&l.product_id[1]||"").toLowerCase().includes(q)||(l.default_code||"").toLowerCase().includes(q)
        ) : this.state.priceChangeLogs;
    }
    get filteredCustomerCategories() {
        const q = (this.state.custCatSearch||"").toLowerCase();
        return q ? this.state.customerCategories.filter(c => c.name.toLowerCase().includes(q)) : this.state.customerCategories;
    }
    get filteredEmployeeCategoryMappings() {
        let data = this.state.employeeCategoryMappings;
        if (this.state.empCatFilter !== "all") data = data.filter(m => m.level === this.state.empCatFilter);
        const q = (this.state.empCatSearch||"").toLowerCase();
        if (q) data = data.filter(m =>
            (m.employee_id&&m.employee_id[1]||"").toLowerCase().includes(q) ||
            (m.category_id&&m.category_id[1]||"").toLowerCase().includes(q)
        );
        return data;
    }
    get filteredCustomerCategoryMappings() {
        let data = this.state.customerCategoryMappings;
        if (this.state.custCatMapFilter !== "all") data = data.filter(m => m.level === this.state.custCatMapFilter);
        const q = (this.state.custCatMapSearch||"").toLowerCase();
        if (q) data = data.filter(m =>
            (m.partner_id&&m.partner_id[1]||"").toLowerCase().includes(q) ||
            (m.category_id&&m.category_id[1]||"").toLowerCase().includes(q)
        );
        return data;
    }
    get filteredCategoryProducts() {
        const q = (this.state.catProdSearch||"").toLowerCase();
        return q ? this.state.categoryProducts.filter(p =>
            p.name.toLowerCase().includes(q)||(p.default_code||"").toLowerCase().includes(q)
        ) : this.state.categoryProducts;
    }
}

ProductHubComponent.template = "employee_dashboard_v19.ProductHubComponent";
registry.category("actions").add("product_hub_component", ProductHubComponent);
