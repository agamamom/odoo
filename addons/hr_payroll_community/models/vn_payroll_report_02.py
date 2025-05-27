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

_logger = logging.getLogger(__name__)

class VNPayrollReportMixin(models.AbstractModel):
    _name = 'vn.payroll.report.mixin'
    _description = 'Vietnam Payroll Report Mixin'
    
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

class VNPayrollReport(models.Model):
    _inherit = 'vn.payroll.report'
    
    def _generate_income_summary_report(self):
        """Generate income summary report"""
        payslips = self._get_payslips()
        if not payslips:
            return {'error': _("No payslips found for the selected period.")}
        
        # Create workbook
        workbook, output, styles = self._prepare_workbook()
        sheet = workbook.add_worksheet(_('Bảng Tổng hợp Thu nhập'))
        
        # Set column widths
        sheet.set_column(0, 0, 5)   # STT
        sheet.set_column(1, 1, 25)  # Họ và tên
        sheet.set_column(2, 2, 15)  # Mã NV
        sheet.set_column(3, 3, 18)  # Phòng/Ban
        sheet.set_column(4, 4, 18)  # Chức vụ
        sheet.set_column(5, 5, 15)  # Lương cơ bản
        sheet.set_column(6, 6, 15)  # Lương thực tế
        sheet.set_column(7, 7, 15)  # Phụ cấp
        sheet.set_column(8, 8, 15)  # Thưởng
        sheet.set_column(9, 9, 15)  # Tổng thu nhập
        sheet.set_column(10, 10, 15)  # BHXH
        sheet.set_column(11, 11, 15)  # BHYT
        sheet.set_column(12, 12, 15)  # BHTN
        sheet.set_column(13, 13, 15)  # Thuế TNCN
        sheet.set_column(14, 14, 15)  # Tổng khấu trừ
        sheet.set_column(15, 15, 15)  # Thực lãnh
        
        # Write report title
        sheet.merge_range('A1:P1', _('BẢNG TỔNG HỢP THU NHẬP THÁNG %s/%s') % (
            self.date_from.month, self.date_from.year), styles['title'])
        
        # Write company information
        company = self.company_id
        sheet.merge_range('A3:F3', _('Đơn vị: %s') % company.name, styles['text_bold'])
        sheet.merge_range('A4:F4', _('Địa chỉ: %s') % (company.street or ''), styles['text_bold'])
        
        # Write header row
        headers = [
            _('STT'), _('Họ và tên'), _('Mã NV'), 
            _('Phòng/Ban'), _('Chức vụ'), _('Lương cơ bản'), 
            _('Lương thực tế'), _('Phụ cấp'), _('Thưởng'), 
            _('Tổng thu nhập'), _('BHXH'), _('BHYT'),
            _('BHTN'), _('Thuế TNCN'), _('Tổng khấu trừ'), _('Thực lãnh')
        ]
        
        row = 5
        for col, header in enumerate(headers):
            sheet.write(row, col, header, styles['header'])
        
        # Group payslips by employee
        payslips_by_employee = {}
        for slip in payslips:
            employee = slip.employee_id
            if employee not in payslips_by_employee:
                payslips_by_employee[employee] = []
            payslips_by_employee[employee].append(slip)
        
        # Write employee data
        row = 6
        total_basic = total_wage = total_allowance = total_bonus = total_gross = 0
        total_si = total_hi = total_ui = total_pit = total_deduction = total_net = 0
        
        for i, (employee, slips) in enumerate(payslips_by_employee.items()):
            # Get the latest payslip
            slip = slips[0] if len(slips) == 1 else sorted(slips, key=lambda s: s.date_to, reverse=True)[0]
            
            # Get department and position
            department = employee.department_id.name if employee.department_id else ''
            position = employee.job_id.name if employee.job_id else ''
            
            # Get salary information
            basic_salary = employee.contract_id.wage if employee.contract_id else 0
            
            # Calculate totals from payslip
            wage = allowance = bonus = si = hi = ui = pit = 0
            
            # Map rule categories to amounts
            for line in slip.line_ids:
                rule_category = line.salary_rule_id.category_id.code
                
                # Basic classifications
                if rule_category == 'BASIC':
                    wage += line.total
                elif rule_category == 'ALW':
                    allowance += line.total
                elif rule_category == 'BONUS':
                    bonus += line.total
                # Deductions
                elif rule_category == 'COMP' and 'SI' in line.salary_rule_id.code:
                    si += abs(line.total)
                elif rule_category == 'COMP' and 'HI' in line.salary_rule_id.code:
                    hi += abs(line.total)
                elif rule_category == 'COMP' and 'UI' in line.salary_rule_id.code:
                    ui += abs(line.total)
                elif rule_category == 'DED' and 'PIT' in line.salary_rule_id.code:
                    pit += abs(line.total)
            
            # Calculate totals
            gross = wage + allowance + bonus
            total_deductions = si + hi + ui + pit
            net = gross - total_deductions
            
            # Write employee row
            sheet.write(row, 0, i+1, styles['text_center'])
            sheet.write(row, 1, employee.name, styles['text'])
            sheet.write(row, 2, employee.employee_code if hasattr(employee, 'employee_code') else '', styles['text_center'])
            sheet.write(row, 3, department, styles['text'])
            sheet.write(row, 4, position, styles['text'])
            sheet.write(row, 5, basic_salary, styles['number'])
            sheet.write(row, 6, wage, styles['number'])
            sheet.write(row, 7, allowance, styles['number'])
            sheet.write(row, 8, bonus, styles['number'])
            sheet.write(row, 9, gross, styles['number'])
            sheet.write(row, 10, si, styles['number'])
            sheet.write(row, 11, hi, styles['number'])
            sheet.write(row, 12, ui, styles['number'])
            sheet.write(row, 13, pit, styles['number'])
            sheet.write(row, 14, total_deductions, styles['number'])
            sheet.write(row, 15, net, styles['number'])
            
            # Update grand totals
            total_basic += basic_salary
            total_wage += wage
            total_allowance += allowance
            total_bonus += bonus
            total_gross += gross
            total_si += si
            total_hi += hi
            total_ui += ui
            total_pit += pit
            total_deduction += total_deductions
            total_net += net
            
            row += 1
        
        # Write totals row
        sheet.write(row, 0, '', styles['border'])
        sheet.write(row, 1, _('TỔNG CỘNG'), styles['border_bold'])
        sheet.write(row, 2, '', styles['border'])
        sheet.write(row, 3, '', styles['border'])
        sheet.write(row, 4, '', styles['border'])
        sheet.write(row, 5, total_basic, styles['number_bold'])
        sheet.write(row, 6, total_wage, styles['number_bold'])
        sheet.write(row, 7, total_allowance, styles['number_bold'])
        sheet.write(row, 8, total_bonus, styles['number_bold'])
        sheet.write(row, 9, total_gross, styles['number_bold'])
        sheet.write(row, 10, total_si, styles['number_bold'])
        sheet.write(row, 11, total_hi, styles['number_bold'])
        sheet.write(row, 12, total_ui, styles['number_bold'])
        sheet.write(row, 13, total_pit, styles['number_bold'])
        sheet.write(row, 14, total_deduction, styles['number_bold'])
        sheet.write(row, 15, total_net, styles['number_bold'])
        
        # Write footer with signature spaces
        row += 3
        sheet.merge_range(f'A{row}:E{row}', '', styles['text'])
        sheet.merge_range(f'L{row}:P{row}', _('Ngày %s tháng %s năm %s') % (
            self.report_date.day, self.report_date.month, self.report_date.year), styles['text_right'])
        
        row += 1
        sheet.merge_range(f'A{row}:E{row}', _('NGƯỜI LẬP BIỂU'), styles['text_center'])
        sheet.merge_range(f'L{row}:P{row}', _('GIÁM ĐỐC'), styles['text_center'])
        
        row += 1
        sheet.merge_range(f'A{row}:E{row}', _('(Ký, ghi rõ họ tên)'), styles['text_center'])
        sheet.merge_range(f'L{row}:P{row}', _('(Ký, đóng dấu, ghi rõ họ tên)'), styles['text_center'])
        
        row += 5
        sheet.merge_range(f'A{row}:E{row}', self.reporter_name or '', styles['text_center'])
        sheet.merge_range(f'L{row}:P{row}', self.signer_name or '', styles['text_center'])
        
        file_data = self._finalize_workbook(workbook, output)
        return {
            'file': file_data,
            'file_name': f'TongHopThuNhap_{self.date_from.month}_{self.date_from.year}.xlsx'
        }
    
    def _generate_bhxh_02_report(self):
        """Generate BHXH 02 report - Changes in social insurance information"""
        employees = self._get_employees()
        if not employees:
            return {'error': _("No employees found matching criteria.")}
        
        # Create workbook
        workbook, output, styles = self._prepare_workbook()
        sheet = workbook.add_worksheet(_('BHXH 02'))
        
        # Set column widths
        sheet.set_column(0, 0, 5)   # STT
        sheet.set_column(1, 1, 25)  # Họ và tên
        sheet.set_column(2, 2, 15)  # Mã số BHXH
        sheet.set_column(3, 3, 20)  # Thông tin cũ
        sheet.set_column(4, 4, 20)  # Thông tin mới
        sheet.set_column(5, 5, 20)  # Thời điểm thay đổi
        sheet.set_column(6, 6, 25)  # Lý do thay đổi
        
        # Write report title
        sheet.merge_range('A1:G1', _('CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM'), styles['title'])
        sheet.merge_range('A2:G2', _('Độc lập - Tự do - Hạnh phúc'), styles['text_center'])
        sheet.merge_range('A4:G4', _('DANH SÁCH THAY ĐỔI THÔNG TIN THAM GIA BHXH, BHYT, BHTN'), styles['title'])
        
        # Write company information
        company = self.company_id
        sheet.merge_range('A6:C6', _('Tên đơn vị: %s') % company.name, styles['text_bold'])
        sheet.merge_range('A7:C7', _('Mã số đơn vị: %s') % (self.bhxh_company_code or ''), styles['text_bold'])
        sheet.merge_range('E6:G6', _('Mã số thuế: %s') % (company.vat or ''), styles['text_bold'])
        sheet.merge_range('E7:G7', _('Địa chỉ: %s') % (company.street or ''), styles['text_bold'])
        
        # Write header row
        headers = [
            _('STT'), _('Họ và tên'), _('Mã số BHXH'), 
            _('Thông tin cũ'), _('Thông tin mới'), 
            _('Thời điểm thay đổi'), _('Lý do thay đổi')
        ]
        
        row = 9
        for col, header in enumerate(headers):
            sheet.write(row, col, header, styles['header'])
        
        # Here we would need actual changes data - for demonstration, using mock data
        # In a real implementation, this should fetch changes from hr.employee.history or similar
        
        # For this example, just showing potential salary changes for demonstration
        row += 1
        for i, employee in enumerate(employees[:5]):  # Limit to 5 for example
            contract = employee.contract_id
            if not contract:
                continue
                
            # Get social insurance code - may be in different fields depending on implementation
            social_insurance_code = employee.social_insurance_code if hasattr(employee, 'social_insurance_code') else ''
            
            # Mock old and new data - in real implementation, get from history
            old_value = contract.wage * 0.9  # Simulate 10% lower previous wage
            new_value = contract.wage
            change_date = fields.Date.today() - timedelta(days=30)  # Mock date 1 month ago
            reason = _("Điều chỉnh lương")
            
            # Basic data
            sheet.write(row, 0, i+1, styles['text_center'])
            sheet.write(row, 1, employee.name, styles['text'])
            sheet.write(row, 2, social_insurance_code, styles['text_center'])
            
            # Change information
            sheet.write(row, 3, f"Mức lương BHXH: {old_value:,.0f} VND", styles['text'])
            sheet.write(row, 4, f"Mức lương BHXH: {new_value:,.0f} VND", styles['text'])
            sheet.write(row, 5, change_date, styles['date'])
            sheet.write(row, 6, reason, styles['text'])
            
            row += 1
        
        # Write footer with signature spaces
        row += 2
        sheet.merge_range(f'A{row}:C{row}', '', styles['text'])
        sheet.merge_range(f'E{row}:G{row}', _('Ngày %s tháng %s năm %s') % (
            self.report_date.day, self.report_date.month, self.report_date.year), styles['text_right'])
        
        row += 1
        sheet.merge_range(f'A{row}:C{row}', _('NGƯỜI LẬP BIỂU'), styles['text_center'])
        sheet.merge_range(f'E{row}:G{row}', _('GIÁM ĐỐC'), styles['text_center'])
        
        row += 1
        sheet.merge_range(f'A{row}:C{row}', _('(Ký, ghi rõ họ tên)'), styles['text_center'])
        sheet.merge_range(f'E{row}:G{row}', _('(Ký, đóng dấu, ghi rõ họ tên)'), styles['text_center'])
        
        row += 5
        sheet.merge_range(f'A{row}:C{row}', self.reporter_name or '', styles['text_center'])
        sheet.merge_range(f'E{row}:G{row}', self.signer_name or '', styles['text_center'])
        
        file_data = self._finalize_workbook(workbook, output)
        return {
            'file': file_data,
            'file_name': 'BHXH02_ThayDoiThongTin.xlsx'
        } 