# -*- coding: utf-8 -*-
#############################################################################
#   A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Raneesha M K (<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import fields, models, api, _
import re
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class HrEmployee(models.Model):
    """Inherited the model to add some fields"""
    _inherit = 'hr.employee'

    insurance_percentage = fields.Float(string="Phần trăm công ty",
                                        help="Phần trăm bảo hiểm công ty đóng")
    deduced_amount_per_month = fields.Float(string="Lương khấu trừ hàng tháng",
                                            compute="_compute_deducted_amount",
                                            search="_search_deduced_amount_per_month",
                                            help="Số tiền khấu trừ từ lương hàng tháng")
    deduced_amount_per_year = fields.Float(string="Lương khấu trừ hàng năm",
                                           compute="_compute_deducted_amount",
                                           search="_search_deduced_amount_per_year",
                                           help="Số tiền khấu trừ từ lương hàng năm")
    bhxh_amount = fields.Float(string="BHXH hàng tháng", 
                               compute="_compute_social_insurance_amounts",
                               search="_search_bhxh_amount",
                               help="Khoản đóng BHXH hàng tháng của nhân viên")
    bhyt_amount = fields.Float(string="BHYT hàng tháng", 
                               compute="_compute_social_insurance_amounts",
                               search="_search_bhyt_amount",
                               help="Khoản đóng BHYT hàng tháng của nhân viên")
    bhtn_amount = fields.Float(string="BHTN hàng tháng", 
                               compute="_compute_social_insurance_amounts",
                               search="_search_bhtn_amount",
                               help="Khoản đóng BHTN hàng tháng của nhân viên")
    bhxh_company_amount = fields.Float(string="BHXH công ty", 
                                       compute="_compute_social_insurance_amounts",
                                       search="_search_bhxh_company_amount",
                                       help="Khoản đóng BHXH hàng tháng của công ty")
    bhyt_company_amount = fields.Float(string="BHYT công ty", 
                                       compute="_compute_social_insurance_amounts",
                                       search="_search_bhyt_company_amount",
                                       help="Khoản đóng BHYT hàng tháng của công ty")
    bhtn_company_amount = fields.Float(string="BHTN công ty", 
                                       compute="_compute_social_insurance_amounts",
                                       search="_search_bhtn_company_amount",
                                       help="Khoản đóng BHTN hàng tháng của công ty")
    total_social_insurance = fields.Float(string="Tổng BHXH, BHYT, BHTN", 
                                         compute="_compute_social_insurance_amounts",
                                         search="_search_total_social_insurance",
                                         help="Tổng khoản đóng BHXH, BHYT, BHTN hàng tháng của nhân viên")
    insurance_ids = fields.One2many('hr.insurance',
                                    'employee_id',
                                    string="Bảo hiểm", help="Các hợp đồng bảo hiểm của nhân viên",
                                    domain=[('state', '=', 'active')])
    
    # Trường mã số BHXH
    social_insurance_code = fields.Char(
        string='Mã số BHXH', 
        help='Mã số BHXH của nhân viên theo quy định của BHXH Việt Nam',
        copy=False
    )
    social_insurance_status = fields.Selection([
        ('unregistered', 'Chưa đăng ký'),
        ('pending', 'Đang chờ xử lý'),
        ('active', 'Đã kích hoạt'),
        ('suspended', 'Tạm dừng'),
    ], string='Trạng thái BHXH', default='unregistered', 
       help='Trạng thái mã số BHXH của nhân viên')
    social_insurance_issue_date = fields.Date(
        string='Ngày cấp',
        help='Ngày cấp mã số BHXH'
    )
    social_insurance_place = fields.Char(
        string='Nơi cấp', 
        help='Cơ quan cấp mã số BHXH'
    )
    social_insurance_note = fields.Text(
        string='Ghi chú BHXH',
        help='Ghi chú về BHXH của nhân viên'
    )
    has_social_insurance = fields.Boolean(
        string='Đã có BHXH', 
        compute='_compute_has_social_insurance',
        search='_search_has_social_insurance',
        store=True,
        help='Nhân viên đã có mã số BHXH'
    )
    
    # Liên kết với tài liệu BHXH
    social_insurance_document_ids = fields.One2many(
        'social.insurance.document',
        'employee_id',
        string='Tài liệu BHXH',
        help='Tài liệu BHXH của nhân viên'
    )
    
    # Liên kết với lịch sử đóng BHXH
    social_insurance_history_ids = fields.One2many(
        'social.insurance.history',
        'employee_id',
        string='Lịch sử đóng BHXH',
        help='Lịch sử đóng BHXH, BHYT, BHTN của nhân viên'
    )
    
    # Liên kết với trợ cấp BHXH
    social_insurance_benefit_ids = fields.One2many(
        'social.insurance.benefit',
        'employee_id',
        string='Trợ cấp BHXH',
        help='Các khoản trợ cấp BHXH mà nhân viên được hưởng'
    )
    
    # Tổng hợp thông tin về BHXH
    total_bhxh_paid = fields.Float(
        string='Tổng BHXH đã đóng',
        compute='_compute_total_insurance_stats',
        store=False,
        help='Tổng số tiền BHXH đã đóng'
    )
    
    total_benefits_received = fields.Float(
        string='Tổng trợ cấp đã nhận',
        compute='_compute_total_insurance_stats',
        store=False,
        help='Tổng số tiền trợ cấp đã nhận'
    )
    
    bhxh_months_count = fields.Integer(
        string='Số tháng đóng BHXH',
        compute='_compute_total_insurance_stats',
        store=False,
        help='Tổng số tháng đã đóng BHXH'
    )
    
    @api.depends('social_insurance_history_ids', 'social_insurance_benefit_ids')
    def _compute_total_insurance_stats(self):
        for employee in self:
            # Tính tổng tiền BHXH đã đóng
            paid_histories = employee.social_insurance_history_ids.filtered(lambda r: r.state == 'paid')
            employee.total_bhxh_paid = sum(paid_histories.mapped('total_amount'))
            
            # Tính tổng trợ cấp đã nhận
            paid_benefits = employee.social_insurance_benefit_ids.filtered(lambda r: r.state == 'paid')
            employee.total_benefits_received = sum(paid_benefits.mapped('benefit_amount'))
            
            # Đếm số tháng đóng BHXH
            employee.bhxh_months_count = len(paid_histories)
    
    @api.depends('social_insurance_code')
    def _compute_has_social_insurance(self):
        for employee in self:
            employee.has_social_insurance = bool(employee.social_insurance_code)
            
    @api.model
    def _search_has_social_insurance(self, operator, value):
        if operator == '=' and value:
            return [('social_insurance_code', '!=', False)]
        elif operator == '=' and not value:
            return [('social_insurance_code', '=', False)]
        elif operator == '!=' and value:
            return [('social_insurance_code', '=', False)]
        elif operator == '!=' and not value:
            return [('social_insurance_code', '!=', False)]
        return []
    
    @api.constrains('social_insurance_code')
    def _check_social_insurance_code(self):
        for employee in self:
            if employee.social_insurance_code:
                # Kiểm tra định dạng mã số BHXH (10 số)
                if not re.match(r'^\d{10}$', employee.social_insurance_code):
                    raise ValidationError(_('Mã số BHXH phải gồm đúng 10 chữ số!'))
                
                # Kiểm tra trùng lặp mã số BHXH
                other_employee = self.search([
                    ('id', '!=', employee.id),
                    ('social_insurance_code', '=', employee.social_insurance_code)
                ])
                if other_employee:
                    raise ValidationError(_(
                        'Mã số BHXH %s đã được sử dụng bởi nhân viên %s!') % 
                        (employee.social_insurance_code, other_employee[0].name))

    @api.depends('insurance_ids', 'insurance_ids.employee_contribution', 
                'insurance_ids.company_contribution', 'insurance_ids.insurance_type')
    def _compute_social_insurance_amounts(self):
        """Calculate social insurance amounts by type"""
        for emp in self:
            # Initialize values
            emp.bhxh_amount = 0.0
            emp.bhyt_amount = 0.0
            emp.bhtn_amount = 0.0
            emp.bhxh_company_amount = 0.0
            emp.bhyt_company_amount = 0.0
            emp.bhtn_company_amount = 0.0
            emp.total_social_insurance = 0.0
            
            # Current date for active insurances
            current_date = fields.date.today()
            
            for insurance in emp.insurance_ids:
                if insurance.is_social_insurance and insurance.date_from <= current_date:
                    if not insurance.date_to or insurance.date_to >= current_date:
                        # BHXH
                        if insurance.insurance_type == 'bhxh':
                            emp.bhxh_amount = insurance.employee_contribution
                            emp.bhxh_company_amount = insurance.company_contribution
                        # BHYT
                        elif insurance.insurance_type == 'bhyt':
                            emp.bhyt_amount = insurance.employee_contribution
                            emp.bhyt_company_amount = insurance.company_contribution
                        # BHTN
                        elif insurance.insurance_type == 'bhtn':
                            emp.bhtn_amount = insurance.employee_contribution
                            emp.bhtn_company_amount = insurance.company_contribution
            
            # Calculate total
            emp.total_social_insurance = emp.bhxh_amount + emp.bhyt_amount + emp.bhtn_amount

    def _compute_deducted_amount(self):
        """Used to get deduced amount"""
        current_date = fields.date.today()
        for emp in self:
            ins_amount = 0
            for ins in emp.insurance_ids:
                if ins.date_from <= current_date:
                    if ins.date_to >= current_date:
                        if ins.policy_coverage == 'monthly':
                            ins_amount = ins_amount + (ins.amount*12)
                        else:
                            ins_amount = ins_amount + ins.amount
            emp.deduced_amount_per_year = ins_amount-((ins_amount*emp.insurance_percentage)/100)
            emp.deduced_amount_per_month = emp.deduced_amount_per_year/12
            
    @api.model
    def _search_deduced_amount_per_month(self, operator, value):
        # This is a simplified search implementation
        # In a real scenario, you might want to calculate this more precisely
        employees = self.search([])
        matching_employees = self.env['hr.employee']
        
        for emp in employees:
            if operator == '=' and float(emp.deduced_amount_per_month) == float(value):
                matching_employees |= emp
            elif operator == '>' and float(emp.deduced_amount_per_month) > float(value):
                matching_employees |= emp
            elif operator == '<' and float(emp.deduced_amount_per_month) < float(value):
                matching_employees |= emp
            elif operator == '>=' and float(emp.deduced_amount_per_month) >= float(value):
                matching_employees |= emp
            elif operator == '<=' and float(emp.deduced_amount_per_month) <= float(value):
                matching_employees |= emp
        
        return [('id', 'in', matching_employees.ids)]
    
    @api.model
    def _search_deduced_amount_per_year(self, operator, value):
        # Similar simplified approach as above
        employees = self.search([])
        matching_employees = self.env['hr.employee']
        
        for emp in employees:
            if operator == '=' and float(emp.deduced_amount_per_year) == float(value):
                matching_employees |= emp
            elif operator == '>' and float(emp.deduced_amount_per_year) > float(value):
                matching_employees |= emp
            elif operator == '<' and float(emp.deduced_amount_per_year) < float(value):
                matching_employees |= emp
            elif operator == '>=' and float(emp.deduced_amount_per_year) >= float(value):
                matching_employees |= emp
            elif operator == '<=' and float(emp.deduced_amount_per_year) <= float(value):
                matching_employees |= emp
        
        return [('id', 'in', matching_employees.ids)]
    
    def action_verify_social_insurance_code(self):
        """Verify BHXH code with government database (dummy implementation)"""
        self.ensure_one()
        
        if not self.social_insurance_code:
            raise ValidationError(_('Không có mã số BHXH để xác thực.'))
        
        # In real implementation, this would verify with Vietnamese BHXH service
        # For now, we simulate the verification process
        
        # Simulate API call response
        is_valid = True  # Fake validation
        validated_info = {
            'full_name': self.name,
            'issue_date': fields.Date.today() - timedelta(days=365),
            'issue_place': 'Cơ quan BHXH ' + (self.company_id.city or 'TP.HCM'),
            'status': 'active'
        }
        
        if is_valid:
            self.write({
                'social_insurance_status': 'active',
                'social_insurance_issue_date': validated_info['issue_date'],
                'social_insurance_place': validated_info['issue_place']
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Xác thực thành công'),
                    'message': _('Mã số BHXH %s hợp lệ và đã được kích hoạt.') % self.social_insurance_code,
                    'sticky': False,
                    'type': 'success',
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Xác thực thất bại'),
                    'message': _('Mã số BHXH không hợp lệ hoặc đã bị khóa.'),
                    'sticky': False,
                    'type': 'danger',
                }
            }
    
    def action_view_insurance_history(self):
        """View insurance history for this employee"""
        self.ensure_one()
        action = self.env.ref('hr_insurance.action_social_insurance_history').read()[0]
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {'default_employee_id': self.id}
        return action
    
    def action_view_insurance_benefits(self):
        """View insurance benefits for this employee"""
        self.ensure_one()
        action = self.env.ref('hr_insurance.action_social_insurance_benefit').read()[0]
        action['domain'] = [('employee_id', '=', self.id)]
        action['context'] = {'default_employee_id': self.id}
        return action

    @api.model
    def _search_bhxh_amount(self, operator, value):
        # This is a simplified search implementation
        # In a real scenario, you might want to calculate this more precisely
        employees = self.search([])
        matching_employees = self.env['hr.employee']
        
        for emp in employees:
            if operator == '=' and emp.bhxh_amount == value:
                matching_employees |= emp
            elif operator == '>' and emp.bhxh_amount > value:
                matching_employees |= emp
            elif operator == '<' and emp.bhxh_amount < value:
                matching_employees |= emp
            elif operator == '>=' and emp.bhxh_amount >= value:
                matching_employees |= emp
            elif operator == '<=' and emp.bhxh_amount <= value:
                matching_employees |= emp
        
        return [('id', 'in', matching_employees.ids)]
    
    @api.model
    def _search_bhyt_amount(self, operator, value):
        employees = self.search([])
        matching_employees = self.env['hr.employee']
        
        for emp in employees:
            if operator == '=' and emp.bhyt_amount == value:
                matching_employees |= emp
            elif operator == '>' and emp.bhyt_amount > value:
                matching_employees |= emp
            elif operator == '<' and emp.bhyt_amount < value:
                matching_employees |= emp
            elif operator == '>=' and emp.bhyt_amount >= value:
                matching_employees |= emp
            elif operator == '<=' and emp.bhyt_amount <= value:
                matching_employees |= emp
        
        return [('id', 'in', matching_employees.ids)]
    
    @api.model
    def _search_bhtn_amount(self, operator, value):
        employees = self.search([])
        matching_employees = self.env['hr.employee']
        
        for emp in employees:
            if operator == '=' and emp.bhtn_amount == value:
                matching_employees |= emp
            elif operator == '>' and emp.bhtn_amount > value:
                matching_employees |= emp
            elif operator == '<' and emp.bhtn_amount < value:
                matching_employees |= emp
            elif operator == '>=' and emp.bhtn_amount >= value:
                matching_employees |= emp
            elif operator == '<=' and emp.bhtn_amount <= value:
                matching_employees |= emp
        
        return [('id', 'in', matching_employees.ids)]
    
    @api.model
    def _search_bhxh_company_amount(self, operator, value):
        employees = self.search([])
        matching_employees = self.env['hr.employee']
        
        for emp in employees:
            if operator == '=' and emp.bhxh_company_amount == value:
                matching_employees |= emp
            elif operator == '>' and emp.bhxh_company_amount > value:
                matching_employees |= emp
            elif operator == '<' and emp.bhxh_company_amount < value:
                matching_employees |= emp
            elif operator == '>=' and emp.bhxh_company_amount >= value:
                matching_employees |= emp
            elif operator == '<=' and emp.bhxh_company_amount <= value:
                matching_employees |= emp
        
        return [('id', 'in', matching_employees.ids)]
    
    @api.model
    def _search_bhyt_company_amount(self, operator, value):
        employees = self.search([])
        matching_employees = self.env['hr.employee']
        
        for emp in employees:
            if operator == '=' and emp.bhyt_company_amount == value:
                matching_employees |= emp
            elif operator == '>' and emp.bhyt_company_amount > value:
                matching_employees |= emp
            elif operator == '<' and emp.bhyt_company_amount < value:
                matching_employees |= emp
            elif operator == '>=' and emp.bhyt_company_amount >= value:
                matching_employees |= emp
            elif operator == '<=' and emp.bhyt_company_amount <= value:
                matching_employees |= emp
        
        return [('id', 'in', matching_employees.ids)]
    
    @api.model
    def _search_bhtn_company_amount(self, operator, value):
        employees = self.search([])
        matching_employees = self.env['hr.employee']
        
        for emp in employees:
            if operator == '=' and emp.bhtn_company_amount == value:
                matching_employees |= emp
            elif operator == '>' and emp.bhtn_company_amount > value:
                matching_employees |= emp
            elif operator == '<' and emp.bhtn_company_amount < value:
                matching_employees |= emp
            elif operator == '>=' and emp.bhtn_company_amount >= value:
                matching_employees |= emp
            elif operator == '<=' and emp.bhtn_company_amount <= value:
                matching_employees |= emp
        
        return [('id', 'in', matching_employees.ids)]
    
    @api.model
    def _search_total_social_insurance(self, operator, value):
        employees = self.search([])
        matching_employees = self.env['hr.employee']
        
        for emp in employees:
            if operator == '=' and emp.total_social_insurance == value:
                matching_employees |= emp
            elif operator == '>' and emp.total_social_insurance > value:
                matching_employees |= emp
            elif operator == '<' and emp.total_social_insurance < value:
                matching_employees |= emp
            elif operator == '>=' and emp.total_social_insurance >= value:
                matching_employees |= emp
            elif operator == '<=' and emp.total_social_insurance <= value:
                matching_employees |= emp
        
        return [('id', 'in', matching_employees.ids)]
