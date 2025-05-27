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

class VNPayrollReport(models.Model):
    _name = 'vn.payroll.report'
    _description = 'Vietnam Payroll Report Generator'
    _order = 'create_date desc'
    
    name = fields.Char(string='Report Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    date_from = fields.Date(string='From Date', required=True, default=lambda self: date(date.today().year, date.today().month, 1))
    date_to = fields.Date(string='To Date', required=True, default=lambda self: date(date.today().year, date.today().month, calendar.monthrange(date.today().year, date.today().month)[1]))
    report_type = fields.Selection([
        ('01_bhxh', 'BHXH 01 - Đăng ký tham gia BHXH, BHYT, BHTN'),
        ('02_bhxh', 'BHXH 02 - Thay đổi thông tin BHXH, BHYT, BHTN'),
        ('03_bhxh', 'BHXH 03 - Báo cáo tình hình sử dụng lao động'),
        ('thu_nhap', 'Bảng Tổng hợp Thu nhập'),
        ('phu_cap', 'Bảng Tổng hợp Phụ cấp'),
        ('luong_mem', 'Bảng Tổng hợp Lương mềm'),
        ('thue_tncn', 'Bảng kê Thuế TNCN'),
        ('thue_xml', 'Báo cáo Thuế TNCN XML'),
        ('05_bhxh', 'BHXH 05 - Tổng hợp tiền lương BHXH')
    ], string='Report Type', required=True, default='thu_nhap')
    
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
    bhxh_company_code = fields.Char(string='BHXH Company Code')
    bhxh_unit_code = fields.Char(string='BHXH Unit Code')
    bhxh_province_code = fields.Char(string='BHXH Province Code')
    
    def action_generate_report(self):
        """Generate the selected report"""
        self.ensure_one()
        
        if not self.is_all_employees and not self.employee_ids:
            raise UserError(_("You must select at least one employee or check 'All Employees'."))
        
        # Reset previous results
        self.write({
            'generated_file': False,
            'file_name': False,
            'error_message': False,
            'state': 'draft'
        })
        
        try:
            # BHXH Reports
            if self.report_type == '01_bhxh':
                result = self._generate_bhxh_01_report()
            elif self.report_type == '02_bhxh':
                result = self._generate_bhxh_02_report()
            elif self.report_type == '03_bhxh':
                result = self._generate_bhxh_03_report()
            elif self.report_type == '05_bhxh':
                result = self._generate_bhxh_05_report()
            # Salary Reports
            elif self.report_type == 'thu_nhap':
                result = self._generate_income_summary_report()
            elif self.report_type == 'phu_cap':
                result = self._generate_allowance_report()
            elif self.report_type == 'luong_mem':
                result = self._generate_variable_salary_report()
            # Tax Reports
            elif self.report_type == 'thue_tncn':
                result = self._generate_pit_report()
            elif self.report_type == 'thue_xml':
                result = self._generate_pit_xml_report()
            else:
                raise UserError(_("Report type not yet implemented."))
            
            # Update with the generated file
            if result and 'file' in result:
                file_name = result.get('file_name', f"{self.report_type}_{self.date_from}_{self.date_to}.xlsx")
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
                        'message': _('Report has been generated successfully.'),
                        'sticky': False,
                        'type': 'success',
                    }
                }
            else:
                self.write({
                    'error_message': _("No data found or error occurred."),
                    'state': 'error'
                })
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Warning'),
                        'message': _('No data found or error occurred.'),
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
            raise UserError(_("No report file has been generated. Please generate the report first."))
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=vn.payroll.report&id={self.id}&field=generated_file&filename={self.file_name}&download=true',
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
    
    def _prepare_workbook(self):
        """Create and prepare Excel workbook for reports"""
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Define common styles
        styles = {
            'title': workbook.add_format({
                'bold': True, 
                'font_size': 16, 
                'align': 'center', 
                'valign': 'vcenter'
            }),
            'header': workbook.add_format({
                'bold': True, 
                'font_size': 11, 
                'align': 'center', 
                'valign': 'vcenter', 
                'border': 1,
                'bg_color': '#D3D3D3'
            }),
            'date': workbook.add_format({
                'num_format': 'dd/mm/yyyy'
            }),
            'number': workbook.add_format({
                'num_format': '#,##0'
            }),
            'number_bold': workbook.add_format({
                'num_format': '#,##0',
                'bold': True
            }),
            'text': workbook.add_format({
                'align': 'left'
            }),
            'text_center': workbook.add_format({
                'align': 'center'
            }),
            'text_right': workbook.add_format({
                'align': 'right'
            }),
            'text_bold': workbook.add_format({
                'bold': True
            }),
            'border': workbook.add_format({
                'border': 1
            }),
            'border_bold': workbook.add_format({
                'border': 1,
                'bold': True
            }),
        }
        
        return workbook, output, styles
    
    def _finalize_workbook(self, workbook, output):
        """Finalize and return the workbook as base64 data"""
        workbook.close()
        output.seek(0)
        file_data = output.read()
        return base64.b64encode(file_data)
    
    def _generate_bhxh_01_report(self):
        """Generate BHXH 01 report - Employee social insurance registration form"""
        employees = self._get_employees()
        if not employees:
            return {'error': _("No employees found matching criteria.")}
        
        # Create workbook
        workbook, output, styles = self._prepare_workbook()
        sheet = workbook.add_worksheet(_('BHXH 01'))
        
        # Set column widths
        sheet.set_column(0, 0, 5)   # STT 
        sheet.set_column(1, 1, 25)  # Họ và tên
        sheet.set_column(2, 2, 15)  # Mã số BHXH
        sheet.set_column(3, 3, 10)  # Ngày sinh
        sheet.set_column(4, 4, 10)  # Giới tính
        sheet.set_column(5, 5, 20)  # Số CMND/CCCD
        sheet.set_column(6, 6, 15)  # Nơi cấp
        sheet.set_column(7, 7, 30)  # Địa chỉ
        sheet.set_column(8, 8, 15)  # Mức lương BHXH
        sheet.set_column(9, 9, 20)  # Phụ cấp
        sheet.set_column(10, 10, 25)  # Vị trí/Chức danh
        sheet.set_column(11, 11, 15)  # Ngày bắt đầu
        sheet.set_column(12, 12, 15)  # Số hợp đồng
        
        # Write report title
        sheet.merge_range('A1:M1', _('CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'), styles['title'])
        sheet.merge_range('A2:M2', _('Độc lập - Tự do - Hạnh phúc'), styles['text_center'])
        sheet.merge_range('A4:M4', _('DANH SÁCH NGƯỜI LAO ĐỘNG THAM GIA BHXH, BHYT, BHTN'), styles['title'])
        
        # Write company information
        company = self.company_id
        sheet.merge_range('A6:C6', _('Tên đơn vị: %s') % company.name, styles['text_bold'])
        sheet.merge_range('A7:C7', _('Mã số đơn vị: %s') % (self.bhxh_company_code or ''), styles['text_bold'])
        sheet.merge_range('I6:M6', _('Mã số thuế: %s') % (company.vat or ''), styles['text_bold'])
        sheet.merge_range('I7:M7', _('Địa chỉ: %s') % (company.street or ''), styles['text_bold'])
        
        # Write header row
        headers = [
            _('STT'), _('Họ và tên'), _('Mã số BHXH'), 
            _('Ngày sinh'), _('Giới tính'), _('Số CMND/CCCD'), 
            _('Nơi cấp'), _('Địa chỉ nơi cư trú'), _('Mức lương BHXH'), 
            _('Phụ cấp'), _('Vị trí/Chức danh'), _('Ngày bắt đầu đóng BHXH'),
            _('Số hợp đồng LĐ')
        ]
        
        row = 9
        for col, header in enumerate(headers):
            sheet.write(row, col, header, styles['header'])
        
        # Write employee data
        row += 1
        for i, employee in enumerate(employees):
            contract = employee.contract_id
            if not contract:
                continue
                
            # Get social insurance code - may be in different fields depending on implementation
            social_insurance_code = employee.social_insurance_code if hasattr(employee, 'social_insurance_code') else ''
            
            # Basic data
            sheet.write(row, 0, i+1, styles['text_center'])
            sheet.write(row, 1, employee.name, styles['text'])
            sheet.write(row, 2, social_insurance_code, styles['text_center'])
            sheet.write(row, 3, employee.birthday or '', styles['date'])
            sheet.write(row, 4, dict(employee._fields['gender'].selection).get(employee.gender) if employee.gender else '', styles['text_center'])
            
            # ID information
            identification_id = employee.identification_id or ''
            sheet.write(row, 5, identification_id, styles['text_center'])
            sheet.write(row, 6, employee.place_of_issue if hasattr(employee, 'place_of_issue') else '', styles['text'])
            
            # Address
            address = (employee.address_home_id.street or '') if employee.address_home_id else ''
            sheet.write(row, 7, address, styles['text'])
            
            # Salary information
            sheet.write(row, 8, contract.wage, styles['number'])
            
            # Get allowances - implementation may vary
            allowances = 0
            if hasattr(contract, 'allowance_ids'):
                allowances = sum(contract.allowance_ids.mapped('amount'))
            sheet.write(row, 9, allowances, styles['number'])
            
            # Position and contract info
            position = employee.job_id.name if employee.job_id else ''
            sheet.write(row, 10, position, styles['text'])
            sheet.write(row, 11, contract.date_start or '', styles['date'])
            sheet.write(row, 12, contract.name or '', styles['text_center'])
            
            row += 1
        
        # Write footer with signature spaces
        row += 2
        sheet.merge_range(f'A{row}:E{row}', '', styles['text'])
        sheet.merge_range(f'I{row}:M{row}', _('Ngày %s tháng %s năm %s') % (
            self.report_date.day, self.report_date.month, self.report_date.year), styles['text_right'])
        
        row += 1
        sheet.merge_range(f'A{row}:E{row}', _('NGƯỜI LẬP BIỂU'), styles['text_center'])
        sheet.merge_range(f'I{row}:M{row}', _('GIÁM ĐỐC'), styles['text_center'])
        
        row += 1
        sheet.merge_range(f'A{row}:E{row}', _('(Ký, ghi rõ họ tên)'), styles['text_center'])
        sheet.merge_range(f'I{row}:M{row}', _('(Ký, đóng dấu, ghi rõ họ tên)'), styles['text_center'])
        
        row += 5
        sheet.merge_range(f'A{row}:E{row}', self.reporter_name or '', styles['text_center'])
        sheet.merge_range(f'I{row}:M{row}', self.signer_name or '', styles['text_center'])
        
        file_data = self._finalize_workbook(workbook, output)
        return {
            'file': file_data,
            'file_name': 'BHXH01_DangKyThamGia.xlsx'
        } 