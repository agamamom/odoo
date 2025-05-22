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
import time
from dateutil.relativedelta import relativedelta
from odoo import api, models, fields, _
from odoo.exceptions import UserError
from odoo.tools import float_round


class HrLeaveInsuranceReport(models.AbstractModel):
    """Báo cáo nghỉ phép hưởng BHXH"""
    _name = 'report.hr_leave_request_aliasing.report_hr_leave_insurance'
    _description = 'Báo cáo nghỉ phép hưởng BHXH'

    def _get_header_info(self, start_date, end_date, company_name):
        """Lấy thông tin header cho báo cáo"""
        return {
            'start_date': start_date.strftime('%d/%m/%Y'),
            'end_date': end_date.strftime('%d/%m/%Y'),
            'report_date': fields.Date.today().strftime('%d/%m/%Y'),
            'company_name': company_name,
        }

    def _get_day(self, date):
        """Hàm hỗ trợ định dạng ngày tháng"""
        return date.strftime('%d/%m/%Y')

    def _calculate_days(self, date_from, date_to):
        """Tính số ngày từ ngày bắt đầu đến ngày kết thúc"""
        if not date_from or not date_to:
            return 0.0
        delta = date_to - date_from
        return delta.days + (delta.seconds / (60 * 60 * 24))

    def _get_insurance_leaves(self, start_date, end_date, department_id=False, employee_id=False, insurance_type=False):
        """Lấy thông tin các đơn nghỉ phép hưởng BHXH trong khoảng thời gian"""
        domain = [
            ('date_from', '>=', start_date),
            ('date_to', '<=', end_date),
            ('state', '=', 'validate'),
            ('is_insurance_eligible', '=', True),
        ]
        
        if department_id:
            domain.append(('department_id', '=', department_id))
        if employee_id:
            domain.append(('employee_id', '=', employee_id))
        if insurance_type and insurance_type != 'all':
            domain.append(('insurance_type', '=', insurance_type))
            
        return self.env['hr.leave'].search(domain)

    def _get_employees_with_insurance(self, department_id=False):
        """Lấy danh sách nhân viên có BHXH theo phòng ban nếu có"""
        domain = [('has_insurance', '=', True)]
        if department_id:
            domain.append(('department_id', '=', department_id))
        return self.env['hr.employee'].search(domain)

    def _get_insurance_statistics(self, start_date, end_date, leaves, employees):
        """Tính toán thống kê BHXH cho từng nhân viên"""
        res = []
        
        for employee in employees:
            employee_leaves = leaves.filtered(lambda l: l.employee_id.id == employee.id)
            
            # Bỏ qua nhân viên không có đơn nghỉ phép hưởng BHXH
            if not employee_leaves:
                continue
                
            # Thống kê theo loại BHXH
            sick_leaves = employee_leaves.filtered(lambda l: l.insurance_type == 'sick')
            maternity_leaves = employee_leaves.filtered(lambda l: l.insurance_type == 'maternity')
            
            # Tính tổng ngày và trợ cấp
            total_sick_days = sum(self._calculate_days(leave.date_from, leave.date_to) for leave in sick_leaves)
            total_maternity_days = sum(self._calculate_days(leave.date_from, leave.date_to) for leave in maternity_leaves)
            total_sick_allowance = sum(sick_leaves.mapped('insurance_allowance'))
            total_maternity_allowance = sum(maternity_leaves.mapped('insurance_allowance'))
            
            # Lấy thông tin BHXH
            insurance = employee.active_insurance_id
            
            row = {
                'employee': employee,
                'department': employee.department_id and employee.department_id.name or '',
                'job': employee.job_id and employee.job_id.name or '',
                'insurance_number': employee.insurance_number or '',
                'basic_salary': insurance and insurance.basic_salary or 0.0,
                'sick_days': total_sick_days,
                'sick_allowance': total_sick_allowance,
                'maternity_days': total_maternity_days,
                'maternity_allowance': total_maternity_allowance,
                'total_days': total_sick_days + total_maternity_days,
                'total_allowance': total_sick_allowance + total_maternity_allowance,
                'leaves': employee_leaves,
            }
                
            res.append(row)
            
        return res

    @api.model
    def _get_report_values(self, docids, data=None):
        """Chuẩn bị dữ liệu cho báo cáo"""
        if not data.get('form'):
            raise UserError(_("Vui lòng nhập thông tin để tạo báo cáo"))
            
        docs = []
        start_date = fields.Date.from_string(data['form']['date_from'])
        end_date = fields.Date.from_string(data['form']['date_to'])
        department_id = data['form'].get('department_id', False)
        employee_id = data['form'].get('employee_id', False)
        insurance_type = data['form'].get('insurance_type', 'all')
        company_name = self.env.company.name
        
        leaves = self._get_insurance_leaves(
            start_date, end_date, department_id, employee_id, insurance_type
        )
        
        if employee_id:
            employees = self.env['hr.employee'].browse(employee_id)
        else:
            employees = self._get_employees_with_insurance(department_id)
            
        insurance_statistics = self._get_insurance_statistics(
            start_date, end_date, leaves, employees
        )
        
        # Tính tổng cộng
        total_sick_days = sum(item['sick_days'] for item in insurance_statistics)
        total_maternity_days = sum(item['maternity_days'] for item in insurance_statistics)
        total_sick_allowance = sum(item['sick_allowance'] for item in insurance_statistics)
        total_maternity_allowance = sum(item['maternity_allowance'] for item in insurance_statistics)

        return {
            'doc_ids': docids,
            'doc_model': 'hr.leave',
            'docs': docs,
            'time': time,
            'get_header_info': self._get_header_info(start_date, end_date, company_name),
            'get_day': self._get_day,
            'insurance_statistics': insurance_statistics,
            'insurance_type': dict(self.env['hr.leave']._fields['insurance_type'].selection).get(insurance_type, 'Tất cả') if insurance_type != 'all' else 'Tất cả',
            'float_round': float_round,
            'total_sick_days': total_sick_days,
            'total_maternity_days': total_maternity_days,
            'total_sick_allowance': total_sick_allowance,
            'total_maternity_allowance': total_maternity_allowance,
            'total_days': total_sick_days + total_maternity_days,
            'total_allowance': total_sick_allowance + total_maternity_allowance,
        }


