# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """
    Remove all DB records that reference the deleted scheme.master model.
    Without this cleanup, Odoo returns 404 on any page that cached an
    ir.actions.act_window pointing to 'scheme.master'.
    """
    # 1. Find and delete menu items pointing to scheme.master action
    cr.execute("""
        DELETE FROM ir_ui_menu
        WHERE action LIKE '%scheme.master%'
           OR id IN (
               SELECT res_id FROM ir_model_data
               WHERE model = 'ir.ui.menu'
                 AND name IN ('menu_scheme_master')
                 AND module = 'employee_dashboard_v19'
           )
    """)
    _logger.info("Deleted %d ir_ui_menu records for scheme.master", cr.rowcount)

    # 2. Delete window actions for scheme.master
    cr.execute("""
        DELETE FROM ir_act_window
        WHERE res_model = 'scheme.master'
    """)
    _logger.info("Deleted %d ir_act_window records for scheme.master", cr.rowcount)

    # 3. Delete views for scheme.master
    cr.execute("""
        DELETE FROM ir_ui_view
        WHERE model = 'scheme.master'
    """)
    _logger.info("Deleted %d ir_ui_view records for scheme.master", cr.rowcount)

    # 4. Clean ir.model.data entries that pointed to scheme.master objects
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE model IN ('scheme.master', 'ir.actions.act_window', 'ir.ui.view', 'ir.ui.menu')
          AND name IN (
              'action_scheme_master',
              'view_scheme_master_list',
              'view_scheme_master_form',
              'menu_scheme_master'
          )
          AND module = 'employee_dashboard_v19'
    """)
    _logger.info("Deleted %d ir_model_data records for scheme.master", cr.rowcount)

    # 5. Remove ir.model entry for scheme.master if it somehow still exists
    cr.execute("""
        DELETE FROM ir_model WHERE model = 'scheme.master'
    """)

    # 6. Remove scheme_id column reference on sale_order_line if it points
    #    to old scheme.master (column stays, just clear orphan values)
    cr.execute("""
        UPDATE sale_order_line SET scheme_id = NULL
        WHERE scheme_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM scheme_promotion WHERE id = sale_order_line.scheme_id
          )
    """)
    _logger.info("Cleared %d orphan scheme_id refs on sale_order_line", cr.rowcount)

    _logger.info("scheme.master cleanup migration complete.")
