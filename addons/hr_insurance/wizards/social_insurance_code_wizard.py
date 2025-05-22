# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import re


class SocialInsuranceCodeWizard(models.TransientModel):
    _name = 'social.insurance.code.wizard'
    _description = 'Cập nhật mã số BHXH'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    social_insurance_code = fields.Char(string='Mã số BHXH', required=True)

    @api.model
    def default_get(self, fields):
        res = super(SocialInsuranceCodeWizard, self).default_get(fields)
        if self._context.get('active_model') == 'hr.employee' and self._context.get('active_id'):
            employee = self.env['hr.employee'].browse(self._context.get('active_id'))
            res['employee_id'] = employee.id
            res['social_insurance_code'] = employee.social_insurance_code
        return res

    def action_update_code(self):
        self.ensure_one()
        if not self.social_insurance_code:
            raise UserError(_("Mã số BHXH không được để trống."))
        
        self.employee_id.write({
            'social_insurance_code': self.social_insurance_code
        })
        
        # Cập nhật mã BHXH trong các bảo hiểm hiện có của nhân viên
        insurances = self.env['hr.insurance'].search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['draft', 'active'])
        ])
        if insurances:
            insurances.write({
                'social_insurance_code': self.social_insurance_code
            })
            
        return {'type': 'ir.actions.act_window_close'}


class SocialInsuranceCodeLine(models.TransientModel):
    _name = 'social.insurance.code.line'
    _description = 'Chi tiết mã số BHXH'

    wizard_id = fields.Many2one(
        'social.insurance.code.wizard', 
        string='Wizard'
    )
    employee_id = fields.Many2one(
        'hr.employee', 
        string='Nhân viên',
        required=True
    )
    social_insurance_code = fields.Char(
        string='Mã số BHXH',
        help='Mã số BHXH (10 chữ số)'
    )
    social_insurance_status = fields.Selection([
        ('unregistered', 'Chưa đăng ký'),
        ('pending', 'Đang chờ xử lý'),
        ('active', 'Đã kích hoạt'),
        ('suspended', 'Tạm dừng'),
    ], string='Trạng thái', default='active')
    social_insurance_issue_date = fields.Date(
        string='Ngày cấp'
    )
    social_insurance_place = fields.Char(
        string='Nơi cấp'
    ) 