class HrLeaveInsuranceReportWizard(models.TransientModel):
    """Wizard để tạo báo cáo nghỉ phép hưởng BHXH"""
    _name = 'hr.leave.insurance.report.wizard'
    _description = 'Wizard báo cáo nghỉ phép hưởng BHXH'

    date_from = fields.Date(string='Từ ngày', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Đến ngày', required=True, default=lambda self: fields.Date.today().replace(day=1) + relativedelta(months=1, days=-1))
    department_id = fields.Many2one('hr.department', string='Phòng ban')
    employee_id = fields.Many2one('hr.employee', string='Nhân viên')
    insurance_type = fields.Selection([
        ('all', 'Tất cả'),
        ('sick', 'Ốm đau'),
        ('maternity', 'Thai sản')
    ], string='Loại BHXH', default='all', required=True)
    report_type = fields.Selection([
        ('pdf', 'PDF'),
        ('xlsx', 'Excel'),
    ], string='Loại báo cáo', default='pdf', required=True)

    @api.onchange('department_id')
    def onchange_department_id(self):
        """Xóa nhân viên đã chọn khi thay đổi phòng ban"""
        if self.department_id:
            self.employee_id = False
            return {'domain': {'employee_id': [('department_id', '=', self.department_id.id), ('has_insurance', '=', True)]}}
        return {'domain': {'employee_id': [('has_insurance', '=', True)]}}

    def action_print_report(self):
        """In báo cáo theo loại đã chọn"""
        self.ensure_one()
        
        if self.report_type == 'pdf':
            return self._print_pdf_report()
        else:
            return self._print_xlsx_report()
            
    def _print_pdf_report(self):
        """In báo cáo dạng PDF"""
        data = {
            'ids': self.ids,
            'model': self._name,
            'form': {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'department_id': self.department_id.id if self.department_id else False,
                'employee_id': self.employee_id.id if self.employee_id else False,
                'insurance_type': self.insurance_type,
            },
        }
        return self.env.ref('hr_leave_request_aliasing.action_report_hr_leave_insurance').report_action(self, data=data)

    def _print_xlsx_report(self):
        """In báo cáo dạng Excel"""
        data = {
            'ids': self.ids,
            'model': self._name,
            'form': {
                'date_from': self.date_from,
                'date_to': self.date_to,
                'department_id': self.department_id.id if self.department_id else False,
                'employee_id': self.employee_id.id if self.employee_id else False,
                'insurance_type': self.insurance_type,
            },
        }
        return self.env.ref('hr_leave_request_aliasing.action_report_hr_leave_insurance_xlsx').report_action(self, data=data) 