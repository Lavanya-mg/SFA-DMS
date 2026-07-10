# -*- coding: utf-8 -*-
# Odoo 19 Enterprise — Visit Checklist
from odoo import models, fields, api


class ChecklistTemplate(models.Model):
    _name = 'checklist.template'
    _description = 'Checklist Template'
    _order = 'sequence, id'

    name = fields.Char(string='Template Name', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    item_ids = fields.One2many('checklist.template.item', 'template_id', string='Items')


class ChecklistTemplateItem(models.Model):
    _name = 'checklist.template.item'
    _description = 'Checklist Template Item'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'checklist.template', string='Template', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Sequence', default=10)
    question = fields.Char(string='Question / Checklist Item', required=True)
    requires_photo = fields.Boolean(string='Requires Photo Proof', default=False)
    active = fields.Boolean(string='Active', default=True)


class VisitChecklist(models.Model):
    _name = 'visit.checklist'
    _description = 'Visit Checklist Response'
    _order = 'visit_id desc, sequence'

    visit_id = fields.Many2one(
        'visit.model', string='Visit', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(
        related='visit_id.partner_id', string='Customer', store=True, readonly=True)
    employee_id = fields.Many2one(
        related='visit_id.employee_id', string='Employee', store=True, readonly=True)
    template_item_id = fields.Many2one('checklist.template.item', string='Checklist Item')
    sequence = fields.Integer(string='Sequence', default=10)
    question = fields.Char(string='Question', required=True)
    answer = fields.Boolean(string='Yes / Done', default=False)
    requires_photo = fields.Boolean(string='Requires Photo', default=False)
    photo = fields.Binary(string='Photo Proof', attachment=True)
    photo_filename = fields.Char(string='Photo Filename')
    remarks = fields.Text(string='Remarks')

    @api.model
    def create_from_template(self, visit_id, template_id=None):
        visit = self.env['visit.model'].sudo().browse(visit_id)
        if not visit.exists():
            return []
        self.sudo().search([('visit_id', '=', visit_id)]).unlink()
        if template_id:
            template = self.env['checklist.template'].sudo().browse(template_id)
        else:
            template = self.env['checklist.template'].sudo().search(
                [('active', '=', True)], limit=1, order='id asc')
        created = []
        if template:
            for item in template.item_ids.filtered(lambda i: i.active).sorted('sequence'):
                rec = self.sudo().create([{
                    'visit_id': visit_id,
                    'template_item_id': item.id,
                    'sequence': item.sequence,
                    'question': item.question,
                    'requires_photo': item.requires_photo,
                }])
                created.extend(rec.ids)
        return created

    @api.model
    def get_for_visit(self, visit_id):
        items = self.sudo().search([('visit_id', '=', visit_id)], order='sequence')
        return [{
            'id': r.id,
            'question': r.question,
            'answer': r.answer,
            'requires_photo': r.requires_photo,
            'has_photo': bool(r.photo),
            'remarks': r.remarks or '',
        } for r in items]

    @api.model
    def save_responses(self, visit_id, responses):
        for resp in responses:
            rec = self.sudo().browse(resp.get('id'))
            if rec.exists() and rec.visit_id.id == visit_id:
                rec.write({
                    'answer': resp.get('answer', False),
                    'remarks': resp.get('remarks', ''),
                })
        return True
