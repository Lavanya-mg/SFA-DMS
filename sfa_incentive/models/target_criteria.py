# -*- coding: utf-8 -*-
import re
import logging
from datetime import timedelta
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


# Numeric field types eligible for the SUM aggregate.
NUMERIC_TTYPES = ('integer', 'float', 'monetary')
DATE_TTYPES = ('date', 'datetime')

CATEGORY_SELECTION = [
    ('revenue', 'Revenue'),
    ('activity', 'Activity'),
    ('collection', 'Collection'),
    ('coverage', 'Coverage'),
    ('quality', 'Quality'),
    ('other', 'Other'),
]

OPERATOR_SELECTION = [
    ('sum', 'SUM'),
    ('count', 'COUNT'),
]

DISPLAY_FORMAT_SELECTION = [
    ('number', 'Number (1,234)'),
    ('currency', 'Currency'),
    ('percentage', 'Percentage'),
]

# Domain operators offered in the filter builder.
FILTER_OPERATOR_SELECTION = [
    ('=', '='),
    ('!=', '≠'),
    ('>', '>'),
    ('>=', '≥'),
    ('<', '<'),
    ('<=', '≤'),
    ('like', 'contains'),
    ('not like', 'does not contain'),
    ('ilike', 'contains (no case)'),
    ('in', 'in'),
    ('not in', 'not in'),
    ('set', 'is set'),
    ('not set', 'is not set'),
]


