# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime

class HrOvertime(models.Model):
    _name = 'hr.overtime'
    _description = _('Overtime Request')
    _order = 'date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string=_('Reference'), required=True, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string=_('Employee'), required=True, index=True)
    date = fields.Date(string=_('Date'), required=True, default=fields.Date.today)
    shift_id = fields.Many2one('resource.calendar', string=_('Work Shift'))
    hours = fields.Float(string=_('Overtime Hours'), required=True)
    overtime_type = fields.Selection([
        ('normal', _('Normal Day')),
        ('weekend', _('Weekend')),
        ('holiday', _('Holiday')),
        ('night', _('Night')),
    ], string=_('Overtime Type'), required=True, default='normal')
    state = fields.Selection([
        ('draft', _('Draft')),
        ('to_approve', _('To Approve')),
        ('approved', _('Approved')),
        ('refused', _('Refused')),
        ('cancelled', _('Cancelled')),
    ], string=_('Status'), default='draft', tracking=True)
    approver_id = fields.Many2one('res.users', string=_('Approver'))
    approve_date = fields.Datetime(string=_('Approve Date'))
    payslip_id = fields.Many2one('hr.payslip', string=_('Payslip'))
    wage_coefficient = fields.Float(string=_('Wage Coefficient'), compute='_compute_wage_coefficient', store=True)
    note = fields.Text(string=_('Note'))
    company_id = fields.Many2one('res.company', string=_('Company'), default=lambda self: self.env.company)
    log_ids = fields.One2many('hr.overtime.log', 'overtime_id', string=_('Logs'))

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.overtime') or _('New')
        return super().create(vals)

    @api.depends('overtime_type')
    def _compute_wage_coefficient(self):
        for rec in self:
            if rec.overtime_type == 'normal':
                rec.wage_coefficient = 1.5
            elif rec.overtime_type == 'weekend':
                rec.wage_coefficient = 2.0
            elif rec.overtime_type == 'holiday':
                rec.wage_coefficient = 3.0
            elif rec.overtime_type == 'night':
                rec.wage_coefficient = 1.3
            else:
                rec.wage_coefficient = 1.0

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft requests can be submitted.'))
            rec.state = 'to_approve'

    def action_approve(self):
        for rec in self:
            if rec.state != 'to_approve':
                raise UserError(_('Only requests to approve can be approved.'))
            rec.state = 'approved'
            rec.approver_id = self.env.user
            rec.approve_date = fields.Datetime.now()

    def action_refuse(self):
        for rec in self:
            if rec.state not in ['to_approve', 'draft']:
                raise UserError(_('Only draft or to approve requests can be refused.'))
            rec.state = 'refused'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_reset_draft(self):
        for rec in self:
            rec.state = 'draft'

    @api.model
    def log_action(self, overtime_id, action, user_id=None):
        self.env['hr.overtime.log'].create({
            'overtime_id': overtime_id,
            'action': action,
            'user_id': user_id or self.env.user.id,
            'action_date': fields.Datetime.now(),
        })

class HrOvertimeLog(models.Model):
    _name = 'hr.overtime.log'
    _description = _('Overtime Log')
    _order = 'action_date desc'

    overtime_id = fields.Many2one('hr.overtime', string=_('Overtime'), required=True, ondelete='cascade')
    action = fields.Char(string=_('Action'), required=True)
    user_id = fields.Many2one('res.users', string=_('User'), required=True)
    action_date = fields.Datetime(string=_('Action Date'), required=True) 