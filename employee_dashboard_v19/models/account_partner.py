from odoo import api, models, fields


class FmcgAccount(models.Model):
    _name        = 'fmcg.account'
    _description = 'FMCG Account'
    _rec_name    = 'name'
    _order       = 'name asc'
    _inherit     = ['mail.thread', 'mail.activity.mixin']

    # ── Identity ──────────────────────────────────────────────────────
    name = fields.Char(
        string='Account Name', required=True, tracking=True, index=True)

    account_number = fields.Char(
        string='Account Number', readonly=True, copy=False, default='New')

    image_1920 = fields.Image(string='Logo', max_width=1920, max_height=1920)
    image_128  = fields.Image(
        string='Logo (128)', related='image_1920',
        max_width=128, max_height=128, store=True)

    account_record_type = fields.Selection([
        ('retailer',      'Retailer'),
        ('distributor',   'Distributor'),
        ('modern_trade',  'Modern Trade'),
        ('super_stockist','Super Stockist'),
    ], string='Account Record Type', required=True, tracking=True, index=True)

    partner_type_sel = fields.Selection([
        ('wholesale',     'Wholesale'),
        ('retail',        'Retail'),
        ('institutional', 'Institutional'),
        ('export',        'Export'),
    ], string='Type', tracking=True)

    channel = fields.Selection([
        ('general_trade', 'General Trade'),
        ('modern_trade',  'Modern Trade'),
        ('horeca',        'HoReCa'),
        ('institutional', 'Institutional'),
        ('ecommerce',     'E-Commerce'),
        ('distributor',   'Distributor'),
    ], string='Channel', required=True, tracking=True)

    user_id = fields.Many2one(
        'res.users', string='Account Owner', tracking=True,
        default=lambda self: self.env.user, index=True)
    phone           = fields.Char(string='Phone')
    email           = fields.Char(string='Email')
    website         = fields.Char(string='Website')
    parent_id       = fields.Many2one(
        'fmcg.account', string='Parent Account', ondelete='set null', index=True)
    child_ids       = fields.One2many('fmcg.account', 'parent_id', string='Sub Accounts')
    active          = fields.Boolean(string='Is Active', default=True, tracking=True)
    proprietor_name = fields.Char(string='Proprietor / Contact Name')

    # ── 2. Territory & Beat ───────────────────────────────────────────
    territory    = fields.Char(string='Territory', tracking=True)
    territory_id = fields.Many2many(
        'fmcg.territory', 'fmcg_account_territory_rel',
        'account_id', 'territory_id',
        string='Territories', tracking=True, index=True)
    region       = fields.Char(string='Region')
    beat_id      = fields.Many2one('beat.module', string='Beat', tracking=True)

    # ── 3. Outlet Profile ─────────────────────────────────────────────
    outlet_type = fields.Selection([
        ('grocery',     'Grocery'),
        ('supermarket', 'Supermarket'),
        ('hypermarket', 'Hypermarket'),
        ('convenience', 'Convenience Store'),
        ('pharmacy',    'Pharmacy'),
        ('hotel',       'Hotel / Restaurant'),
        ('institution', 'Institution'),
        ('wholesale',   'Wholesale'),
    ], string='Outlet Type')

    visit_frequency = fields.Selection([
        ('daily',    'Daily'),
        ('weekly',   'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly',  'Monthly'),
    ], string='Visit Frequency')

    outlet_class = fields.Selection([
        ('a', 'Class A'),
        ('b', 'Class B'),
        ('c', 'Class C'),
        ('d', 'Class D'),
    ], string='Outlet Class')

    # ── 4. Addresses ──────────────────────────────────────────────────
    billing_street     = fields.Char(string='Billing Street')
    billing_city       = fields.Char(string='Billing City')
    billing_zip        = fields.Char(string='Billing Zip / Postal Code')
    billing_state_id   = fields.Many2one(
        'res.country.state', string='Billing State / Province',
        domain="[('country_id','=',billing_country_id)]")
    billing_country_id = fields.Many2one('res.country', string='Billing Country')

    shipping_street     = fields.Char(string='Shipping Street')
    shipping_city       = fields.Char(string='Shipping City')
    shipping_zip        = fields.Char(string='Shipping Zip / Postal Code')
    shipping_state_id   = fields.Many2one(
        'res.country.state', string='Shipping State / Province',
        domain="[('country_id','=',shipping_country_id)]")
    shipping_country_id = fields.Many2one('res.country', string='Shipping Country')

    # ── 5. Compliance ─────────────────────────────────────────────────
    gstin            = fields.Char(string='GSTIN')
    fssai_license_no = fields.Char(string='FSSAI License No')
    pan              = fields.Char(string='PAN')
    drug_license_no  = fields.Char(string='Drug License No')

    # ── 6. Credit & Outstanding ───────────────────────────────────────
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id)
    credit_limit        = fields.Monetary(string='Credit Limit',        currency_field='currency_id')
    credit_utilized     = fields.Monetary(string='Credit Utilized',     currency_field='currency_id', default=0.0)
    outstanding_balance = fields.Monetary(string='Outstanding Balance', currency_field='currency_id')

    # ── 7. Geolocation & Geo-Fence ────────────────────────────────────
    outlet_latitude  = fields.Float(string='Outlet Latitude',       digits=(10, 7))
    outlet_longitude = fields.Float(string='Outlet Longitude',      digits=(10, 7))
    geofence_radius  = fields.Float(string='Geofence Radius (m)',   default=0.0)

    # ── 8. Sales Activity ─────────────────────────────────────────────
    last_order_date  = fields.Date(    string='Last Order Date')
    last_order_value = fields.Monetary(string='Last Order Value', currency_field='currency_id')
    last_visit_date  = fields.Date(    string='Last Visit Date')

    # ── Notes ─────────────────────────────────────────────────────────
    notes = fields.Html(string='Internal Notes')

    # ── SQL Constraints ───────────────────────────────────────────────
    _sql_constraints = [
        ('account_number_uniq', 'UNIQUE(account_number)',
         'Account Number must be unique.'),
    ]

    # ── Auto-sequence ─────────────────────────────────────────────────
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('account_number', 'New') == 'New':
                vals['account_number'] = self.env['ir.sequence'].next_by_code(
                    'fmcg.account') or 'New'
        return super().create(vals_list)

    def name_get(self):
        return [
            (rec.id,
             f"[{rec.account_number}] {rec.name}"
             if rec.account_number and rec.account_number != 'New'
             else rec.name)
            for rec in self
        ]
