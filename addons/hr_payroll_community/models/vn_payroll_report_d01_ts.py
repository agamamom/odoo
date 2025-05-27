# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
import base64
import io
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import calendar
import xlsxwriter
import json
import re

_logger = logging.getLogger(__name__)

class VNPayrollReportD01TS(models.Model):
    _name = 'vn.payroll.report.d01.ts'
    _description = 'Vietnam Social Insurance Report D01-TS'
    _order = 'create_date desc'
    
    name = fields.Char(string='Report Name', required=True, default="Báo cáo BHXH D01-TS")
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    date_from = fields.Date(string='From Date', required=True, default=lambda self: date(date.today().year, date.today().month, 1))
    date_to = fields.Date(string='To Date', required=True, default=lambda self: date(date.today().year, date.today().month, calendar.monthrange(date.today().year, date.today().month)[1]))
    
    department_id = fields.Many2one('hr.department', string='Department')
    employee_ids = fields.Many2many('hr.employee', string='Employees')
    is_all_employees = fields.Boolean('All Employees', default=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('error', 'Error')
    ], string='Status', default='draft')
    
    generated_file = fields.Binary(string='Generated File')
    file_name = fields.Char(string='File Name')
    error_message = fields.Text(string='Error Message')
    
    # Thông tin người lập và ký báo cáo
    reporter_name = fields.Char(string='Reporter Name', default=lambda self: self.env.user.name)
    reporter_position = fields.Char(string='Reporter Position', default='HR Manager')
    signer_name = fields.Char(string='Signer Name')
    signer_position = fields.Char(string='Signer Position', default='CEO')
    report_date = fields.Date(string='Report Date', default=fields.Date.today)
    
    # Thông tin cho báo cáo BHXH
    organization_code = fields.Char(string='Mã đơn vị', help='Mã số đơn vị tham gia BHXH')
    organization_name = fields.Char(string='Tên đơn vị', default=lambda self: self.env.company.name)
    organization_address = fields.Char(string='Địa chỉ', default=lambda self: self.env.company.street)
    organization_phone = fields.Char(string='Số điện thoại', default=lambda self: self.env.company.phone)
    organization_email = fields.Char(string='Email', default=lambda self: self.env.company.email)
    
    # Thông tin nộp BHXH
    payment_method = fields.Selection([
        ('bank', 'Chuyển khoản'),
        ('cash', 'Tiền mặt')
    ], string='Phương thức đóng', default='bank')
    bank_account = fields.Char(string='Số tài khoản')
    bank_name = fields.Char(string='Tại ngân hàng')
    
    def action_generate_report(self):
        """Generate the D01-TS report"""
        self.ensure_one()
        
        if not self.is_all_employees and not self.employee_ids:
            raise UserError(_("Bạn phải chọn ít nhất một nhân viên hoặc chọn 'Tất cả nhân viên'."))
        
        # Reset previous results
        self.write({
            'generated_file': False,
            'file_name': False,
            'error_message': False,
            'state': 'draft'
        })
        
        try:
            result = self._generate_d01_ts_report()
            
            # Update with the generated file
            if result and 'file' in result:
                file_name = result.get('file_name', f"D01-TS_{self.date_from}_{self.date_to}.xlsx")
                self.write({
                    'generated_file': result['file'],
                    'file_name': file_name,
                    'state': 'generated'
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Báo cáo đã được tạo thành công.'),
                        'sticky': False,
                        'type': 'success',
                    }
                }
            else:
                self.write({
                    'error_message': _("Không tìm thấy dữ liệu hoặc có lỗi xảy ra."),
                    'state': 'error'
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Warning'),
                        'message': _('Không tìm thấy dữ liệu hoặc có lỗi xảy ra.'),
                        'sticky': False,
                        'type': 'warning',
                    }
                }
                
        except Exception as e:
            self.write({
                'error_message': str(e),
                'state': 'error'
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': str(e),
                    'sticky': False,
                    'type': 'danger',
                }
            }
    
    def action_download_report(self):
        """Download the generated report"""
        self.ensure_one()
        
        if not self.generated_file:
            raise UserError(_("Chưa có báo cáo nào được tạo. Vui lòng tạo báo cáo trước."))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=vn.payroll.report.d01.ts&id={self.id}&field=generated_file&filename={self.file_name}&download=true',
            'target': 'self',
        }
    
    def _get_employee_domain(self):
        """Return domain to filter employees"""
        domain = [('contract_id.state', '=', 'open')]
        
        if not self.is_all_employees and self.employee_ids:
            domain.append(('id', 'in', self.employee_ids.ids))
        
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        
        return domain

    def _get_employees(self):
        """Get employees based on selection criteria"""
        domain = self._get_employee_domain()
        return self.env['hr.employee'].search(domain)
    
    def _get_payslips(self, employees=None):
        """Get payslips for the report period and employees"""
        domain = [
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', 'in', ['done', 'paid'])
        ]
        
        if employees:
            domain.append(('employee_id', 'in', employees.ids))
        elif not self.is_all_employees and self.employee_ids:
            domain.append(('employee_id', 'in', self.employee_ids.ids))
        
        return self.env['hr.payslip'].search(domain)
    
    def _generate_d01_ts_report(self):
        """Generate Excel report for D01-TS form"""
        employees = self._get_employees()
        
        if not employees:
            raise UserError(_("Không tìm thấy nhân viên nào phù hợp với tiêu chí tìm kiếm."))
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Define styles
        title_style = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })
        header_style = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'bg_color': '#D3D3D3'
        })
        date_style = workbook.add_format({
            'num_format': 'dd/mm/yyyy',
            'border': 1
        })
        number_style = workbook.add_format({
            'num_format': '#,##0',
            'border': 1
        })
        text_style = workbook.add_format({
            'align': 'left',
            'border': 1
        })
        text_center_style = workbook.add_format({
            'align': 'center',
            'border': 1
        })
        
        # Create worksheet
        sheet = workbook.add_worksheet('D01-TS')
        sheet.set_column(0, 0, 5)  # STT
        sheet.set_column(1, 1, 20)  # Họ và tên
        sheet.set_column(2, 2, 15)  # Mã số BHXH
        sheet.set_column(3, 3, 12)  # Ngày sinh
        sheet.set_column(4, 4, 6)   # Giới tính
        sheet.set_column(5, 5, 15)  # Số CMND/CCCD
        sheet.set_column(6, 6, 12)  # Ngày cấp
        sheet.set_column(7, 7, 20)  # Nơi cấp
        sheet.set_column(8, 8, 30)  # Địa chỉ
        sheet.set_column(9, 9, 15)  # Chức vụ
        sheet.set_column(10, 10, 15)  # Mức lương
        sheet.set_column(11, 11, 15)  # Phụ cấp
        sheet.set_column(12, 12, 15)  # Ngày tham gia
        sheet.set_column(13, 13, 15)  # Ghi chú
        
        # Title
        sheet.merge_range('A1:N1', 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', title_style)
        sheet.merge_range('A2:N2', 'Độc lập - Tự do - Hạnh phúc', title_style)
        sheet.merge_range('A4:N4', 'DANH SÁCH LAO ĐỘNG THAM GIA BẢO HIỂM XÃ HỘI, BẢO HIỂM Y TẾ', title_style)
        sheet.merge_range('A5:N5', 'Mẫu D01-TS', workbook.add_format({'align': 'center'}))
        
        # Company info
        sheet.merge_range('A7:C7', 'Tên đơn vị:', workbook.add_format({'bold': True}))
        sheet.merge_range('D7:N7', self.organization_name or self.company_id.name)
        sheet.merge_range('A8:C8', 'Mã số đơn vị:', workbook.add_format({'bold': True}))
        sheet.merge_range('D8:N8', self.organization_code or '')
        sheet.merge_range('A9:C9', 'Địa chỉ:', workbook.add_format({'bold': True}))
        sheet.merge_range('D9:N9', self.organization_address or self.company_id.street or '')
        sheet.merge_range('A10:C10', 'Điện thoại:', workbook.add_format({'bold': True}))
        sheet.merge_range('D10:F10', self.organization_phone or self.company_id.phone or '')
        sheet.merge_range('G10:I10', 'Email:', workbook.add_format({'bold': True}))
        sheet.merge_range('J10:N10', self.organization_email or self.company_id.email or '')
        
        # Headers
        headers = [
            'STT', 'Họ và tên', 'Mã số BHXH', 'Ngày sinh', 'Giới tính', 'Số CMND/CCCD', 
            'Ngày cấp', 'Nơi cấp', 'Địa chỉ', 'Chức vụ', 'Mức lương', 'Phụ cấp', 
            'Ngày tham gia', 'Ghi chú'
        ]
        
        for col, header in enumerate(headers):
            sheet.write(11, col, header, header_style)
        
        # Data
        row = 12
        for idx, employee in enumerate(employees, 1):
            contract = employee.contract_id
            
            sheet.write(row, 0, idx, text_center_style)  # STT
            sheet.write(row, 1, employee.name, text_style)  # Họ và tên
            sheet.write(row, 2, employee.social_insurance or '', text_style)  # Mã số BHXH
            sheet.write(row, 3, employee.birthday or '', date_style)  # Ngày sinh
            sheet.write(row, 4, 'Nam' if employee.gender == 'male' else 'Nữ', text_center_style)  # Giới tính
            sheet.write(row, 5, employee.identification_id or '', text_style)  # Số CMND/CCCD
            sheet.write(row, 6, employee.identification_issue_date or '', date_style)  # Ngày cấp
            sheet.write(row, 7, employee.identification_place or '', text_style)  # Nơi cấp
            sheet.write(row, 8, employee.address_home_id.name or '', text_style)  # Địa chỉ
            sheet.write(row, 9, employee.job_title or '', text_style)  # Chức vụ
            
            # Lương và phụ cấp
            wage = contract.wage if contract else 0
            allowances = sum(contract.mapped('allowance_ids.amount')) if contract and hasattr(contract, 'allowance_ids') else 0
            
            sheet.write(row, 10, wage, number_style)  # Mức lương
            sheet.write(row, 11, allowances, number_style)  # Phụ cấp
            sheet.write(row, 12, contract.date_start if contract else '', date_style)  # Ngày tham gia
            sheet.write(row, 13, '', text_style)  # Ghi chú
            
            row += 1
        
        # Signature
        row += 2
        current_date = fields.Date.today()
        date_string = f"Ngày {current_date.day} tháng {current_date.month} năm {current_date.year}"
        
        sheet.merge_range(f'A{row}:G{row}', '', workbook.add_format({'align': 'center'}))
        sheet.merge_range(f'H{row}:N{row}', date_string, workbook.add_format({'align': 'center'}))
        
        row += 1
        sheet.merge_range(f'A{row}:G{row}', 'Người lập biểu', workbook.add_format({'align': 'center', 'bold': True}))
        sheet.merge_range(f'H{row}:N{row}', 'Thủ trưởng đơn vị', workbook.add_format({'align': 'center', 'bold': True}))
        
        row += 1
        sheet.merge_range(f'A{row}:G{row}', '(Ký, ghi rõ họ tên)', workbook.add_format({'align': 'center', 'italic': True}))
        sheet.merge_range(f'H{row}:N{row}', '(Ký, đóng dấu)', workbook.add_format({'align': 'center', 'italic': True}))
        
        row += 5
        sheet.merge_range(f'A{row}:G{row}', self.reporter_name or '', workbook.add_format({'align': 'center', 'bold': True}))
        sheet.merge_range(f'H{row}:N{row}', self.signer_name or '', workbook.add_format({'align': 'center', 'bold': True}))
        
        # Finalize
        workbook.close()
        output.seek(0)
        
        return {
            'file': base64.b64encode(output.read()),
            'file_name': f"D01-TS_{self.date_from.strftime('%d%m%Y')}_{self.date_to.strftime('%d%m%Y')}.xlsx"
        } 