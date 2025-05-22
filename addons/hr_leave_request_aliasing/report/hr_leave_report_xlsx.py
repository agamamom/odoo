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
import base64
import io
from odoo import models, fields, _
from odoo.tools import float_round

try:
    import xlsxwriter
except ImportError:
    # xlsxwriter là thư viện cần thiết để xuất file Excel
    xlsxwriter = None


class HrLeaveReportXlsx(models.AbstractModel):
    """Class xử lý xuất Excel cho báo cáo nghỉ phép"""
    _name = 'report.hr_leave_request_aliasing.report_hr_leave_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Báo cáo nghỉ phép Excel'

    def _calculate_days(self, date_from, date_to):
        """Tính số ngày từ ngày bắt đầu đến ngày kết thúc"""
        if not date_from or not date_to:
            return 0.0
        delta = date_to - date_from
        return delta.days + (delta.seconds / (60 * 60 * 24))

    def generate_xlsx_report(self, workbook, data, objs):
        """Tạo file Excel cho báo cáo nghỉ phép"""
        # Lấy dữ liệu từ form
        form_data = data['form']
        start_date = fields.Date.from_string(form_data['date_from'])
        end_date = fields.Date.from_string(form_data['date_to'])
        department_id = form_data.get('department_id', False)
        employee_id = form_data.get('employee_id', False)
        
        # Tạo worksheet
        sheet = workbook.add_worksheet(_('Báo cáo nghỉ phép'))
        
        # Định dạng
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 12,
            'bg_color': '#D3D3D3',
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 16,
        })
        
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
        })
        
        number_format = workbook.add_format({
            'num_format': '#,##0.00',
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
        })
        
        cell_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
        })
        
        total_format = workbook.add_format({
            'bold': True,
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00',
            'bg_color': '#F2F2F2',
        })
        
        # Tiêu đề báo cáo
        sheet.merge_range('A1:I1', _('BÁO CÁO NGHỈ PHÉP NHÂN VIÊN'), title_format)
        
        # Thông tin thời gian
        sheet.merge_range('A2:B2', _('Từ ngày:'), cell_format)
        sheet.merge_range('C2:D2', start_date, date_format)
        sheet.merge_range('E2:F2', _('Đến ngày:'), cell_format)
        sheet.merge_range('G2:H2', end_date, date_format)
        
        # Tiêu đề cột
        headers = [
            _('STT'),
            _('Mã NV'),
            _('Họ và tên'),
            _('Phòng ban'),
            _('Vị trí'),
            _('Loại nghỉ phép'),
            _('Số ngày'),
            _('Ngày bắt đầu'),
            _('Ngày kết thúc'),
        ]
        
        for col_num, header in enumerate(headers):
            sheet.write(4, col_num, header, header_format)
            
        # Thiết lập độ rộng cột
        sheet.set_column('A:A', 5)
        sheet.set_column('B:B', 10)
        sheet.set_column('C:C', 25)
        sheet.set_column('D:D', 20)
        sheet.set_column('E:E', 20)
        sheet.set_column('F:F', 20)
        sheet.set_column('G:G', 10)
        sheet.set_column('H:H', 15)
        sheet.set_column('I:I', 15)
        
        # Lấy dữ liệu báo cáo
        report_model = self.env['report.hr_leave_request_aliasing.report_hr_leave']
        
        # Chuẩn bị dữ liệu
        leaves = report_model._get_leaves(start_date, end_date, department_id, employee_id)
        if employee_id:
            employees = self.env['hr.employee'].browse(employee_id)
        else:
            employees = report_model._get_employees(department_id)
        
        # Điền dữ liệu vào bảng
        row = 5
        seq = 1
        total_days = 0
        
        for employee in employees:
            employee_leaves = leaves.filtered(lambda l: l.employee_id.id == employee.id)
            
            if not employee_leaves:
                continue
                
            for leave in employee_leaves:
                # Tính số ngày từ date_from và date_to
                days = self._calculate_days(leave.date_from, leave.date_to)
                
                sheet.write(row, 0, seq, cell_format)
                sheet.write(row, 1, employee.barcode or '', cell_format)
                sheet.write(row, 2, employee.name, cell_format)
                sheet.write(row, 3, employee.department_id.name if employee.department_id else '', cell_format)
                sheet.write(row, 4, employee.job_id.name if employee.job_id else '', cell_format)
                sheet.write(row, 5, leave.holiday_status_id.name, cell_format)
                sheet.write(row, 6, days, number_format)
                sheet.write(row, 7, leave.date_from.date(), date_format)
                sheet.write(row, 8, leave.date_to.date(), date_format)
                
                row += 1
                seq += 1
                total_days += days
        
        # Tổng kết
        sheet.merge_range(f'A{row+1}:F{row+1}', _('Tổng số ngày nghỉ:'), total_format)
        sheet.write(row, 6, total_days, total_format)


