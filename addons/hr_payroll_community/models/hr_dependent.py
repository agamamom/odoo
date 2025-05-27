# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class HrDependent(models.Model):
    _name = 'hr.dependent'
    _description = _('Dependent for PIT Deduction')
    _order = 'employee_id, start_date desc'

    name = fields.Char(string=_('Name'), required=True)
    employee_id = fields.Many2one('hr.employee', string=_('Employee'), required=True, index=True)
    relation = fields.Selection([
        ('child', _('Child')),
        ('spouse', _('Spouse')),
        ('parent', _('Parent')),
        ('other', _('Other')),
    ], string=_('Relation'), required=True)
    birthday = fields.Date(string=_('Birthday'))
    id_number = fields.Char(string=_('ID Number'))
    start_date = fields.Date(string=_('Start Date'), required=True)
    end_date = fields.Date(string=_('End Date'))
    state = fields.Selection([
        ('active', _('Active')),
        ('inactive', _('Inactive')),
    ], string=_('Status'), default='active')
    note = fields.Text(string=_('Note'))
    company_id = fields.Many2one('res.company', string=_('Company'), default=lambda self: self.env.company)

    @api.constrains('employee_id', 'id_number', 'start_date')
    def _check_unique_dependent(self):
        for rec in self:
            if rec.id_number:
                domain = [
                    ('employee_id', '=', rec.employee_id.id),
                    ('id_number', '=', rec.id_number),
                    ('start_date', '=', rec.start_date),
                    ('id', '!=', rec.id)
                ]
                if self.search(domain):
                    raise ValidationError(_('This dependent already exists for this employee and start date.')) 