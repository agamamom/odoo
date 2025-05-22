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
from odoo import api, fields, models, _


class HrPayslip(models.Model):
    """Mở rộng model hr.payslip để tích hợp với thông tin trợ cấp BHXH"""
    _inherit = 'hr.payslip'

    total_insurance_allowance = fields.Float(
        string='Tổng trợ cấp BHXH',
        compute='_compute_insurance_allowance',
        store=True,
        help='Tổng số tiền trợ cấp BHXH trong kỳ lương'
    )
    
    sick_leave_insurance = fields.Float(
        string='Trợ cấp ốm đau',
        compute='_compute_insurance_allowance',
        store=True,
        help='Tổng số tiền trợ cấp ốm đau BHXH trong kỳ lương'
    )
    
    maternity_leave_insurance = fields.Float(
        string='Trợ cấp thai sản',
        compute='_compute_insurance_allowance',
        store=True,
        help='Tổng số tiền trợ cấp thai sản BHXH trong kỳ lương'
    )
    
    total_salary_deduction = fields.Float(
        string='Tổng khấu trừ lương do nghỉ phép',
        compute='_compute_insurance_allowance',
        store=True,
        help='Tổng số tiền khấu trừ từ lương cơ bản do nghỉ phép có BHXH'
    )
    
    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_insurance_allowance(self):
        """Tính toán các khoản trợ cấp BHXH và khấu trừ lương trong kỳ lương"""
        for payslip in self:
            if not payslip.employee_id or not payslip.date_from or not payslip.date_to:
                payslip.total_insurance_allowance = 0
                payslip.sick_leave_insurance = 0
                payslip.maternity_leave_insurance = 0
                payslip.total_salary_deduction = 0
                continue
            
            # Tìm các đơn nghỉ phép được phê duyệt trong kỳ lương hiện tại
            leaves = self.env['hr.leave'].search([
                ('employee_id', '=', payslip.employee_id.id),
                ('state', '=', 'validate'),
                ('is_insurance_eligible', '=', True),
                '|', '&',
                ('date_from', '>=', payslip.date_from),
                ('date_from', '<=', payslip.date_to),
                '&',
                ('date_to', '>=', payslip.date_from),
                ('date_to', '<=', payslip.date_to)
            ])
            
            # Tính tổng các khoản trợ cấp BHXH
            sick_leave_amount = sum(leaves.filtered(lambda l: l.insurance_type == 'sick').mapped('insurance_allowance'))
            maternity_leave_amount = sum(leaves.filtered(lambda l: l.insurance_type == 'maternity').mapped('insurance_allowance'))
            total_deduction = sum(leaves.mapped('salary_deduction'))
            
            payslip.sick_leave_insurance = sick_leave_amount
            payslip.maternity_leave_insurance = maternity_leave_amount
            payslip.total_insurance_allowance = sick_leave_amount + maternity_leave_amount
            payslip.total_salary_deduction = total_deduction
    
    def _get_line_values(self, code_list, vals_list=None):
        """Override để thêm các giá trị trợ cấp BHXH vào danh sách giá trị cho các mã lương"""
        res = super(HrPayslip, self)._get_line_values(code_list, vals_list)
        for payslip in self:
            for code in code_list:
                if code == 'SICK_ALLOW' and code in res:
                    res[code][payslip.id]['amount'] = payslip.sick_leave_insurance
                elif code == 'MAT_ALLOW' and code in res:
                    res[code][payslip.id]['amount'] = payslip.maternity_leave_insurance
                elif code == 'INS_ALLOW' and code in res:
                    res[code][payslip.id]['amount'] = payslip.total_insurance_allowance
                elif code == 'LEAVE_DED' and code in res:
                    res[code][payslip.id]['amount'] = payslip.total_salary_deduction
        return res
    
    def action_compute_insurance_allowance(self):
        """Hành động để tính toán lại các khoản trợ cấp BHXH"""
        for payslip in self:
            payslip._compute_insurance_allowance()
        return True 