class HrLeaveInsuranceReportXlsx(models.AbstractModel):
    """Class xử lý xuất Excel cho báo cáo BHXH"""
    _name = 'report.hr_leave_request_aliasing.report_hr_leave_insurance_xlsx'
    _inherit = 'report.report_xlsx.abstract'
    _description = 'Báo cáo BHXH Excel'
    
    def _calculate_days(self, date_from, date_to):
        """Tính số ngày từ ngày bắt đầu đến ngày kết thúc"""
        if not date_from or not date_to:
            return 0.0
        delta = date_to - date_from
        return delta.days + (delta.seconds / (60 * 60 * 24))

    def generate_xlsx_report(self, workbook, data, objs):
        """Tạo file Excel cho báo cáo BHXH"""
        # Lấy dữ liệu từ form
        form_data = data['form']
        start_date = fields.Date.from_string(form_data['date_from'])
        end_date = fields.Date.from_string(form_data['date_to'])
        department_id = form_data.get('department_id', False)
        employee_id = form_data.get('employee_id', False)
        insurance_type = form_data.get('insurance_type', 'all')
        company_name = self.env.company.name
        
        # Dictionary chuyển đổi loại BHXH
        insurance_type_dict = {
            'all': 'Tất cả',
            'sick': 'Ốm đau',
            'maternity': 'Thai sản'
        }
        
        # Tạo worksheet
        sheet = workbook.add_worksheet(_('Báo cáo BHXH'))
        
        # Định dạng
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 12,
            'bg_color': '#D3D3D3',
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 16,
        })
        
        subtitle_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 12,
        })
        
        date_format = workbook.add_format({
            'num_format': 'dd/mm/yyyy',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
        })
        
        number_format = workbook.add_format({
            'num_format': '#,##0.00',
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
        })
        
        cell_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1,
        })
        
        total_format = workbook.add_format({
            'bold': True,
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'num_format': '#,##0.00',
            'bg_color': '#F2F2F2',
        })
        
        # Tiêu đề báo cáo
        sheet.merge_range('A1:J1', _('BÁO CÁO CHẾ ĐỘ BHXH'), title_format)
        sheet.merge_range('A2:J2', company_name, subtitle_format)
        
        # Thông tin thời gian
        sheet.merge_range('A3:B3', _('Từ ngày:'), cell_format)
        sheet.merge_range('C3:D3', start_date, date_format)
        sheet.merge_range('E3:F3', _('Đến ngày:'), cell_format)
        sheet.merge_range('G3:H3', end_date, date_format)
        sheet.merge_range('I3:I3', _('Loại BHXH:'), cell_format)
        sheet.merge_range('J3:J3', insurance_type_dict.get(insurance_type, 'Tất cả'), cell_format)
        
        # Tiêu đề cột
        headers = [
            _('STT'),
            _('Mã NV'),
            _('Mã BHXH'),
            _('Họ và tên'),
            _('Phòng ban'),
            _('Vị trí'),
            _('Số ngày nghỉ ốm'),
            _('Trợ cấp ốm đau'),
            _('Số ngày nghỉ thai sản'),
            _('Trợ cấp thai sản'),
        ]
        
        for col_num, header in enumerate(headers):
            sheet.write(5, col_num, header, header_format)
            
        # Thiết lập độ rộng cột
        sheet.set_column('A:A', 5)
        sheet.set_column('B:B', 10)
        sheet.set_column('C:C', 15)
        sheet.set_column('D:D', 25)
        sheet.set_column('E:E', 20)
        sheet.set_column('F:F', 20)
        sheet.set_column('G:G', 15)
        sheet.set_column('H:H', 15)
        sheet.set_column('I:I', 15)
        sheet.set_column('J:J', 15)
        
        # Lấy dữ liệu báo cáo
        report_model = self.env['report.hr_leave_request_aliasing.report_hr_leave_insurance']
        
        # Chuẩn bị dữ liệu
        leaves = report_model._get_insurance_leaves(
            start_date, end_date, department_id, employee_id, insurance_type
        )
        
        if employee_id:
            employees = self.env['hr.employee'].browse(employee_id)
        else:
            employees = report_model._get_employees_with_insurance(department_id)
        
        # Điền dữ liệu vào bảng
        row = 6
        seq = 1
        total_sick_days = 0
        total_maternity_days = 0
        total_sick_allowance = 0
        total_maternity_allowance = 0
        
        for employee in employees:
            employee_leaves = leaves.filtered(lambda l: l.employee_id.id == employee.id)
            
            if not employee_leaves:
                continue
                
            # Thống kê theo loại BHXH
            sick_leaves = employee_leaves.filtered(lambda l: l.insurance_type == 'sick')
            maternity_leaves = employee_leaves.filtered(lambda l: l.insurance_type == 'maternity')
            
            # Tính tổng ngày và trợ cấp
            sick_days = sum(self._calculate_days(leave.date_from, leave.date_to) for leave in sick_leaves)
            maternity_days = sum(self._calculate_days(leave.date_from, leave.date_to) for leave in maternity_leaves)
            sick_allowance = sum(sick_leaves.mapped('insurance_allowance'))
            maternity_allowance = sum(maternity_leaves.mapped('insurance_allowance'))
            
            sheet.write(row, 0, seq, cell_format)
            sheet.write(row, 1, employee.barcode or '', cell_format)
            sheet.write(row, 2, employee.insurance_number or '', cell_format)
            sheet.write(row, 3, employee.name, cell_format)
            sheet.write(row, 4, employee.department_id.name if employee.department_id else '', cell_format)
            sheet.write(row, 5, employee.job_id.name if employee.job_id else '', cell_format)
            sheet.write(row, 6, sick_days, number_format)
            sheet.write(row, 7, sick_allowance, number_format)
            sheet.write(row, 8, maternity_days, number_format)
            sheet.write(row, 9, maternity_allowance, number_format)
            
            row += 1
            seq += 1
            total_sick_days += sick_days
            total_maternity_days += maternity_days
            total_sick_allowance += sick_allowance
            total_maternity_allowance += maternity_allowance
        
        # Tổng kết
        sheet.merge_range(f'A{row+1}:F{row+1}', _('Tổng cộng:'), total_format)
        sheet.write(row, 6, total_sick_days, total_format)
        sheet.write(row, 7, total_sick_allowance, total_format)
        sheet.write(row, 8, total_maternity_days, total_format)
        sheet.write(row, 9, total_maternity_allowance, total_format) 