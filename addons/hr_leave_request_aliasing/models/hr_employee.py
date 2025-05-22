# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
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
from odoo import api, fields, models


class HrEmployee(models.Model):
    """Mở rộng model hr.employee để thêm trường liên kết đến thông tin BHXH"""
    _inherit = 'hr.employee'

    employee_insurance_ids = fields.One2many('hr.employee.insurance', 'employee_id',
                                  string='Thông tin BHXH')
    has_insurance = fields.Boolean(string='Có BHXH', compute='_compute_has_insurance',
                                 store=True, help='Nhân viên có BHXH không')
    active_insurance_id = fields.Many2one('hr.employee.insurance',
                                        compute='_compute_active_insurance',
                                        string='BHXH hiện tại')
    insurance_number = fields.Char(related='active_insurance_id.insurance_number',
                                 string='Mã số BHXH', readonly=True)
    insurance_issue_date = fields.Date(related='active_insurance_id.issue_date',
                                     string='Ngày tham gia BHXH', readonly=True)
    insurance_contribution_months = fields.Integer(related='active_insurance_id.contribution_months',
                                               string='Số tháng đóng BHXH', readonly=True)

    @api.depends('employee_insurance_ids')
    def _compute_has_insurance(self):
        """Tính toán xem nhân viên có BHXH không dựa trên danh sách BHXH"""
        for employee in self:
            employee.has_insurance = bool(employee.employee_insurance_ids)

    @api.depends('employee_insurance_ids', 'employee_insurance_ids.is_active')
    def _compute_active_insurance(self):
        """Tìm thẻ BHXH đang hoạt động của nhân viên"""
        for employee in self:
            active_insurance = employee.employee_insurance_ids.filtered(lambda i: i.is_active)
            employee.active_insurance_id = active_insurance[:1] if active_insurance else False

    def get_insurance_allowance(self, leave_type, days, salary=None):
        """Tính toán trợ cấp BHXH dựa trên loại nghỉ phép, số ngày và lương cơ bản
        
        Args:
            leave_type: Loại nghỉ phép (sick, maternity)
            days: Số ngày nghỉ
            salary: Lương cơ bản, nếu không cung cấp sẽ lấy từ thông tin BHXH
            
        Returns:
            Số tiền trợ cấp BHXH, hoặc 0 nếu không có BHXH hoặc loại không hợp lệ
        """
        self.ensure_one()
        if not self.active_insurance_id:
            return 0
        
        insurance = self.active_insurance_id
        actual_salary = salary or insurance.basic_salary
        
        if not actual_salary:
            return 0
        
        if leave_type == 'sick':
            return insurance.calculate_sick_leave_allowance(days, actual_salary)
        elif leave_type == 'maternity':
            return insurance.calculate_maternity_leave_allowance(days, actual_salary)
        else:
            return 0
            
    def action_create_insurance(self):
        """Tạo mới thông tin BHXH cho nhân viên"""
        self.ensure_one()
        
        # Lấy thông tin lương từ hợp đồng hiện tại nếu có
        contract = self.env['hr.contract'].search([
            ('employee_id', '=', self.id),
            ('state', '=', 'open')
        ], limit=1)
        
        basic_salary = contract.wage if contract else 0
        
        # Tạo mới thông tin BHXH
        insurance = self.env['hr.employee.insurance'].create({
            'employee_id': self.id,
            'is_active': True,
            'basic_salary': basic_salary,
            'issue_date': fields.Date.today(),
        })
        
        # Mở form để người dùng nhập thêm thông tin
        return {
            'name': 'Thông tin BHXH',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.insurance',
            'res_id': insurance.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_insurance_detail(self):
        """Mở form chi tiết thông tin BHXH"""
        self.ensure_one()
        insurance_id = self.env.context.get('insurance_id')
        
        if not insurance_id:
            return
            
        return {
            'name': 'Thông tin BHXH',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.employee.insurance',
            'res_id': insurance_id,
            'view_mode': 'form',
            'target': 'current',
        } 