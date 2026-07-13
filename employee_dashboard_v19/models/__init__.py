from . import visit_model
from . import pjp_model
from . import hr_employee
from . import hr_attendance
from . import sale_order
from . import visit_collection
from . import visit_ticket
from . import visit_stock
from . import visit_checklist
from . import visit_competitor
from . import visit_geofence
from . import asset_management
from . import executive_beat_report
from . import dashboard_report
from . import price_book
from . import product_hub_models
from . import uom_uom
from . import territory
from . import account_partner
from . import account_wizard
from . import pjp_generate_wizard
from . import beat_extension
# from . import hr_extension
from . import fmcg_holiday
# sfa_expense_band removed: these models (sfa.expense.band/type, sfa.city.tier,
# sfa.travel.mode, sfa.expense.policy.rule) are owned by the sfa_expense_v19 module.
# Defining them here too produced a conflicting merged schema (required policy_id,
# band_code vs code, duplicate duty fields) that broke the upgrade.
# from . import sfa_expense_band