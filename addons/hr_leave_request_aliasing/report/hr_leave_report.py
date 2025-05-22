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
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT


class HrLeaveReport(models.AbstractModel):
    """Báo cáo nghỉ phép theo nhân viên, phòng ban hoặc công ty"""
    _name = 'report.hr_leave_request_aliasing.report_hr_leave'
    _description = 'Báo cáo nghỉ phép nhân viên'

    def _get_header_info(self, start_date, end_date):
        """Lấy thông tin header cho báo cáo"""
        return {
            'start_date': start_date.strftime('%d/%m/%Y'),
            'end_date': end_date.strftime('%d/%m/%Y'),
            'report_date': fields.Date.today().strftime('%d/%m/%Y'),
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

    def _get_leaves(self, start_date, end_date, department_id=False, employee_id=False):
        """Lấy thông tin các đơn nghỉ phép trong khoảng thời gian"""
        domain = [
            ('date_from', '>=', start_date),
            ('date_to', '<=', end_date),
            ('state', '=', 'validate'),
        ]
        
        if department_id:
            domain.append(('department_id', '=', department_id))
        if employee_id:
            domain.append(('employee_id', '=', employee_id))
            
        return self.env['hr.leave'].search(domain)

    def _get_employees(self, department_id=False):
        """Lấy danh sách nhân viên theo phòng ban nếu có"""
        domain = []
        if department_id:
            domain.append(('department_id', '=', department_id))
        return self.env['hr.employee'].search(domain)

    def _get_employee_leave_details(self, start_date, end_date, leaves, employees):
        """Tính toán chi tiết nghỉ phép cho từng nhân viên"""
        res = []
        leave_types = self.env['hr.leave.type'].search([])
        
        for employee in employees:
            row = {
                'employee': employee,
                'leaves': {},
                'total': 0.0,
            }
            
            # Khởi tạo dict cho từng loại nghỉ phép
            for leave_type in leave_types:
                row['leaves'][leave_type.id] = {
                    'name': leave_type.name,
                    'number_of_days': 0.0,
                    'is_insurance': False,
                }
            
            # Tính tổng số ngày nghỉ theo từng loại
            for leave in leaves.filtered(lambda l: l.employee_id.id == employee.id):
                leave_type_id = leave.holiday_status_id.id
                
                # Tính số ngày từ date_from và date_to
                days = self._calculate_days(leave.date_from, leave.date_to)
                
                row['leaves'][leave_type_id]['number_of_days'] += days
                row['leaves'][leave_type_id]['is_insurance'] = leave.is_insurance_eligible
                row['total'] += days
                
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
        
        leaves = self._get_leaves(start_date, end_date, department_id, employee_id)
        
        if employee_id:
            employees = self.env['hr.employee'].browse(employee_id)
        else:
            employees = self._get_employees(department_id)
            
        employee_leave_details = self._get_employee_leave_details(
            start_date, end_date, leaves, employees
        )
        
        # Lấy tất cả các loại nghỉ phép để hiển thị trên báo cáo
        leave_types = self.env['hr.leave.type'].search([])
        
        return {
            'doc_ids': docids,
            'doc_model': 'hr.leave',
            'docs': docs,
            'time': time,
            'get_header_info': self._get_header_info(start_date, end_date),
            'get_day': self._get_day,
            'employee_leave_details': employee_leave_details,
            'leave_types': leave_types,
        }


class HrLeaveReportWizard(models.TransientModel):
    """Wizard để tạo báo cáo nghỉ phép"""
    _name = 'hr.leave.report.wizard'
    _description = 'Wizard báo cáo nghỉ phép'

    date_from = fields.Date(string='Từ ngày', required=True, default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(string='Đến ngày', required=True, default=lambda self: fields.Date.today().replace(day=1) + relativedelta(months=1, days=-1))
    department_id = fields.Many2one('hr.department', string='Phòng ban')
    employee_id = fields.Many2one('hr.employee', string='Nhân viên')
    report_type = fields.Selection([
        ('pdf', 'PDF'),
        ('xlsx', 'Excel'),
    ], string='Loại báo cáo', default='pdf', required=True)

    @api.onchange('department_id')
    def onchange_department_id(self):
        """Xóa nhân viên đã chọn khi thay đổi phòng ban"""
        if self.department_id:
            self.employee_id = False
            return {'domain': {'employee_id': [('department_id', '=', self.department_id.id)]}}
        return {'domain': {'employee_id': []}}

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
            },
        }
        return self.env.ref('hr_leave_request_aliasing.action_report_hr_leave').report_action(self, data=data)

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
            },
        }
        return self.env.ref('hr_leave_request_aliasing.action_report_hr_leave_xlsx').report_action(self, data=data) 