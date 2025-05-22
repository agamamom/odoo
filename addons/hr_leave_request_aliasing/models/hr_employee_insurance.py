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
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo import api, fields, models, _


class HrEmployeeInsurance(models.Model):
    """Model để quản lý thông tin BHXH của nhân viên"""
    _name = 'hr.employee.insurance'
    _description = 'Thông tin BHXH của nhân viên'
    _rec_name = 'employee_id'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True,
                                ondelete='cascade', index=True)
    insurance_number = fields.Char(string='Mã số BHXH', help='Mã số BHXH của nhân viên')
    issue_date = fields.Date(string='Ngày tham gia', help='Ngày bắt đầu tham gia BHXH')
    expiry_date = fields.Date(string='Ngày hết hạn', help='Ngày hết hạn thẻ BHXH (nếu có)')
    is_active = fields.Boolean(string='Đang hoạt động', default=True,
                             help='Trạng thái BHXH có đang hoạt động không')
    insurance_rate = fields.Float(string='Mức đóng BHXH', default=10.5,
                               help='Tỷ lệ % lương cơ bản đóng BHXH (phần người lao động)')
    company_insurance_rate = fields.Float(string='Mức đóng BHXH của công ty', default=17.5,
                                       help='Tỷ lệ % lương cơ bản công ty đóng BHXH')
    basic_salary = fields.Float(string='Lương cơ bản BHXH',
                             help='Mức lương cơ bản đóng BHXH')
    contribution_months = fields.Integer(string='Số tháng đã đóng',
                                      compute='_compute_contribution_months',
                                      store=True, readonly=True,
                                      help='Số tháng đã đóng BHXH')
    note = fields.Text(string='Ghi chú')
    attachment_ids = fields.Many2many('ir.attachment', 'insurance_attachment_rel',
                                   'insurance_id', 'attachment_id',
                                   string='Tài liệu đính kèm')
    sick_leave_coefficient = fields.Float(string='Hệ số trợ cấp ốm đau', default=0.75,
                                       help='Hệ số % lương cơ bản được hưởng khi nghỉ ốm theo BHXH')
    maternity_leave_coefficient = fields.Float(string='Hệ số trợ cấp thai sản', default=1.0,
                                            help='Hệ số % lương cơ bản được hưởng khi nghỉ thai sản theo BHXH')
    
    @api.depends('issue_date')
    def _compute_contribution_months(self):
        """Tính số tháng đã đóng BHXH dựa trên ngày tham gia"""
        for record in self:
            if record.issue_date:
                today = date.today()
                delta = relativedelta(today, record.issue_date)
                record.contribution_months = delta.years * 12 + delta.months
            else:
                record.contribution_months = 0
    
    def calculate_sick_leave_allowance(self, days, salary):
        """Tính trợ cấp ốm đau dựa trên số ngày nghỉ và lương cơ bản
        
        Theo quy định BHXH Việt Nam, người lao động được hưởng 75% mức lương
        đóng BHXH của tháng liền kề trước khi nghỉ việc hưởng BHXH
        """
        self.ensure_one()
        daily_salary = salary / 30  # Chia lương tháng cho 30 ngày
        return days * daily_salary * self.sick_leave_coefficient
    
    def calculate_maternity_leave_allowance(self, days, salary):
        """Tính trợ cấp thai sản dựa trên số ngày nghỉ và lương cơ bản
        
        Theo quy định BHXH Việt Nam, người lao động nữ được hưởng 100% mức lương
        đóng BHXH của tháng liền kề trước khi nghỉ thai sản, thời gian hưởng
        tối đa là 6 tháng
        """
        self.ensure_one()
        daily_salary = salary / 30  # Chia lương tháng cho 30 ngày
        max_days = 180  # 6 tháng x 30 ngày
        actual_days = min(days, max_days)
        return actual_days * daily_salary * self.maternity_leave_coefficient 