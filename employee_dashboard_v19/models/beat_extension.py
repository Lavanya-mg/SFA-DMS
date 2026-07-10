# -*- coding: utf-8 -*-
from odoo import models, fields


class BeatModuleExtension(models.Model):
    _inherit = 'beat.module'

    territory_id = fields.Many2one(
        'fmcg.territory', string='Territory',
        tracking=True, index=True, ondelete='restrict')
