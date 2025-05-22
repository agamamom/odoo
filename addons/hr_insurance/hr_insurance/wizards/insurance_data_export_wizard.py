# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, date
import base64
import csv
import io


class InsuranceDataExportWizard(models.TransientModel):
    _name = 'insurance.data.export.wizard'
    _description = 'Insurance Data Export Wizard'

    name = fields.Char(string='Tên file', required=True, default='BHXH_Export')
    date_from = fields.Date(string='Từ ngày', required=True, default=lambda self: date(date.today().year, date.today().month, 1))
    date_to = fields.Date(string='Đến ngày', required=True, default=lambda self: date.today())
    
    export_type = fields.Selection([
        ('insurance_history', 'Lịch sử đóng BHXH'),
        ('insurance_payment', 'Chi tiết thanh toán'),
        ('insurance_late_fee', 'Phí chậm nộp'),
        ('insurance_benefit', 'Quyền lợi bảo hiểm'),
        ('all', 'Tất cả dữ liệu')
    ], string='Loại dữ liệu xuất', required=True, default='insurance_history')
    
    department_ids = fields.Many2many('hr.department', string='Phòng ban',
                                     help='Để trống nếu xuất dữ liệu cho toàn bộ công ty')
    
    employee_ids = fields.Many2many('hr.employee', string='Nhân viên',
                                    help='Để trống nếu xuất dữ liệu cho tất cả nhân viên')
    
    include_personal_info = fields.Boolean(string='Bao gồm thông tin cá nhân', default=True,
                                         help='Thêm thông tin cá nhân của nhân viên như ID, ngày sinh, địa chỉ, v.v')
    
    file_format = fields.Selection([
        ('csv', 'CSV'),
        ('xlsx', 'Excel (XLSX)')
    ], string='Định dạng file', required=True, default='csv')
    
    export_data = fields.Binary(string='Dữ liệu xuất', readonly=True)
    filename = fields.Char(string='Tên file tải về')
    
    state = fields.Selection([
        ('choose', 'Lựa chọn'),
        ('get', 'Tải xuống')
    ], string='Trạng thái', default='choose')
    
    def action_export(self):
        """Export insurance data based on the selections"""
        self.ensure_one()
        
        # Build domain for filtering employees
        employee_domain = []
        if self.department_ids:
            employee_domain.append(('department_id', 'in', self.department_ids.ids))
        if self.employee_ids:
            employee_domain.append(('id', 'in', self.employee_ids.ids))
            
        employees = self.env['hr.employee'].search(employee_domain)
        if not employees:
            raise UserError(_("Không tìm thấy nhân viên nào thỏa mãn điều kiện lọc."))
        
        # Prepare data based on export type
        method_name = f'_prepare_{self.export_type}_data'
        if not hasattr(self, method_name):
            raise UserError(_("Chức năng xuất loại dữ liệu này chưa được hỗ trợ."))
            
        data = getattr(self, method_name)(employees)
        
        # Export to the selected format
        if self.file_format == 'csv':
            result = self._export_as_csv(data)
        elif self.file_format == 'xlsx':
            result = self._export_as_xlsx(data)
        else:
            raise UserError(_("Định dạng file không được hỗ trợ."))
        
        # Update wizard state and return
        self.write({
            'state': 'get',
            'export_data': result['file_data'],
            'filename': result['filename']
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'insurance.data.export.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
    
    def _prepare_insurance_history_data(self, employees):
        """Prepare insurance history data for export"""
        header = [
            'Mã nhân viên', 'Tên nhân viên', 'Mã số BHXH', 'Phòng ban', 
            'Năm', 'Tháng', 'Ngày đóng', 'Lương cơ sở',
            'BHXH (NV)', 'BHXH (CTY)', 'BHYT (NV)', 'BHYT (CTY)', 
            'BHTN (NV)', 'BHTN (CTY)', 'Tổng đóng', 'Trạng thái',
        ]
        
        # Add personal info columns if requested
        if self.include_personal_info:
            header.extend(['Ngày sinh', 'Số CMND/CCCD', 'Địa chỉ', 'Thâm niên (tháng)'])
        
        rows = [header]
        
        # Get history records
        history_domain = [
            ('employee_id', 'in', employees.ids),
            ('payment_date', '>=', self.date_from),
            ('payment_date', '<=', self.date_to),
        ]
        
        history_records = self.env['social.insurance.history'].search(history_domain)
        
        for record in history_records:
            employee = record.employee_id
            
            row = [
                employee.barcode or '',
                employee.name,
                employee.social_insurance_code or '',
                employee.department_id.name or '',
                record.year,
                record.month,
                record.payment_date.strftime('%Y-%m-%d') if record.payment_date else '',
                record.salary_base,
                record.bhxh_employee_amount,
                record.bhxh_company_amount,
                record.bhyt_employee_amount,
                record.bhyt_company_amount,
                record.bhtn_employee_amount,
                record.bhtn_company_amount,
                record.total_amount,
                dict(record._fields['state'].selection).get(record.state),
            ]
            
            # Add personal info if requested
            if self.include_personal_info:
                seniority_months = 0
                if employee.contract_id and employee.contract_id.date_start:
                    seniority_months = (date.today().year - employee.contract_id.date_start.year) * 12 + \
                                      (date.today().month - employee.contract_id.date_start.month)
                
                row.extend([
                    employee.birthday.strftime('%Y-%m-%d') if employee.birthday else '',
                    employee.identification_id or '',
                    employee.address_home_id.contact_address if employee.address_home_id else '',
                    seniority_months,
                ])
                
            rows.append(row)
            
        return {
            'title': 'Lịch sử đóng BHXH',
            'headers': header,
            'rows': rows,
            'empty_msg': 'Không có dữ liệu lịch sử đóng BHXH trong khoảng thời gian này.'
        }
    
    def _prepare_insurance_payment_data(self, employees):
        """Prepare insurance payment data for export"""
        header = [
            'Mã nhân viên', 'Tên nhân viên', 'Mã số BHXH', 'Phòng ban',
            'Mã thanh toán', 'Kỳ thanh toán', 'Ngày thanh toán', 'Lương cơ sở',
            'BHXH', 'BHYT', 'BHTN', 'Tổng thanh toán',
        ]
        
        rows = [header]
        
        # Get payment line records
        payment_domain = [
            ('payment_date', '>=', self.date_from),
            ('payment_date', '<=', self.date_to),
        ]
        
        payments = self.env['insurance.payment'].search(payment_domain)
        payment_lines = self.env['insurance.payment.line'].search([
            ('payment_id', 'in', payments.ids),
            ('employee_id', 'in', employees.ids),
        ])
        
        for line in payment_lines:
            employee = line.employee_id
            payment = line.payment_id
            
            row = [
                employee.barcode or '',
                employee.name,
                employee.social_insurance_code or '',
                employee.department_id.name or '',
                payment.name or '',
                f"{payment.period_month}/{payment.period_year}" if payment.period_month and payment.period_year else '',
                payment.payment_date.strftime('%Y-%m-%d') if payment.payment_date else '',
                line.salary_base,
                line.bhxh_amount,
                line.bhyt_amount,
                line.bhtn_amount,
                line.total_amount,
            ]
            
            rows.append(row)
            
        return {
            'title': 'Chi tiết thanh toán BHXH',
            'headers': header,
            'rows': rows,
            'empty_msg': 'Không có dữ liệu thanh toán BHXH trong khoảng thời gian này.'
        }
    
    def _prepare_insurance_late_fee_data(self, employees):
        """Prepare late fee data for export"""
        header = [
            'Mã nhân viên', 'Tên nhân viên', 'Mã số BHXH', 'Phòng ban',
            'Mã truy thu', 'Kỳ truy thu', 'Số ngày chậm nộp', 'Lương cơ sở',
            'BHXH phải đóng', 'BHYT phải đóng', 'BHTN phải đóng',
            'BHXH đã đóng', 'BHYT đã đóng', 'BHTN đã đóng',
            'Tiền còn thiếu', 'Lãi phạt', 'Tổng phải đóng', 'Trách nhiệm',
            'Trạng thái',
        ]
        
        rows = [header]
        
        # Get late fee records
        late_fee_domain = [
            ('employee_id', 'in', employees.ids),
            ('state', 'in', ['confirmed', 'paid']),
        ]
        
        if self.date_from and self.date_to:
            late_fee_domain.extend([
                '|', '|',
                '&', ('period_type', '=', 'month'), 
                     '&', ('year', '>=', str(self.date_from.year)), ('year', '<=', str(self.date_to.year)),
                '&', ('period_type', '=', 'range'), ('date_from', '>=', self.date_from),
                '&', ('period_type', '=', 'range'), ('date_to', '<=', self.date_to),
            ])
        
        late_fees = self.env['social.insurance.late.fee'].search(late_fee_domain)
        
        for fee in late_fees:
            employee = fee.employee_id
            
            period_str = ''
            if fee.period_type == 'month':
                period_str = f"{fee.month}/{fee.year}"
            else:
                period_str = f"{fee.date_from.strftime('%d/%m/%Y')} - {fee.date_to.strftime('%d/%m/%Y')}"
            
            row = [
                employee.barcode or '',
                employee.name,
                employee.social_insurance_code or '',
                employee.department_id.name or '',
                fee.name,
                period_str,
                fee.days_late,
                fee.salary_base,
                fee.bhxh_amount_due,
                fee.bhyt_amount_due,
                fee.bhtn_amount_due,
                fee.bhxh_amount_paid,
                fee.bhyt_amount_paid,
                fee.bhtn_amount_paid,
                fee.total_amount_pending,
                fee.interest_amount,
                fee.total_payment,
                'Công ty' if fee.is_company_responsibility else 'Nhân viên',
                dict(fee._fields['state'].selection).get(fee.state),
            ]
            
            rows.append(row)
            
        return {
            'title': 'Phí chậm nộp BHXH',
            'headers': header,
            'rows': rows,
            'empty_msg': 'Không có dữ liệu phí chậm nộp BHXH trong khoảng thời gian này.'
        }
    
    def _prepare_insurance_benefit_data(self, employees):
        """Prepare insurance benefit data for export"""
        header = [
            'Mã nhân viên', 'Tên nhân viên', 'Mã số BHXH', 'Phòng ban',
            'Loại trợ cấp', 'Từ ngày', 'Đến ngày', 'Số ngày hưởng',
            'Lương cơ sở', 'Tỷ lệ hưởng (%)', 'Số tiền trợ cấp',
            'Trạng thái', 'Ngày chi trả', 'Phương thức chi trả',
            'Số hiệu hồ sơ BHXH',
        ]
        
        rows = [header]
        
        # Get benefit records
        benefit_domain = [
            ('employee_id', 'in', employees.ids),
            '|', 
            '&', ('date_from', '>=', self.date_from), ('date_from', '<=', self.date_to),
            '&', ('date_to', '>=', self.date_from), ('date_to', '<=', self.date_to),
        ]
        
        benefits = self.env['social.insurance.benefit'].search(benefit_domain)
        
        for benefit in benefits:
            employee = benefit.employee_id
            
            row = [
                employee.barcode or '',
                employee.name,
                employee.social_insurance_code or '',
                employee.department_id.name or '',
                dict(benefit._fields['benefit_type'].selection).get(benefit.benefit_type),
                benefit.date_from.strftime('%Y-%m-%d') if benefit.date_from else '',
                benefit.date_to.strftime('%Y-%m-%d') if benefit.date_to else '',
                benefit.benefit_days,
                benefit.salary_base,
                benefit.benefit_rate,
                benefit.benefit_amount,
                dict(benefit._fields['state'].selection).get(benefit.state),
                benefit.payment_date.strftime('%Y-%m-%d') if benefit.payment_date else '',
                dict(benefit._fields['payment_method'].selection).get(benefit.payment_method) if benefit.payment_method else '',
                benefit.agency_reference or '',
            ]
            
            rows.append(row)
            
        return {
            'title': 'Quyền lợi bảo hiểm',
            'headers': header,
            'rows': rows,
            'empty_msg': 'Không có dữ liệu quyền lợi bảo hiểm trong khoảng thời gian này.'
        }
    
    def _prepare_all_data(self, employees):
        """Prepare all types of insurance data for export"""
        # For 'all' type, we create multiple sheets/sections in the export file
        result = {
            'title': 'Dữ liệu bảo hiểm xã hội',
            'sections': [
                self._prepare_insurance_history_data(employees),
                self._prepare_insurance_payment_data(employees),
                self._prepare_insurance_late_fee_data(employees),
                self._prepare_insurance_benefit_data(employees),
            ]
        }
        return result
    
    def _export_as_csv(self, data):
        """Export data as CSV file"""
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL, delimiter=',')
        
        if self.export_type == 'all':
            # Multiple sections, each with its own header
            for section in data['sections']:
                writer.writerow([section['title']])
                writer.writerow([])  # Empty row
                
                if len(section['rows']) > 1:  # Has data (header + at least one data row)
                    for row in section['rows']:
                        writer.writerow(row)
                else:
                    writer.writerow([section['empty_msg']])
                    
                writer.writerow([])
                writer.writerow([])  # Two empty rows between sections
        else:
            # Single section
            if len(data['rows']) > 1:  # Has data (header + at least one data row)
                for row in data['rows']:
                    writer.writerow(row)
            else:
                writer.writerow([data['empty_msg']])
        
        content = output.getvalue().encode()
        filename = f"{self.name}_{fields.Date.today().strftime('%Y%m%d')}.csv"
        
        return {
            'file_data': base64.b64encode(content),
            'filename': filename
        }
    
    def _export_as_xlsx(self, data):
        """Export data as XLSX file"""
        try:
            import xlsxwriter
        except ImportError:
            raise UserError(_("Thư viện xlsxwriter không khả dụng. Vui lòng cài đặt gói Python 'xlsxwriter'."))
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Define styles
        header_style = workbook.add_format({'bold': True, 'bg_color': '#EEEEEE', 'border': 1})
        data_style = workbook.add_format({'border': 1})
        date_style = workbook.add_format({'border': 1, 'num_format': 'yyyy-mm-dd'})
        number_style = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        title_style = workbook.add_format({'bold': True, 'font_size': 14})
        
        if self.export_type == 'all':
            # Multiple sheets, one for each section
            for idx, section in enumerate(data['sections']):
                sheet_name = section['title'][:31]  # Excel limits sheet names to 31 chars
                worksheet = workbook.add_worksheet(sheet_name)
                
                # Title
                worksheet.write(0, 0, section['title'], title_style)
                worksheet.write(1, 0, f"Từ {self.date_from.strftime('%d/%m/%Y')} đến {self.date_to.strftime('%d/%m/%Y')}")
                
                if len(section['rows']) > 1:  # Has data (header + at least one data row)
                    # Write headers
                    for col, header in enumerate(section['headers']):
                        worksheet.write(3, col, header, header_style)
                    
                    # Write data
                    for row_idx, row_data in enumerate(section['rows'][1:], 4):  # Start from row 4 (0-based)
                        for col_idx, cell_value in enumerate(row_data):
                            if isinstance(cell_value, (int, float)) and not isinstance(cell_value, bool):
                                worksheet.write(row_idx, col_idx, cell_value, number_style)
                            elif isinstance(cell_value, str) and cell_value.strip() and len(cell_value) == 10 and cell_value[4] == '-' and cell_value[7] == '-':
                                # Looks like a date string in format "YYYY-MM-DD"
                                try:
                                    date_val = datetime.strptime(cell_value, '%Y-%m-%d').date()
                                    worksheet.write_datetime(row_idx, col_idx, date_val, date_style)
                                except ValueError:
                                    worksheet.write(row_idx, col_idx, cell_value, data_style)
                            else:
                                worksheet.write(row_idx, col_idx, cell_value, data_style)
                else:
                    worksheet.write(3, 0, section['empty_msg'])
                
                # Auto-fit columns
                for col_idx, width in enumerate([len(h) + 2 for h in section['headers']]):
                    worksheet.set_column(col_idx, col_idx, width)
        else:
            # Single sheet
            worksheet = workbook.add_worksheet(data['title'][:31])
            
            # Title
            worksheet.write(0, 0, data['title'], title_style)
            worksheet.write(1, 0, f"Từ {self.date_from.strftime('%d/%m/%Y')} đến {self.date_to.strftime('%d/%m/%Y')}")
            
            if len(data['rows']) > 1:  # Has data (header + at least one data row)
                # Write headers
                for col, header in enumerate(data['headers']):
                    worksheet.write(3, col, header, header_style)
                
                # Write data
                for row_idx, row_data in enumerate(data['rows'][1:], 4):  # Start from row 4 (0-based)
                    for col_idx, cell_value in enumerate(row_data):
                        if isinstance(cell_value, (int, float)) and not isinstance(cell_value, bool):
                            worksheet.write(row_idx, col_idx, cell_value, number_style)
                        elif isinstance(cell_value, str) and cell_value.strip() and len(cell_value) == 10 and cell_value[4] == '-' and cell_value[7] == '-':
                            # Looks like a date string in format "YYYY-MM-DD"
                            try:
                                date_val = datetime.strptime(cell_value, '%Y-%m-%d').date()
                                worksheet.write_datetime(row_idx, col_idx, date_val, date_style)
                            except ValueError:
                                worksheet.write(row_idx, col_idx, cell_value, data_style)
                        else:
                            worksheet.write(row_idx, col_idx, cell_value, data_style)
            else:
                worksheet.write(3, 0, data['empty_msg'])
            
            # Auto-fit columns
            for col_idx, width in enumerate([len(h) + 2 for h in data['headers']]):
                worksheet.set_column(col_idx, col_idx, width)
        
        workbook.close()
        content = output.getvalue()
        filename = f"{self.name}_{fields.Date.today().strftime('%Y%m%d')}.xlsx"
        
        return {
            'file_data': base64.b64encode(content),
            'filename': filename
        } 