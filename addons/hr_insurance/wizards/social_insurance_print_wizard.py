# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import io
from datetime import date, datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

try:
    import xlsxwriter
except ImportError:
    _logger.warning("Không thể import thư viện xlsxwriter, chức năng xuất Excel sẽ không hoạt động")
    xlsxwriter = None

class SocialInsurancePrintWizard(models.TransientModel):
    _name = 'social.insurance.print.wizard'
    _description = 'Social Insurance Print Wizard'

    document_id = fields.Many2one('social.insurance.document', string='Tài liệu BHXH', required=True)
    form_type = fields.Selection([
        ('tk1_ts', 'Mẫu TK1-TS (Đăng ký tham gia)'),
        ('tk3_ts', 'Mẫu TK3-TS (Điều chỉnh thông tin)'),
        ('termination', 'Mẫu chấm dứt tham gia'),
        ('unemployment', 'Mẫu trợ cấp thất nghiệp'),
    ], string='Loại biểu mẫu', required=True)
    
    # Form options
    include_attachments = fields.Boolean(string='Bao gồm tài liệu đính kèm', default=True)
    include_company_info = fields.Boolean(string='Bao gồm thông tin công ty', default=True)
    include_employee_detail = fields.Boolean(string='Chi tiết nhân viên', default=True)
    
    # PDF params
    use_header_footer = fields.Boolean(string='Sử dụng header/footer', default=True)
    paper_size = fields.Selection([
        ('a4', 'A4'),
        ('letter', 'Letter'),
    ], string='Khổ giấy', default='a4')
    
    # Output files
    state = fields.Selection([
        ('choose', 'choose'),
        ('get', 'get')
    ], default='choose')
    file_data = fields.Binary(string='File')
    file_name = fields.Char(string='Tên file')
    
    @api.model
    def default_get(self, fields_list):
        res = super(SocialInsurancePrintWizard, self).default_get(fields_list)
        
        active_id = self.env.context.get('active_id')
        if active_id:
            document = self.env['social.insurance.document'].browse(active_id)
            res['document_id'] = document.id
            
            # Auto select form type based on document type
            if document.document_type == 'registration' or document.document_type == 'tk1_ts':
                res['form_type'] = 'tk1_ts'
            elif document.document_type == 'adjustment' or document.document_type == 'tk3_ts':
                res['form_type'] = 'tk3_ts'
            elif document.document_type == 'termination':
                res['form_type'] = 'termination'
            elif document.document_type == 'unemployment':
                res['form_type'] = 'unemployment'
        
        return res
    
    def action_print_pdf(self):
        """Generate PDF report based on form type"""
        if not self.document_id or not self.form_type:
            raise UserError(_('Vui lòng chọn tài liệu BHXH và loại biểu mẫu'))
        
        # Generate PDF based on form type
        if self.form_type == 'tk1_ts':
            return self._generate_tk1_ts_pdf()
        elif self.form_type == 'tk3_ts':
            return self._generate_tk3_ts_pdf()
        elif self.form_type == 'termination':
            return self._generate_termination_pdf()
        elif self.form_type == 'unemployment':
            return self._generate_unemployment_pdf()
        else:
            raise UserError(_('Loại biểu mẫu không được hỗ trợ'))
    
    def action_generate_excel(self):
        """Generate Excel report based on form type"""
        if not self.document_id or not self.form_type:
            raise UserError(_('Vui lòng chọn tài liệu BHXH và loại biểu mẫu'))
        
        if not xlsxwriter:
            raise UserError(_('Không thể tạo file Excel. Thư viện xlsxwriter không khả dụng.'))
        
        # Generate Excel workbook
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        
        # Choose the appropriate form generation method
        if self.form_type == 'tk1_ts':
            self._generate_tk1_ts_excel(workbook)
        elif self.form_type == 'tk3_ts':
            self._generate_tk3_ts_excel(workbook)
        elif self.form_type == 'termination':
            self._generate_termination_excel(workbook)
        elif self.form_type == 'unemployment':
            self._generate_unemployment_excel(workbook)
        else:
            workbook.close()
            raise UserError(_('Loại biểu mẫu không được hỗ trợ'))
        
        # Save and return the generated Excel file
        workbook.close()
        output.seek(0)
        
        # Create file attachment
        file_data = base64.b64encode(output.read())
        file_name = f"{self.form_type}_{self.document_id.employee_id.name}_{date.today().strftime('%Y%m%d')}.xlsx"
        
        # Update wizard and switch to 'get' state
        self.write({
            'state': 'get',
            'file_data': file_data,
            'file_name': file_name
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'social.insurance.print.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
    
    def _generate_tk1_ts_pdf(self):
        """Generate TK1-TS form PDF"""
        # This would use Odoo's QWeb report engine in a real implementation
        # For now, we'll provide a simple implementation
        return self.env.ref('hr_insurance.action_report_tk1_ts').report_action(self.document_id)
    
    def _generate_tk3_ts_pdf(self):
        """Generate TK3-TS form PDF"""
        return self.env.ref('hr_insurance.action_report_tk3_ts').report_action(self.document_id)
    
    def _generate_termination_pdf(self):
        """Generate termination form PDF"""
        return self.env.ref('hr_insurance.action_report_termination').report_action(self.document_id)
    
    def _generate_unemployment_pdf(self):
        """Generate unemployment form PDF"""
        return self.env.ref('hr_insurance.action_report_unemployment').report_action(self.document_id)
    
    def _generate_tk1_ts_excel(self, workbook):
        """Generate TK1-TS form Excel"""
        document = self.document_id
        employee = document.employee_id
        company = self.env.company
        
        # Create workbook and add worksheet
        worksheet = workbook.add_worksheet('TK1-TS')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 14,
            'border': 1
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 16,
            'border': 0
        })
        
        normal_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Set column widths
        worksheet.set_column('A:A', 5)
        worksheet.set_column('B:B', 25)
        worksheet.set_column('C:E', 15)
        worksheet.set_column('F:F', 20)
        
        # Add header
        worksheet.merge_range('A1:F1', 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', title_format)
        worksheet.merge_range('A2:F2', 'Độc lập - Tự do - Hạnh phúc', title_format)
        worksheet.merge_range('A4:F4', 'TỜ KHAI', title_format)
        worksheet.merge_range('A5:F5', 'THAM GIA, ĐIỀU CHỈNH THÔNG TIN BẢO HIỂM XÃ HỘI, BẢO HIỂM Y TẾ', title_format)
        worksheet.merge_range('A6:F6', '(Áp dụng đối với người lao động tham gia BHXH, BHYT, BHTN)', title_format)
        
        # Add form content
        row = 8
        worksheet.merge_range(f'A{row}:F{row}', 'I. Thông tin người tham gia', header_format)
        row += 1
        
        # Employee information
        worksheet.merge_range(f'A{row}:B{row}', 'Họ và tên:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.name, normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Mã số BHXH:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.social_insurance_code or '', normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Ngày sinh:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.birthday.strftime('%d/%m/%Y') if employee.birthday else '', normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Giới tính:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', dict(employee._fields['gender'].selection).get(employee.gender) if employee.gender else '', normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Số CMND/CCCD:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.identification_id or '', normal_format)
        row += 1
        
        # Company information
        row += 2
        worksheet.merge_range(f'A{row}:F{row}', 'II. Thông tin đơn vị', header_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Tên đơn vị:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', company.name, normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Mã số đơn vị:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', company.company_registry or '', normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Địa chỉ:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', company.street or '', normal_format)
        row += 1
        
        # Signature section
        row += 2
        date_str = datetime.now().strftime('Ngày %d tháng %m năm %Y')
        worksheet.merge_range(f'D{row}:F{row}', date_str, workbook.add_format({'align': 'center'}))
        row += 1
        
        worksheet.merge_range(f'A{row}:C{row}', 'Người kê khai', workbook.add_format({'align': 'center', 'bold': True}))
        worksheet.merge_range(f'D{row}:F{row}', 'Thủ trưởng đơn vị', workbook.add_format({'align': 'center', 'bold': True}))
        row += 1
        
        worksheet.merge_range(f'A{row}:C{row}', '(Ký, ghi rõ họ tên)', workbook.add_format({'align': 'center', 'italic': True}))
        worksheet.merge_range(f'D{row}:F{row}', '(Ký, ghi rõ họ tên, đóng dấu)', workbook.add_format({'align': 'center', 'italic': True}))
    
    def _generate_tk3_ts_excel(self, workbook):
        """Generate TK3-TS form Excel"""
        document = self.document_id
        employee = document.employee_id
        company = self.env.company
        
        # Create worksheet
        worksheet = workbook.add_worksheet('TK3-TS')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 14,
            'border': 1
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 16,
            'border': 0
        })
        
        normal_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Set column widths
        worksheet.set_column('A:A', 5)
        worksheet.set_column('B:B', 25)
        worksheet.set_column('C:E', 15)
        worksheet.set_column('F:F', 20)
        
        # Add header
        worksheet.merge_range('A1:F1', 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', title_format)
        worksheet.merge_range('A2:F2', 'Độc lập - Tự do - Hạnh phúc', title_format)
        worksheet.merge_range('A4:F4', 'TỜ KHAI', title_format)
        worksheet.merge_range('A5:F5', 'ĐIỀU CHỈNH THÔNG TIN BẢO HIỂM XÃ HỘI, BẢO HIỂM Y TẾ', title_format)
        worksheet.merge_range('A6:F6', '(Áp dụng đối với người lao động đã tham gia BHXH, BHYT)', title_format)
        
        # Add form content
        row = 8
        worksheet.merge_range(f'A{row}:F{row}', 'I. Thông tin người tham gia', header_format)
        row += 1
        
        # Employee information
        worksheet.merge_range(f'A{row}:B{row}', 'Họ và tên:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.name, normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Mã số BHXH:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.social_insurance_code or '', normal_format)
        row += 1
        
        # Information to be adjusted
        row += 2
        worksheet.merge_range(f'A{row}:F{row}', 'II. Thông tin điều chỉnh', header_format)
        row += 1
        
        adjustment_type = dict(document._fields['adjustment_type'].selection).get(document.adjustment_type) if document.adjustment_type else ''
        worksheet.merge_range(f'A{row}:B{row}', 'Loại điều chỉnh:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', adjustment_type, normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Thông tin cũ:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', document.old_value or '', normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Thông tin mới:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', document.new_value or '', normal_format)
        row += 1
        
        # Signature section
        row += 2
        date_str = datetime.now().strftime('Ngày %d tháng %m năm %Y')
        worksheet.merge_range(f'D{row}:F{row}', date_str, workbook.add_format({'align': 'center'}))
        row += 1
        
        worksheet.merge_range(f'A{row}:C{row}', 'Người kê khai', workbook.add_format({'align': 'center', 'bold': True}))
        worksheet.merge_range(f'D{row}:F{row}', 'Thủ trưởng đơn vị', workbook.add_format({'align': 'center', 'bold': True}))
        row += 1
        
        worksheet.merge_range(f'A{row}:C{row}', '(Ký, ghi rõ họ tên)', workbook.add_format({'align': 'center', 'italic': True}))
        worksheet.merge_range(f'D{row}:F{row}', '(Ký, ghi rõ họ tên, đóng dấu)', workbook.add_format({'align': 'center', 'italic': True}))
    
    def _generate_termination_excel(self, workbook):
        """Generate termination form Excel"""
        document = self.document_id
        employee = document.employee_id
        company = self.env.company
        
        # Create worksheet
        worksheet = workbook.add_worksheet('Chấm dứt tham gia')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 14,
            'border': 1
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 16,
            'border': 0
        })
        
        normal_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Set column widths
        worksheet.set_column('A:A', 5)
        worksheet.set_column('B:B', 25)
        worksheet.set_column('C:E', 15)
        worksheet.set_column('F:F', 20)
        
        # Add header
        worksheet.merge_range('A1:F1', 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', title_format)
        worksheet.merge_range('A2:F2', 'Độc lập - Tự do - Hạnh phúc', title_format)
        worksheet.merge_range('A4:F4', 'THÔNG BÁO', title_format)
        worksheet.merge_range('A5:F5', 'CHẤM DỨT THAM GIA BẢO HIỂM XÃ HỘI, BẢO HIỂM Y TẾ', title_format)
        worksheet.merge_range('A6:F6', '(Áp dụng đối với người lao động chấm dứt tham gia BHXH, BHYT)', title_format)
        
        # Add form content
        row = 8
        worksheet.merge_range(f'A{row}:F{row}', 'I. Thông tin người tham gia', header_format)
        row += 1
        
        # Employee information
        worksheet.merge_range(f'A{row}:B{row}', 'Họ và tên:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.name, normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Mã số BHXH:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.social_insurance_code or '', normal_format)
        row += 1
        
        # Termination information
        row += 2
        worksheet.merge_range(f'A{row}:F{row}', 'II. Thông tin chấm dứt tham gia', header_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Ngày chấm dứt:', normal_format)
        termination_date = document.date or datetime.now().date()
        worksheet.merge_range(f'C{row}:F{row}', termination_date.strftime('%d/%m/%Y'), normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Lý do chấm dứt:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', document.notes or '', normal_format)
        row += 1
        
        # Signature section
        row += 2
        date_str = datetime.now().strftime('Ngày %d tháng %m năm %Y')
        worksheet.merge_range(f'D{row}:F{row}', date_str, workbook.add_format({'align': 'center'}))
        row += 1
        
        worksheet.merge_range(f'D{row}:F{row}', 'Thủ trưởng đơn vị', workbook.add_format({'align': 'center', 'bold': True}))
        row += 1
        
        worksheet.merge_range(f'D{row}:F{row}', '(Ký, ghi rõ họ tên, đóng dấu)', workbook.add_format({'align': 'center', 'italic': True}))
    
    def _generate_unemployment_excel(self, workbook):
        """Generate unemployment form Excel"""
        document = self.document_id
        employee = document.employee_id
        company = self.env.company
        
        # Create worksheet
        worksheet = workbook.add_worksheet('Trợ cấp thất nghiệp')
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 14,
            'border': 1
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 16,
            'border': 0
        })
        
        normal_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1
        })
        
        # Set column widths
        worksheet.set_column('A:A', 5)
        worksheet.set_column('B:B', 25)
        worksheet.set_column('C:E', 15)
        worksheet.set_column('F:F', 20)
        
        # Add header
        worksheet.merge_range('A1:F1', 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', title_format)
        worksheet.merge_range('A2:F2', 'Độc lập - Tự do - Hạnh phúc', title_format)
        worksheet.merge_range('A4:F4', 'ĐỀ NGHỊ', title_format)
        worksheet.merge_range('A5:F5', 'HƯỞNG TRỢ CẤP THẤT NGHIỆP', title_format)
        
        # Add form content
        row = 8
        worksheet.merge_range(f'A{row}:F{row}', 'I. Thông tin người lao động', header_format)
        row += 1
        
        # Employee information
        worksheet.merge_range(f'A{row}:B{row}', 'Họ và tên:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.name, normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Mã số BHXH:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.social_insurance_code or '', normal_format)
        row += 1
        
        worksheet.merge_range(f'A{row}:B{row}', 'Số CMND/CCCD:', normal_format)
        worksheet.merge_range(f'C{row}:F{row}', employee.identification_id or '', normal_format)
        row += 1
        
        if employee.address_home_id:
            address = employee.address_home_id
            address_str = ', '.join(filter(None, [address.street, address.city, address.state_id.name, address.country_id.name]))
            worksheet.merge_range(f'A{row}:B{row}', 'Địa chỉ liên hệ:', normal_format)
            worksheet.merge_range(f'C{row}:F{row}', address_str, normal_format)
            row += 1
        
        # Employment information
        row += 2
        worksheet.merge_range(f'A{row}:F{row}', 'II. Thông tin việc làm và thời gian đóng bảo hiểm thất nghiệp', header_format)
        row += 1
        
        contract = self.env['hr.contract'].search([('employee_id', '=', employee.id), ('state', '=', 'close')], limit=1, order='date_end desc')
        
        if contract:
            worksheet.merge_range(f'A{row}:B{row}', 'Ngày bắt đầu làm việc:', normal_format)
            worksheet.merge_range(f'C{row}:F{row}', contract.date_start.strftime('%d/%m/%Y'), normal_format)
            row += 1
            
            worksheet.merge_range(f'A{row}:B{row}', 'Ngày chấm dứt làm việc:', normal_format)
            worksheet.merge_range(f'C{row}:F{row}', contract.date_end.strftime('%d/%m/%Y'), normal_format)
            row += 1
        
        # Get BHTN insurance
        bhtn_insurance = self.env['hr.insurance'].search([
            ('employee_id', '=', employee.id),
            ('insurance_type', '=', 'bhtn'),
            ('state', '=', 'active')
        ], limit=1)
        
        if bhtn_insurance:
            worksheet.merge_range(f'A{row}:B{row}', 'Thời gian đóng BHTN:', normal_format)
            
            # Calculate months of BHTN contribution
            bhtn_histories = self.env['social.insurance.history'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'paid'),
                ('bhtn_employee_amount', '>', 0)
            ])
            months_count = len(bhtn_histories)
            
            worksheet.merge_range(f'C{row}:F{row}', f"{months_count} tháng", normal_format)
            row += 1
        
        # Signature section
        row += 2
        date_str = datetime.now().strftime('Ngày %d tháng %m năm %Y')
        worksheet.merge_range(f'D{row}:F{row}', date_str, workbook.add_format({'align': 'center'}))
        row += 1
        
        worksheet.merge_range(f'A{row}:C{row}', 'Xác nhận của đơn vị', workbook.add_format({'align': 'center', 'bold': True}))
        worksheet.merge_range(f'D{row}:F{row}', 'Người đề nghị', workbook.add_format({'align': 'center', 'bold': True}))
        row += 1
        
        worksheet.merge_range(f'A{row}:C{row}', '(Ký, ghi rõ họ tên, đóng dấu)', workbook.add_format({'align': 'center', 'italic': True}))
        worksheet.merge_range(f'D{row}:F{row}', '(Ký, ghi rõ họ tên)', workbook.add_format({'align': 'center', 'italic': True})) 