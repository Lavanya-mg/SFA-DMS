# -*- coding: utf-8 -*-
# Intentionally empty.
#
# The expense configuration models — sfa.expense.band, sfa.expense.type,
# sfa.city.tier(.config), sfa.travel.mode, sfa.expense.policy and
# sfa.expense.policy.rule — are owned by the dedicated `sfa_expense_v19` module.
#
# Previously this file re-declared the same _name models with a different,
# conflicting field set (required policy_id, band_code vs code, a duplicate
# duty_type Selection alongside duty_type_id). Because neither module depends on
# the other, Odoo merged both definitions into one broken schema, which failed
# the upgrade ("column policy_id ... contains null values") and left new fields
# such as type_code unregistered. Keep this module free of those models.