class SfaTargetCriteria(models.Model):
    _name = 'sfa.target.criteria'
    _description = 'Target Criteria'
    _order = 'sequence, name'
    _sql_constraints = [('unique_code', 'UNIQUE(code)', 'Criteria code must be unique.')]

    name = fields.Char('Criteria Name', required=True)
    # Code is kept for the incentive engine but is now auto-generated when left blank.
    code = fields.Char('Code', copy=False)
    # Legacy mapping onto kpi.target field names (still used by the incentive dashboard).
    target_field = fields.Char('KPI Target Field', help='Field name on kpi.target for target value')
    actual_field = fields.Char('KPI Actual Field', help='Field name on kpi.target for actual value')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    # ── Target Criteria Manager (dynamic definition) ──────────────────────────
    category = fields.Selection(CATEGORY_SELECTION, string='Category')

    model_id = fields.Many2one(
        'ir.model', string='Search Object', ondelete='cascade',
        help='The Odoo object this criterion measures (e.g. Sales Order).')
    model_name = fields.Char(related='model_id.model', string='Model', store=True, readonly=True)

    # Incentive configuration
    incentive_weight = fields.Float('Incentive Weight %', digits=(5, 2))
    prerequisite_criteria_id = fields.Many2one(
        'sfa.target.criteria', string='Prerequisite Criteria', ondelete='set null',
        help='Optional criterion that must be met before this one pays out.')
    prerequisite_min_pct = fields.Float('Prerequisite Min %', digits=(5, 2), default=90.0)

    # Field mapping
    operator = fields.Selection(OPERATOR_SELECTION, string='Operator', default='count')
    aggregate_field_id = fields.Many2one(
        'ir.model.fields', string='SUM Field', ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['integer', 'float', 'monetary'])]",
        help='Numeric field summed when Operator is SUM.')
    date_field_id = fields.Many2one(
        'ir.model.fields', string='Date Field', ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', 'in', ['date', 'datetime'])]",
        help='Date/Datetime field used for period comparison.')
    user_field_id = fields.Many2one(
        'ir.model.fields', string='User Field', ondelete='set null',
        domain="[('model_id', '=', model_id), ('ttype', '=', 'many2one')]",
        help='Field linking a record to its salesperson/owner.')
    display_format = fields.Selection(
        DISPLAY_FORMAT_SELECTION, string='Display Format', default='number')

    # Filters & logic
    filter_ids = fields.One2many('sfa.target.criteria.filter', 'criteria_id', string='Filters')
    filter_logic = fields.Char(
        'Filter Logic', help='e.g. 1 AND (2 OR 3). Leave blank to AND all filters.')
    filter_count = fields.Integer('Filters', compute='_compute_filter_count', store=True)
    domain_preview = fields.Text('Domain Preview', compute='_compute_domain_preview')

    # ── Computes ──────────────────────────────────────────────────────────────
    @api.depends('filter_ids')
    def _compute_filter_count(self):
        for rec in self:
            rec.filter_count = len(rec.filter_ids)

    @api.depends('filter_ids.field_name', 'filter_ids.operator', 'filter_ids.value', 'filter_logic')
    def _compute_domain_preview(self):
        for rec in self:
            rec.domain_preview = rec._build_domain_preview()

    def _build_domain_preview(self):
        """Human-readable preview of the filter set (best-effort, not executed)."""
        self.ensure_one()
        leaves = []
        for idx, f in enumerate(self.filter_ids.sorted('sequence'), start=1):
            fname = f.field_name or (f.field_id.name if f.field_id else '?')
            if f.operator in ('set', 'not set'):
                leaves.append("%d. %s %s" % (idx, fname, dict(FILTER_OPERATOR_SELECTION).get(f.operator)))
            elif f.operator in ('in', 'not in'):
                vals = [v.strip() for v in (f.value or '').split(',') if v.strip()]
                leaves.append("%d. %s %s [%s]" % (idx, fname, f.operator, ', '.join(vals)))
            else:
                leaves.append("%d. %s %s %s" % (idx, fname, f.operator, f.value or "''"))
        if not leaves:
            return '(no filters — matches all records)'
        logic = (self.filter_logic or '').strip()
        joined = ('\n'.join(leaves))
        if logic:
            return joined + '\n\nLogic: ' + logic
        return joined + ('\n\nLogic: ' + ' AND '.join(str(i + 1) for i in range(len(leaves))) if len(leaves) > 1 else '')

    # ── Code generation / integrity ───────────────────────────────────────────
    def _generate_code(self, name):
        base = re.sub(r'[^a-z0-9]+', '_', (name or 'criteria').strip().lower()).strip('_') or 'criteria'
        code = base
        n = 1
        existing = set(self.sudo().with_context(active_test=False).search(
            [('code', 'like', base + '%')]).mapped('code'))
        while code in existing:
            n += 1
            code = '%s_%d' % (base, n)
        return code

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self._generate_code(vals.get('name'))
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals and not vals.get('code'):
            for rec in self:
                if not rec.code:
                    rec.code = rec._generate_code(vals['name'])
        return super().write(vals)

    @api.constrains('operator', 'aggregate_field_id')
    def _check_sum_field(self):
        for rec in self:
            if rec.operator == 'sum' and rec.model_id and not rec.aggregate_field_id:
                raise ValidationError(_("A SUM Field is required when the operator is SUM."))

    # ══════════════════════════════════════════════════════════════════════════
    #  RPC API for the Target Criteria Manager (OWL client action)
    # ══════════════════════════════════════════════════════════════════════════
    @api.model
    def get_manager_data(self, category=None, active_filter='all'):
        """List-screen payload: stat boxes + rows, honouring the category tab."""
        domain = []
        if category and category != 'all':
            domain.append(('category', '=', category))
        if active_filter == 'active':
            domain.append(('active', '=', True))
        elif active_filter == 'inactive':
            domain.append(('active', '=', False))

        recs = self.with_context(active_test=False).search(domain)
        cat_labels = dict(CATEGORY_SELECTION)
        op_labels = dict(OPERATOR_SELECTION)
        rows = [{
            'id': r.id,
            'name': r.name,
            'category': r.category or '',
            'category_label': cat_labels.get(r.category, ''),
            'model_label': r.model_id.name if r.model_id else '',
            'model_name': r.model_name or '',
            'operator': r.operator or '',
            'operator_label': op_labels.get(r.operator, ''),
            'filter_count': r.filter_count,
            'active': r.active,
        } for r in recs]

        all_recs = self.with_context(active_test=False).search([])
        stats = {
            'total': len(all_recs),
            'active': len(all_recs.filtered('active')),
            'inactive': len(all_recs.filtered(lambda x: not x.active)),
        }
        return {
            'rows': rows,
            'stats': stats,
            'categories': [{'value': v, 'label': l} for v, l in CATEGORY_SELECTION],
        }

    @api.model
    def get_form_options(self):
        """Static option lists needed by the wizard."""
        models = self.env['ir.model'].sudo().search(
            [('transient', '=', False)], order='name')
        criteria = self.with_context(active_test=False).search([])
        return {
            'models': [{'id': m.id, 'model': m.model, 'name': m.name} for m in models],
            'categories': [{'value': v, 'label': l} for v, l in CATEGORY_SELECTION],
            'operators': [{'value': v, 'label': l} for v, l in OPERATOR_SELECTION],
            'display_formats': [{'value': v, 'label': l} for v, l in DISPLAY_FORMAT_SELECTION],
            'filter_operators': [{'value': v, 'label': l} for v, l in FILTER_OPERATOR_SELECTION],
            'criteria': [{'id': c.id, 'name': c.name} for c in criteria],
        }

    @api.model
    def get_model_fields(self, model_id):
        """Fields of the selected object, split by role for the mapping dropdowns."""
        if not model_id:
            return {'all': [], 'numeric': [], 'date': [], 'user': []}
        fields_rs = self.env['ir.model.fields'].sudo().search(
            [('model_id', '=', int(model_id)), ('store', '=', True)], order='field_description')

        def pack(rs):
            return [{
                'id': f.id, 'name': f.name, 'label': f.field_description or f.name,
                'ttype': f.ttype, 'relation': f.relation or '',
                # Selection options so the filter builder can offer value pickers
                # instead of free text for Status/Selection fields.
                'selection': [{'value': s.value, 'label': s.name}
                              for s in f.selection_ids] if f.ttype == 'selection' else [],
            } for f in rs]

        return {
            'all': pack(fields_rs),
            'numeric': pack(fields_rs.filtered(lambda f: f.ttype in NUMERIC_TTYPES)),
            'date': pack(fields_rs.filtered(lambda f: f.ttype in DATE_TTYPES)),
            'user': pack(fields_rs.filtered(lambda f: f.ttype == 'many2one')),
        }

    @api.model
    def get_criteria_detail(self, criteria_id):
        """Full record data to prefill the wizard when editing."""
        rec = self.with_context(active_test=False).browse(int(criteria_id))
        rec.ensure_one()
        return {
            'id': rec.id,
            'name': rec.name,
            'category': rec.category or '',
            'model_id': rec.model_id.id or False,
            'model_field_id': rec.model_id.id or False,
            'incentive_weight': rec.incentive_weight,
            'prerequisite_criteria_id': rec.prerequisite_criteria_id.id or False,
            'prerequisite_min_pct': rec.prerequisite_min_pct,
            'operator': rec.operator or 'count',
            'aggregate_field_id': rec.aggregate_field_id.id or False,
            'date_field_id': rec.date_field_id.id or False,
            'user_field_id': rec.user_field_id.id or False,
            'display_format': rec.display_format or 'number',
            'filter_logic': rec.filter_logic or '',
            'filters': [{
                'field_id': f.field_id.id or False,
                'field_label': f.field_id.field_description or f.field_name or '',
                'operator': f.operator,
                'value': f.value or '',
            } for f in rec.filter_ids.sorted('sequence')],
        }

    @api.model
    def save_criteria(self, vals, criteria_id=None):
        """Create or update a criterion (including its filter lines) from the wizard."""
        if not vals.get('name'):
            raise UserError(_("Criteria Name is required."))
        if not vals.get('model_id'):
            raise UserError(_("Search Object is required."))

        filters = vals.pop('filters', []) or []
        filter_cmds = [(5, 0, 0)]
        for idx, f in enumerate(filters):
            if not f.get('field_id'):
                continue
            filter_cmds.append((0, 0, {
                'sequence': (idx + 1) * 10,
                'field_id': int(f['field_id']),
                'operator': f.get('operator') or '=',
                'value': f.get('value') or '',
            }))

        writable = {
            'name': vals.get('name'),
            'category': vals.get('category') or False,
            'model_id': int(vals['model_id']),
            'incentive_weight': vals.get('incentive_weight') or 0.0,
            'prerequisite_criteria_id': int(vals['prerequisite_criteria_id']) if vals.get('prerequisite_criteria_id') else False,
            'prerequisite_min_pct': vals.get('prerequisite_min_pct') if vals.get('prerequisite_min_pct') not in (None, '') else 90.0,
            'operator': vals.get('operator') or 'count',
            'aggregate_field_id': int(vals['aggregate_field_id']) if vals.get('aggregate_field_id') else False,
            'date_field_id': int(vals['date_field_id']) if vals.get('date_field_id') else False,
            'user_field_id': int(vals['user_field_id']) if vals.get('user_field_id') else False,
            'display_format': vals.get('display_format') or 'number',
            'filter_logic': vals.get('filter_logic') or False,
            'filter_ids': filter_cmds,
        }

        # No sudo: the model ACL restricts create/write/unlink to managers
        # (base.group_system), so config edits stay admin-only.
        if criteria_id:
            rec = self.browse(int(criteria_id))
            rec.write(writable)
        else:
            rec = self.create(writable)
        return rec.id

    @api.model
    def toggle_active(self, criteria_id):
        rec = self.with_context(active_test=False).browse(int(criteria_id))
        rec.active = not rec.active
        return rec.active

    @api.model
    def delete_criteria(self, criteria_id):
        self.with_context(active_test=False).browse(int(criteria_id)).unlink()
        return True

    # ══════════════════════════════════════════════════════════════════════════
    #  Execution engine — run a criterion against its object for a given
    #  employee + date range and return the SUM/COUNT achievement value.
    # ══════════════════════════════════════════════════════════════════════════
    def _cast_scalar(self, field, raw):
        """Cast a filter value string to the field's Python type."""
        ttype = field.ttype if field else 'char'
        try:
            if ttype == 'integer' or ttype == 'many2one':
                return int(raw)
            if ttype in ('float', 'monetary'):
                return float(raw)
            if ttype == 'boolean':
                return str(raw).strip().lower() in ('1', 'true', 'yes', 't')
        except (ValueError, TypeError):
            return raw
        return raw

    def _filter_leaf(self, f):
        """Turn one filter line into an Odoo domain leaf tuple."""
        fname = f.field_name or (f.field_id.name if f.field_id else 'id')
        op = f.operator
        if op == 'set':
            return (fname, '!=', False)
        if op == 'not set':
            return (fname, '=', False)
        if op in ('in', 'not in'):
            vals = [self._cast_scalar(f.field_id, v.strip())
                    for v in (f.value or '').split(',') if v.strip() != '']
            return (fname, op, vals)
        return (fname, op, self._cast_scalar(f.field_id, f.value))

    def _logic_to_domain(self, logic, leaves):
        """Compile an infix logic expression (e.g. '1 AND (2 OR 3)') into an
        Odoo prefix domain. Falls back to implicit-AND of all leaves on error."""
        tokens = re.findall(r'\(|\)|\d+|AND|OR|and|or|&&|\|\|', logic or '')

        def norm(t):
            tu = t.upper()
            if tu in ('AND', '&&'):
                return 'AND'
            if tu in ('OR', '||'):
                return 'OR'
            return t
        tokens = [norm(t) for t in tokens]

        prec = {'OR': 1, 'AND': 2}
        output, ops = [], []
        for t in tokens:
            if t.isdigit():
                output.append(t)
            elif t in prec:
                while ops and ops[-1] in prec and prec[ops[-1]] >= prec[t]:
                    output.append(ops.pop())
                ops.append(t)
            elif t == '(':
                ops.append(t)
            elif t == ')':
                while ops and ops[-1] != '(':
                    output.append(ops.pop())
                if ops and ops[-1] == '(':
                    ops.pop()
        while ops:
            output.append(ops.pop())

        stack = []
        for t in output:
            if t in prec:
                if len(stack) < 2:
                    return list(leaves)
                b = stack.pop()
                a = stack.pop()
                stack.append(['&' if t == 'AND' else '|'] + a + b)
            else:
                idx = int(t) - 1
                if 0 <= idx < len(leaves):
                    stack.append([leaves[idx]])
                else:
                    return list(leaves)
        return stack[0] if len(stack) == 1 else list(leaves)

    def _compile_filter_domain(self):
        self.ensure_one()
        leaves = [self._filter_leaf(f) for f in self.filter_ids.sorted('sequence')]
        if not leaves:
            return []
        logic = (self.filter_logic or '').strip()
        if not logic:
            return leaves  # implicit AND
        return self._logic_to_domain(logic, leaves)

    def _resolve_user_value(self, employee):
        """Map the target's employee onto the value expected by the user field."""
        self.ensure_one()
        rel = self.user_field_id.relation if self.user_field_id else False
        if rel == 'hr.employee':
            return employee.id
        if rel == 'res.partner':
            return employee.user_id.partner_id.id if employee.user_id else False
        # res.users or any other many2one → the employee's linked user
        return employee.user_id.id if employee.user_id else False

    def _build_execution_domain(self, employee, date_from, date_to):
        self.ensure_one()
        domain = []
        if self.date_field_id:
            dfn = self.date_field_id.name
            # Upper bound is exclusive next-day so Datetime fields include the whole
            # last day (e.g. sale.order.date_order at 18:00 on date_to).
            upper = date_to + timedelta(days=1) if date_to else date_to
            domain += [(dfn, '>=', str(date_from)), (dfn, '<', str(upper))]
        domain += self._compile_filter_domain()
        return domain

    def compute_value_for(self, employee, date_from, date_to):
        """Return the SUM/COUNT achievement for one employee in a date range."""
        self.ensure_one()
        if not self.model_id or not self.model_name:
            return 0.0
        try:
            # Cannot attribute records to an employee without a resolvable user value.
            user_val = self._resolve_user_value(employee) if self.user_field_id else None
            if self.user_field_id and not user_val:
                return 0.0
            domain = self._build_execution_domain(employee, date_from, date_to)
            if self.user_field_id:
                domain.append((self.user_field_id.name, '=', user_val))
            Model = self.env[self.model_name].sudo()
            if self.operator == 'sum' and self.aggregate_field_id:
                records = Model.search(domain)
                return float(sum(records.mapped(self.aggregate_field_id.name)))
            return float(Model.search_count(domain))
        except Exception as e:
            _logger.warning("Criteria %s compute failed: %s", self.name, e)
            return 0.0


class SfaTargetCriteriaFilter(models.Model):
    _name = 'sfa.target.criteria.filter'
    _description = 'Target Criteria Filter'
    _order = 'sequence, id'

    criteria_id = fields.Many2one(
        'sfa.target.criteria', string='Criteria', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    field_id = fields.Many2one(
        'ir.model.fields', string='Field', required=True, ondelete='cascade')
    field_name = fields.Char(related='field_id.name', string='Field Name', store=True, readonly=True)
    operator = fields.Selection(FILTER_OPERATOR_SELECTION, string='Operator', required=True, default='=')
    value = fields.Char('Value')
