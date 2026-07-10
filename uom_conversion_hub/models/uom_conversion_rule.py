from odoo import models, fields, api
from odoo.exceptions import ValidationError

class UomConversionRule(models.Model):
    _name = 'uom.conversion.rule'
    _description = 'Dynamic UoM Conversion Rule'
    _order = 'id desc'

    name = fields.Char(string='Rule Reference', compute='_compute_name', store=True)
    
    from_uom_id = fields.Many2one(
        'uom.uom', 
        string='From UoM', 
        required=True, 
        ondelete='cascade'
    )
    to_uom_id = fields.Many2one(
        'uom.uom', 
        string='To UoM', 
        required=True, 
        ondelete='cascade'
    )
    
    factor = fields.Float(
        string='Conversion Factor', 
        required=True, 
        digits=(16, 5), 
        default=1.0,
        help="How many 'From UoM' fit into one 'To UoM'."
    )
    inverse_factor = fields.Float(
        string='Inverse Factor', 
        compute='_compute_inverse_factor', 
        store=True,
        digits=(16, 5)
    )
    
    is_global = fields.Boolean(
        string='Is Global',
        default=True,
        help="If enabled, applies to all products for this UOM pair. "
             "Disable and set a Product for product-specific conversion."
    )
    product_id = fields.Many2one(
        'product.product',
        string='Product',
        help="Set only for product-specific conversion. Leave blank (and enable Is Global) for global rules."
    )

    active = fields.Boolean(string='Active', default=True)

    @api.constrains('is_global', 'product_id')
    def _check_global_product(self):
        for rec in self:
            if not rec.is_global and not rec.product_id:
                from odoo.exceptions import ValidationError
                raise ValidationError("Product-specific conversion requires a Product. Either enable Is Global or select a product.")

    @api.depends('from_uom_id', 'to_uom_id', 'product_id', 'is_global')
    def _compute_name(self):
        for record in self:
            prod_suffix = f" [{record.product_id.display_name}]" if record.product_id else " [Global]"
            if record.from_uom_id and record.to_uom_id:
                record.name = f"{record.from_uom_id.name} -> {record.to_uom_id.name}{prod_suffix}"
            else:
                record.name = "New Rule"

    @api.depends('factor')
    def _compute_inverse_factor(self):
        for record in self:
            record.inverse_factor = 1.0 / record.factor if record.factor > 0 else 0.0

    @api.constrains('from_uom_id', 'to_uom_id')
    def _check_uom_distinct(self):
        for record in self:
            if record.from_uom_id == record.to_uom_id:
                raise ValidationError("Source UoM ('From UoM') and Destination UoM ('To UoM') cannot be identical!")

    def convert_quantity(self, qty, product, source_uom, target_uom):
        """
        Public execution utility to fetch conversion evaluations cleanly.
        Usage: env['uom.conversion.rule'].convert_quantity(100, product_id, pcs_uom, box_uom)
        """
        rule = self.search([
            ('from_uom_id', '=', source_uom.id),
            ('to_uom_id', '=', target_uom.id),
            '|', ('product_id', '=', product.id), ('product_id', '=', False)
        ], order='product_id desc', limit=1) # Product-specific rules take priority over global ones

        if rule:
            return qty / rule.factor
        
        # Fallback onto core native framework conversions if no custom rules match
        return source_uom._compute_quantity(qty, target_uom)