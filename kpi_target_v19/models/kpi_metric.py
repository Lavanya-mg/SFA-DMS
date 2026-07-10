# -*- coding: utf-8 -*-
import re
import logging
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)

NUMERIC_TTYPES = ('integer', 'float', 'monetary')
DATE_TTYPES = ('date', 'datetime')

CATEGORY_SELECTION = [
    ('sales', 'Sales'),
    ('visits', 'Visits'),
    ('outlets', 'Outlets'),
    ('collections', 'Collections'),
    ('other', 'Other'),
]
AGGREGATION_SELECTION = [
    ('count', 'COUNT — count records'),
    ('sum', 'SUM — sum field'),
]
DISPLAY_FORMAT_SELECTION = [
    ('number', 'Number (1,234)'),
    ('currency', 'Currency'),
    ('percentage', 'Percentage'),
]


class KpiMetric(models.Model):
    _name = 'kpi.metric'
    _description = 'KPI Metric Definition'
    _order = 'sort_order, name'
    _sql_constraints = [('uniq_key', 'UNIQUE(key)', 'Metric Key must be unique.')]

    name = fields.Char('Metric Name', required=True)
    key = fields.Char('Metric Key', required=True, help='API key — no spaces (e.g. revenue_total).')
    display_label = fields.Char('Display Label', required=True)
    category = fields.Selection(CATEGORY_SELECTION, string='Category', default='sales')

    model_id = fields.Many2one('ir.model', string='Source Object', required=True, ondelete='cascade')
    model_name = fields.Char(related='model_id.model', string='Model', store=True, readonly=True)

    aggregation = fields.Selection(AGGREGATION_SELECTION, string='Aggregation', required=True, default='count')
    date_field_id = fields.Many2one(
        'ir.model.fields', string='Date Field', ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['date', 'datetime'])]")
    aggregate_field_id = fields.Many2one(
        'ir.model.fields', string='Aggregate Field', ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['integer', 'float', 'monetary'])]")
    user_field_id = fields.Many2one(
        'ir.model.fields', string='User/Owner Field', ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', '=', 'many2one')]")

    display_format = fields.Selection(DISPLAY_FORMAT_SELECTION, string='Display Format',
                                      required=True, default='number')
    icon = fields.Char('Icon', help='Icon name (e.g. utility:money or a Font Awesome name).')
    card_color = fields.Char('Card Color', default='#0176d3')
    raw_filter = fields.Text('Advanced Filter', help='Optional Odoo domain, e.g. '
                             "[('state', '=', 'sale')]. Applied on top of the date/user filters.")
    description = fields.Text('Description')
    sort_order = fields.Integer('Sort Order', default=10)
    active = fields.Boolean('Is Active', default=True)
    allow_forecast = fields.Boolean('Allow Forecast')

    # ── Integrity ─────────────────────────────────────────────────────────────
    @api.constrains('key')
    def _check_key(self):
        for rec in self:
            if rec.key and not re.match(r'^[A-Za-z0-9_]+$', rec.key):
                raise ValidationError(_("Metric Key may only contain letters, digits and underscores (no spaces)."))

    @api.constrains('aggregation', 'aggregate_field_id')
    def _check_aggregate(self):
        for rec in self:
            if rec.aggregation == 'sum' and not rec.aggregate_field_id:
                raise ValidationError(_("An Aggregate Field is required when Aggregation is SUM."))

    @api.constrains('raw_filter')
    def _check_raw_filter(self):
        for rec in self:
            if rec.raw_filter:
                try:
                    dom = safe_eval(rec.raw_filter)
                    assert isinstance(dom, list)
                except Exception:
                    raise ValidationError(_("Advanced Filter must be a valid Odoo domain list, "
                                            "e.g. [('state', '=', 'sale')]."))

    # ══════════════════════════════════════════════════════════════════════════
    #  Execution engine — value for a date range (+ optional user)
    # ══════════════════════════════════════════════════════════════════════════
    def compute_value(self, date_from, date_to, user=None):
        self.ensure_one()
        if not self.model_id or not self.model_name:
            return 0.0
        try:
            domain = []
            if self.date_field_id:
                dfn = self.date_field_id.name
                upper = date_to + timedelta(days=1) if date_to else date_to
                domain += [(dfn, '>=', str(date_from)), (dfn, '<', str(upper))]
            if self.user_field_id and user:
                domain.append((self.user_field_id.name, '=', user.id))
            if self.raw_filter:
                extra = safe_eval(self.raw_filter)
                if isinstance(extra, list):
                    domain += extra
            Model = self.env[self.model_name].sudo()
            if self.aggregation == 'sum' and self.aggregate_field_id:
                return float(sum(Model.search(domain).mapped(self.aggregate_field_id.name)))
            return float(Model.search_count(domain))
        except Exception as e:
            _logger.warning("Metric %s compute failed: %s", self.name, e)
            return 0.0

    # ══════════════════════════════════════════════════════════════════════════
    #  RPC API for the KPI Metric Manager (OWL client action)
    # ══════════════════════════════════════════════════════════════════════════
    @api.model
    def get_manager_data(self):
        recs = self.with_context(active_test=False).search([])
        cat_labels = dict(CATEGORY_SELECTION)
        fmt_labels = dict(DISPLAY_FORMAT_SELECTION)

        def agg_display(r):
            if r.aggregation == 'sum':
                fld = r.aggregate_field_id.name if r.aggregate_field_id else '—'
                return 'SUM (%s)' % fld
            return 'COUNT (Id)'

        return {
            'rows': [{
                'id': r.id,
                'name': r.name,
                'key': r.key or '',
                'category': r.category or '',
                'category_label': cat_labels.get(r.category, ''),
                'model_name': r.model_name or '',
                'aggregation_display': agg_display(r),
                'format_label': fmt_labels.get(r.display_format, ''),
                'allow_forecast': r.allow_forecast,
                'active': r.active,
                'card_color': r.card_color or '#0176d3',
            } for r in recs],
        }

    @api.model
    def get_form_options(self):
        models = self.env['ir.model'].sudo().search([('transient', '=', False)], order='name')
        return {
            'models': [{'id': m.id, 'model': m.model, 'name': m.name} for m in models],
            'categories': [{'value': v, 'label': l} for v, l in CATEGORY_SELECTION],
            'aggregations': [{'value': v, 'label': l} for v, l in AGGREGATION_SELECTION],
            'display_formats': [{'value': v, 'label': l} for v, l in DISPLAY_FORMAT_SELECTION],
        }

    @api.model
    def get_model_fields(self, model_id):
        if not model_id:
            return {'all': [], 'numeric': [], 'date': [], 'user': []}
        fields_rs = self.env['ir.model.fields'].sudo().search(
            [('model_id', '=', int(model_id)), ('store', '=', True)], order='field_description')

        def pack(rs):
            return [{'id': f.id, 'name': f.name, 'label': f.field_description or f.name, 'ttype': f.ttype} for f in rs]
        return {
            'all': pack(fields_rs),
            'numeric': pack(fields_rs.filtered(lambda f: f.ttype in NUMERIC_TTYPES)),
            'date': pack(fields_rs.filtered(lambda f: f.ttype in DATE_TTYPES)),
            'user': pack(fields_rs.filtered(lambda f: f.ttype == 'many2one')),
        }

    @api.model
    def get_metric_detail(self, metric_id):
        r = self.with_context(active_test=False).browse(int(metric_id))
        r.ensure_one()
        return {
            'id': r.id, 'name': r.name, 'key': r.key or '', 'display_label': r.display_label or '',
            'category': r.category or 'sales', 'model_id': r.model_id.id or False,
            'aggregation': r.aggregation or 'count',
            'date_field_id': r.date_field_id.id or False,
            'aggregate_field_id': r.aggregate_field_id.id or False,
            'user_field_id': r.user_field_id.id or False,
            'display_format': r.display_format or 'number',
            'icon': r.icon or '', 'card_color': r.card_color or '#0176d3',
            'raw_filter': r.raw_filter or '', 'description': r.description or '',
            'sort_order': r.sort_order, 'active': r.active, 'allow_forecast': r.allow_forecast,
        }

    @api.model
    def save_metric(self, vals, metric_id=None):
        if not vals.get('name'):
            raise UserError(_("Metric Name is required."))
        if not vals.get('key'):
            raise UserError(_("Metric Key is required."))
        if not vals.get('model_id'):
            raise UserError(_("Source Object is required."))

        writable = {
            'name': vals.get('name'),
            'key': (vals.get('key') or '').strip(),
            'display_label': vals.get('display_label') or vals.get('name'),
            'category': vals.get('category') or 'sales',
            'model_id': int(vals['model_id']),
            'aggregation': vals.get('aggregation') or 'count',
            'date_field_id': int(vals['date_field_id']) if vals.get('date_field_id') else False,
            'aggregate_field_id': int(vals['aggregate_field_id']) if vals.get('aggregate_field_id') else False,
            'user_field_id': int(vals['user_field_id']) if vals.get('user_field_id') else False,
            'display_format': vals.get('display_format') or 'number',
            'icon': vals.get('icon') or False,
            'card_color': vals.get('card_color') or '#0176d3',
            'raw_filter': vals.get('raw_filter') or False,
            'description': vals.get('description') or False,
            'sort_order': int(vals['sort_order']) if str(vals.get('sort_order') or '').strip() else 10,
            'active': bool(vals.get('active', True)),
            'allow_forecast': bool(vals.get('allow_forecast')),
        }
        if vals.get('aggregation') != 'sum':
            writable['aggregate_field_id'] = False

        if metric_id:
            rec = self.browse(int(metric_id))
            rec.write(writable)
        else:
            rec = self.create(writable)
        return rec.id

    @api.model
    def toggle_active(self, metric_id):
        rec = self.with_context(active_test=False).browse(int(metric_id))
        rec.active = not rec.active
        return rec.active

    @api.model
    def delete_metric(self, metric_id):
        self.with_context(active_test=False).browse(int(metric_id)).unlink()
        return True
