/** @odoo-module **/
import { ListController } from "@web/views/list/list_controller";
import { listView } from "@web/views/list/list_view";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { useRef, onMounted } from "@odoo/owl";

class FmcgAccountListController extends ListController {
    setup() {
        super.setup();
        this.actionService = useService("action");
    }

    async createRecord() {
        await this.actionService.doAction(
            "employee_dashboard_v19.action_new_account_wizard",
            {
                onClose: async () => {
                    await this.model.load();
                    this.render(true);
                },
            }
        );
    }

    goBackToDashboard() {
        this.actionService.doAction(
            "employee_dashboard_v19.action_employee_component",
            { clearBreadcrumbs: true }
        );
    }
}

FmcgAccountListController.template = "employee_dashboard_v19.FmcgAccountListView";

registry.category("views").add("fmcg_account_list", {
    ...listView,
    Controller: FmcgAccountListController,
});
