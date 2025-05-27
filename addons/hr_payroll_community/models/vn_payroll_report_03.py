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
import xml.etree.ElementTree as ET
from xml.dom import minidom

_logger = logging.getLogger(__name__)

class VNPayrollReport(models.Model):
    _inherit = 'vn.payroll.report'
    
    # Thông tin bổ sung cho báo cáo thuế
    tax_period = fields.Selection([
        ('month', 'Tháng'),
        ('quarter', 'Quý'),
        ('year', 'Năm')
    ], string='Kỳ thuế', default='month')
    tax_period_month = fields.Selection([
        ('01', '01'), ('02', '02'), ('03', '03'), ('04', '04'),
        ('05', '05'), ('06', '06'), ('07', '07'), ('08', '08'),
        ('09', '09'), ('10', '10'), ('11', '11'), ('12', '12')
    ], string='Tháng')
    tax_period_quarter = fields.Selection([
        ('1', 'Quý 1'), ('2', 'Quý 2'), ('3', 'Quý 3'), ('4', 'Quý 4')
    ], string='Quý')
    tax_period_year = fields.Char(string='Năm', default=lambda self: str(fields.Date.today().year))
    tax_declaration_number = fields.Char(string='Số tờ khai')
    tax_authority = fields.Char(string='Cơ quan thuế', default='Chi cục Thuế')
    
    def _generate_pit_report(self):
        """Generate Personal Income Tax (PIT) report"""
        payslips = self._get_payslips()
        if not payslips:
            return {'error': _("No payslips found for the selected period.")}
        
        # Create workbook
        workbook, output, styles = self._prepare_workbook()
        sheet = workbook.add_worksheet(_('Bảng kê Thuế TNCN'))
        
        # Set column widths
        sheet.set_column(0, 0, 5)   # STT
        sheet.set_column(1, 1, 25)  # Họ và tên
        sheet.set_column(2, 2, 15)  # Mã số thuế
        sheet.set_column(3, 3, 15)  # CMND/CCCD
        sheet.set_column(4, 4, 15)  # Lương brutto
        sheet.set_column(5, 5, 15)  # Các khoản giảm trừ
        sheet.set_column(6, 6, 15)  # BHXH, BHYT, BHTN
        sheet.set_column(7, 7, 15)  # Giảm trừ gia cảnh
        sheet.set_column(8, 8, 15)  # Thu nhập tính thuế
        sheet.set_column(9, 9, 15)  # Thuế TNCN
        
        # Write report title
        period_name = ''
        if self.tax_period == 'month':
            period_name = _('THÁNG %s NĂM %s') % (self.tax_period_month or self.date_from.month, self.tax_period_year or self.date_from.year)
        elif self.tax_period == 'quarter':
            period_name = _('QUÝ %s NĂM %s') % (self.tax_period_quarter, self.tax_period_year or self.date_from.year)
        else:
            period_name = _('NĂM %s') % (self.tax_period_year or self.date_from.year)
            
        sheet.merge_range('A1:J1', _('BẢNG KÊ THU NHẬP CÁ NHÂN VÀ THUẾ TNCN %s') % period_name, styles['title'])
        
        # Write company information
        company = self.company_id
        sheet.merge_range('A3:E3', _('Đơn vị: %s') % company.name, styles['text_bold'])
        sheet.merge_range('A4:E4', _('Mã số thuế: %s') % (company.vat or ''), styles['text_bold'])
        sheet.merge_range('A5:E5', _('Địa chỉ: %s') % (company.street or ''), styles['text_bold'])
        
        # Write header row
        headers = [
            _('STT'), _('Họ và tên'), _('Mã số thuế'), 
            _('CMND/CCCD'), _('Tổng thu nhập'), _('Các khoản giảm trừ'), 
            _('BHXH, BHYT, BHTN'), _('Giảm trừ gia cảnh'), _('Thu nhập tính thuế'), 
            _('Thuế TNCN')
        ]
        
        row = 7
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
        row = 8
        total_gross = total_deductions = total_insurance = total_dependents = total_taxable = total_tax = 0
        
        for i, (employee, slips) in enumerate(payslips_by_employee.items()):
            # Get the latest payslip
            slip = slips[0] if len(slips) == 1 else sorted(slips, key=lambda s: s.date_to, reverse=True)[0]
            
            # Tax information
            tax_code = employee.identification_id or ''
            tax_id = employee.tin or '' if hasattr(employee, 'tin') else ''
            
            # Calculate totals from payslip
            gross = deductions = insurance = dependents = taxable = tax = 0
            
            # Map rule categories to amounts
            for line in slip.line_ids:
                rule_category = line.salary_rule_id.category_id.code
                rule_code = line.salary_rule_id.code
                
                # Map different categories
                if rule_category in ('BASIC', 'ALW', 'BONUS'):
                    gross += line.total
                elif rule_category == 'DED' and 'PIT' not in rule_code:
                    deductions += abs(line.total)
                elif rule_category == 'COMP':
                    insurance += abs(line.total)
                
                # Tax specific fields
                if rule_code == 'GROSS':
                    gross = line.total
                elif rule_code == 'TAXABLE':
                    taxable = line.total
                elif rule_code == 'PIT':
                    tax = abs(line.total)
                elif rule_code == 'DEP':
                    dependents = line.total
            
            # Calculate taxable income if not directly provided
            if taxable == 0:
                taxable = gross - insurance - dependents
            
            # Write employee row
            sheet.write(row, 0, i+1, styles['text_center'])
            sheet.write(row, 1, employee.name, styles['text'])
            sheet.write(row, 2, tax_id, styles['text_center'])
            sheet.write(row, 3, tax_code, styles['text_center'])
            sheet.write(row, 4, gross, styles['number'])
            sheet.write(row, 5, deductions, styles['number'])
            sheet.write(row, 6, insurance, styles['number'])
            sheet.write(row, 7, dependents, styles['number'])
            sheet.write(row, 8, taxable, styles['number'])
            sheet.write(row, 9, tax, styles['number'])
            
            # Update grand totals
            total_gross += gross
            total_deductions += deductions
            total_insurance += insurance
            total_dependents += dependents
            total_taxable += taxable
            total_tax += tax
            
            row += 1
        
        # Write totals row
        sheet.write(row, 0, '', styles['border'])
        sheet.write(row, 1, _('TỔNG CỘNG'), styles['border_bold'])
        sheet.write(row, 2, '', styles['border'])
        sheet.write(row, 3, '', styles['border'])
        sheet.write(row, 4, total_gross, styles['number_bold'])
        sheet.write(row, 5, total_deductions, styles['number_bold'])
        sheet.write(row, 6, total_insurance, styles['number_bold'])
        sheet.write(row, 7, total_dependents, styles['number_bold'])
        sheet.write(row, 8, total_taxable, styles['number_bold'])
        sheet.write(row, 9, total_tax, styles['number_bold'])
        
        # Write footer with signature spaces
        row += 3
        sheet.merge_range(f'A{row}:C{row}', '', styles['text'])
        sheet.merge_range(f'H{row}:J{row}', _('Ngày %s tháng %s năm %s') % (
            self.report_date.day, self.report_date.month, self.report_date.year), styles['text_right'])
        
        row += 1
        sheet.merge_range(f'A{row}:C{row}', _('NGƯỜI LẬP BIỂU'), styles['text_center'])
        sheet.merge_range(f'H{row}:J{row}', _('GIÁM ĐỐC'), styles['text_center'])
        
        row += 1
        sheet.merge_range(f'A{row}:C{row}', _('(Ký, ghi rõ họ tên)'), styles['text_center'])
        sheet.merge_range(f'H{row}:J{row}', _('(Ký, đóng dấu, ghi rõ họ tên)'), styles['text_center'])
        
        row += 5
        sheet.merge_range(f'A{row}:C{row}', self.reporter_name or '', styles['text_center'])
        sheet.merge_range(f'H{row}:J{row}', self.signer_name or '', styles['text_center'])
        
        file_data = self._finalize_workbook(workbook, output)
        
        # Determine the period for filename
        period_str = ''
        if self.tax_period == 'month':
            period_str = f"Thang{self.tax_period_month or self.date_from.month}"
        elif self.tax_period == 'quarter':
            period_str = f"Quy{self.tax_period_quarter}"
        else:
            period_str = f"Nam{self.tax_period_year or self.date_from.year}"
            
        return {
            'file': file_data,
            'file_name': f'BangKeThueTNCN_{period_str}.xlsx'
        }
    
    def _generate_pit_xml_report(self):
        """Generate Personal Income Tax (PIT) XML report according to Vietnamese Tax Authority format"""
        payslips = self._get_payslips()
        if not payslips:
            return {'error': _("No payslips found for the selected period.")}
        
        # Group payslips by employee
        payslips_by_employee = {}
        for slip in payslips:
            employee = slip.employee_id
            if employee not in payslips_by_employee:
                payslips_by_employee[employee] = []
            payslips_by_employee[employee].append(slip)
        
        # Create XML structure
        root = ET.Element("HSoThueDTu")
        
        # Add metadata
        metadata = ET.SubElement(root, "HSoKhaiThue")
        ET.SubElement(metadata, "TTChung")
        ET.SubElement(metadata, "NNT")
        ET.SubElement(metadata, "TTinChung")
        
        # Add header information
        header = metadata.find("TTChung")
        ET.SubElement(header, "PBan").text = "2.0.0"
        ET.SubElement(header, "MaHSo").text = "01/TNCN"
        
        # Period for the declaration
        period_type = ""
        period_value = ""
        if self.tax_period == 'month':
            period_type = "M"
            period_value = self.tax_period_month or str(self.date_from.month).zfill(2)
        elif self.tax_period == 'quarter':
            period_type = "Q"
            period_value = self.tax_period_quarter
        else:
            period_type = "Y"
            period_value = self.tax_period_year or str(self.date_from.year)
            
        ET.SubElement(header, "KyKKhai").text = period_type
        ET.SubElement(header, "KyKKhaiTuNgay").text = self.date_from.strftime("%d/%m/%Y")
        ET.SubElement(header, "KyKKhaiDenNgay").text = self.date_to.strftime("%d/%m/%Y")
        ET.SubElement(header, "NamKKhai").text = period_value if period_type == "Y" else str(self.date_from.year)
        ET.SubElement(header, "GiaHan").text = "0"
        
        # Company information
        company = self.company_id
        taxpayer = metadata.find("NNT")
        ET.SubElement(taxpayer, "mst").text = company.vat or ""
        ET.SubElement(taxpayer, "tenNNT").text = company.name
        ET.SubElement(taxpayer, "dchiNNT").text = company.street or ""
        ET.SubElement(taxpayer, "dthoaiNNT").text = company.phone or ""
        ET.SubElement(taxpayer, "faxNNT").text = company.fax if hasattr(company, 'fax') else ""
        ET.SubElement(taxpayer, "emailNNT").text = company.email or ""
        
        # General information
        general = metadata.find("TTinChung")
        ET.SubElement(general, "cqtqlTD").text = self.tax_authority or ""
        ET.SubElement(general, "ngayLapTKhai").text = self.report_date.strftime("%d/%m/%Y")
        
        # Employee data
        employees_section = ET.SubElement(root, "PLuc01")
        
        total_gross = total_insurance = total_taxable = total_tax = 0
        employee_count = 0
        
        for employee, slips in payslips_by_employee.items():
            # Skip employees without tax ID
            tax_id = employee.tin or '' if hasattr(employee, 'tin') else ''
            if not tax_id:
                continue
                
            # Get the latest payslip
            slip = slips[0] if len(slips) == 1 else sorted(slips, key=lambda s: s.date_to, reverse=True)[0]
            
            # Calculate totals from payslip
            gross = insurance = dependents = taxable = tax = 0
            
            # Map rule categories to amounts
            for line in slip.line_ids:
                rule_category = line.salary_rule_id.category_id.code
                rule_code = line.salary_rule_id.code
                
                # Map different categories
                if rule_category in ('BASIC', 'ALW', 'BONUS'):
                    gross += line.total
                elif rule_category == 'COMP':
                    insurance += abs(line.total)
                
                # Tax specific fields
                if rule_code == 'GROSS':
                    gross = line.total
                elif rule_code == 'TAXABLE':
                    taxable = line.total
                elif rule_code == 'PIT':
                    tax = abs(line.total)
                elif rule_code == 'DEP':
                    dependents = line.total
            
            # Calculate taxable income if not directly provided
            if taxable == 0:
                taxable = gross - insurance - dependents
            
            # Add employee entry
            employee_entry = ET.SubElement(employees_section, "CTietNLD")
            ET.SubElement(employee_entry, "stt").text = str(employee_count + 1)
            ET.SubElement(employee_entry, "ten").text = employee.name
            ET.SubElement(employee_entry, "mst").text = tax_id
            ET.SubElement(employee_entry, "cccd").text = employee.identification_id or ""
            ET.SubElement(employee_entry, "tongTNChiuThue").text = str(int(taxable))
            ET.SubElement(employee_entry, "thueTNCN").text = str(int(tax))
            
            # Update totals
            total_gross += gross
            total_insurance += insurance
            total_taxable += taxable
            total_tax += tax
            employee_count += 1
        
        # Summary section
        summary = ET.SubElement(root, "PLuc01_HDKCN")
        ET.SubElement(summary, "tongSoNLD").text = str(employee_count)
        ET.SubElement(summary, "tongTNChiuThue").text = str(int(total_taxable))
        ET.SubElement(summary, "tongThueKhauTru").text = str(int(total_tax))
        
        # Generate XML file
        xml_str = minidom.parseString(ET.tostring(root)).toprettyxml(indent="  ")
        
        # Determine the period for filename
        period_str = ''
        if self.tax_period == 'month':
            period_str = f"Thang{self.tax_period_month or self.date_from.month}"
        elif self.tax_period == 'quarter':
            period_str = f"Quy{self.tax_period_quarter}"
        else:
            period_str = f"Nam{self.tax_period_year or self.date_from.year}"
        
        file_name = f'ThueTNCN_{period_str}.xml'
        
        return {
            'file': base64.b64encode(xml_str.encode('utf-8')),
            'file_name': file_name
        } 