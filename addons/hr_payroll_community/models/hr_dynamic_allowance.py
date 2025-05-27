# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class HrDynamicAllowance(models.Model):
    _name = 'hr.dynamic.allowance'
    _description = _('Dynamic Allowance')
    _order = 'employee_id, start_date desc'

    name = fields.Char(string=_('Name'), required=True)
    employee_id = fields.Many2one('hr.employee', string=_('Employee'), required=True, index=True)
    contract_id = fields.Many2one('hr.contract', string=_('Contract'))
    allowance_type = fields.Selection([
        ('lunch', _('Lunch')),
        ('transport', _('Transport')),
        ('phone', _('Phone')),
        ('responsibility', _('Responsibility')),
        ('other', _('Other')),
    ], string=_('Allowance Type'), required=True)
    amount = fields.Float(string=_('Amount'), required=True)
    start_date = fields.Date(string=_('Start Date'), required=True)
    end_date = fields.Date(string=_('End Date'))
    state = fields.Selection([
        ('active', _('Active')),
        ('inactive', _('Inactive')),
    ], string=_('Status'), default='active')
    note = fields.Text(string=_('Note'))
    company_id = fields.Many2one('res.company', string=_('Company'), default=lambda self: self.env.company)

    @api.constrains('employee_id', 'allowance_type', 'start_date')
    def _check_unique_allowance(self):
        for rec in self:
            domain = [
                ('employee_id', '=', rec.employee_id.id),
                ('allowance_type', '=', rec.allowance_type),
                ('start_date', '=', rec.start_date),
                ('id', '!=', rec.id)
            ]
            if self.search(domain):
                raise ValidationError(_('This allowance already exists for this employee, type and start date.')) 