# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date, datetime, timedelta
import base64
import io
try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class D03TsReportWizard(models.TransientModel):
    _name = 'hr_insurance.d03_ts_report_wizard'
    _description = 'D03-TS Report Wizard'

    company_id = fields.Many2one('res.company', string='Công ty', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string='Từ ngày', required=True, default=lambda self: date.today() - timedelta(days=30))
    date_to = fields.Date(string='Đến ngày', required=True, default=lambda self: date.today())
    department_ids = fields.Many2many('hr.department', string='Phòng ban')
    change_type = fields.Selection([
        ('all', 'Tất cả thay đổi'),
        ('new', 'Tham gia mới'),
        ('update', 'Thay đổi thông tin'),
        ('end', 'Kết thúc tham gia')
    ], string='Loại biến động', default='all', required=True)
    
    # Fields for the report file
    file_data = fields.Binary('File', readonly=True)
    file_name = fields.Char('File Name', readonly=True)
    state = fields.Selection([
        ('choose', 'choose'),
        ('get', 'get')
    ], default='choose')
    
    @api.onchange('date_from')
    def _onchange_date_from(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            self.date_to = self.date_from
    
    @api.onchange('date_to')
    def _onchange_date_to(self):
        if self.date_from and self.date_to and self.date_to < self.date_from:
            self.date_from = self.date_to
    
    def _get_changes_domain(self):
        # Tìm kiếm các bảo hiểm được tạo, cập nhật hoặc kết thúc trong khoảng thời gian
        base_domain = [
            '|', '|',
            # Bảo hiểm mới (date_from trong khoảng thời gian)
            '&', ('date_from', '>=', self.date_from), ('date_from', '<=', self.date_to),
            # Bảo hiểm kết thúc (date_to trong khoảng thời gian)
            '&', ('date_to', '>=', self.date_from), ('date_to', '<=', self.date_to),
            # Bảo hiểm có thay đổi trong khoảng thời gian (dựa trên write_date)
            '&', ('write_date', '>=', self.date_from), ('write_date', '<=', self.date_to)
        ]
        
        if self.department_ids:
            base_domain.append(('employee_id.department_id', 'in', self.department_ids.ids))
            
        if self.change_type == 'new':
            return ['&', ('date_from', '>=', self.date_from), ('date_from', '<=', self.date_to)]
        elif self.change_type == 'end':
            return ['&', ('date_to', '>=', self.date_from), ('date_to', '<=', self.date_to)]
        elif self.change_type == 'update':
            return ['&', '&', 
                   ('write_date', '>=', self.date_from), 
                   ('write_date', '<=', self.date_to),
                   '&', 
                   ('date_from', '<', self.date_from),
                   '|', ('date_to', '>', self.date_to), ('date_to', '=', False)]
        
        return base_domain
    
    def _get_change_type(self, insurance):
        """Xác định loại thay đổi của bảo hiểm"""
        if insurance.date_from >= self.date_from and insurance.date_from <= self.date_to:
            return 'new', 'Tham gia mới'
        elif insurance.date_to and insurance.date_to >= self.date_from and insurance.date_to <= self.date_to:
            return 'end', 'Kết thúc tham gia'
        else:
            return 'update', 'Thay đổi thông tin'
    
    def _get_report_data(self):
        insurances = self.env['hr.insurance'].search(self._get_changes_domain())
        
        if not insurances:
            raise UserError(_("Không tìm thấy thay đổi nào trong khoảng thời gian đã chọn."))
        
        change_data = []
        for insurance in insurances:
            change_type_code, change_type_name = self._get_change_type(insurance)
            if self.change_type != 'all' and self.change_type != change_type_code:
                continue
                
            change_data.append({
                'employee_id': insurance.employee_id.id,
                'employee_code': insurance.employee_id.barcode or '',
                'employee_name': insurance.employee_id.name,
                'identification_id': insurance.employee_id.identification_id or '',
                'department': insurance.employee_id.department_id.name or '',
                'job_title': insurance.employee_id.job_title or '',
                'social_insurance_code': insurance.employee_id.social_insurance_code or '',
                'insurance_code': insurance.social_insurance_code or '',
                'policy': insurance.policy_id.name,
                'insurance_type': dict(insurance._fields['insurance_type'].selection).get(insurance.insurance_type),
                'insurance_type_code': insurance.insurance_type,
                'date_from': insurance.date_from,
                'date_to': insurance.date_to,
                'state': dict(insurance._fields['state'].selection).get(insurance.state),
                'salary_base': insurance.salary_base,
                'change_type_code': change_type_code,
                'change_type_name': change_type_name,
                'change_date': insurance.date_from if change_type_code == 'new' else 
                               insurance.date_to if change_type_code == 'end' else
                               insurance.write_date.date(),
                'reason': insurance.notes or ''
            })
        
        # Tính tổng số
        total_new = len([c for c in change_data if c['change_type_code'] == 'new'])
        total_end = len([c for c in change_data if c['change_type_code'] == 'end'])
        total_update = len([c for c in change_data if c['change_type_code'] == 'update'])
        
        return {
            'company': self.company_id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'change_type': self.change_type,
            'department_ids': self.department_ids,
            'change_records': change_data,
            'total_records': len(change_data),
            'total_new': total_new,
            'total_end': total_end,
            'total_update': total_update,
        }
    
    def action_print_pdf(self):
        self.ensure_one()
        
        data = {
            'ids': self.ids,
            'model': self._name,
            'form': self._get_report_data(),
        }
        
        return self.env.ref('hr_insurance.action_d03_ts_report').report_action(self, data=data)
    
    def action_export_excel(self):
        self.ensure_one()
        
        if not xlsxwriter:
            raise UserError(_("Bạn cần cài đặt thư viện xlsxwriter để sử dụng tính năng này."))
        
        data = self._get_report_data()
        
        # Create Excel file
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Định dạng
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 11,
            'bg_color': '#D3D3D3',
            'border': 1
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
            'font_size': 13,
        })
        
        info_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'font_size': 11,
        })
        
        text_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'font_size': 11,
            'border': 1
        })
        
        number_format = workbook.add_format({
            'align': 'right',
            'valign': 'vcenter',
            'font_size': 11,
            'num_format': '#,##0',
            'border': 1
        })
        
        date_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 11,
            'num_format': 'dd/mm/yyyy',
            'border': 1
        })
        
        center_format = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'font_size': 11,
            'border': 1
        })
        
        # Worksheet
        sheet = workbook.add_worksheet('D03-TS')
        sheet.set_column('A:A', 5)
        sheet.set_column('B:C', 20)
        sheet.set_column('D:H', 15)
        sheet.set_column('I:K', 18)
        sheet.set_column('L:L', 30)
        
        # Title
        sheet.merge_range('A1:L1', 'BÁO CÁO THAY ĐỔI THÔNG TIN NGƯỜI THAM GIA BHXH', title_format)
        sheet.merge_range('A2:L2', f'Kỳ báo cáo: {self.date_from.strftime("%d/%m/%Y")} - {self.date_to.strftime("%d/%m/%Y")}', subtitle_format)
        
        # Company info
        sheet.merge_range('A3:C3', 'Đơn vị:', info_format)
        sheet.merge_range('D3:L3', data['company'].name, info_format)
        sheet.merge_range('A4:C4', 'Mã số thuế:', info_format)
        sheet.merge_range('D4:L4', data['company'].vat or '', info_format)
        sheet.merge_range('A5:C5', 'Địa chỉ:', info_format)
        sheet.merge_range('D5:L5', data['company'].street or '', info_format)
        
        # Header
        headers = [
            'STT', 'Mã NV', 'Họ và tên', 'Mã số BHXH', 'CMND/CCCD', 'Phòng ban',
            'Loại thay đổi', 'Ngày thay đổi', 'Loại bảo hiểm', 'Lương đóng BH', 'Trạng thái', 'Lý do thay đổi'
        ]
        
        for col, header in enumerate(headers):
            sheet.write(6, col, header, header_format)
        
        # Data
        row = 7
        for idx, record in enumerate(data['change_records']):
            sheet.write(row, 0, idx + 1, text_format)
            sheet.write(row, 1, record['employee_code'], text_format)
            sheet.write(row, 2, record['employee_name'], text_format)
            sheet.write(row, 3, record['social_insurance_code'], text_format)
            sheet.write(row, 4, record['identification_id'], text_format)
            sheet.write(row, 5, record['department'], text_format)
            sheet.write(row, 6, record['change_type_name'], text_format)
            sheet.write(row, 7, record['change_date'], date_format)
            sheet.write(row, 8, record['insurance_type'], text_format)
            sheet.write(row, 9, record['salary_base'], number_format)
            sheet.write(row, 10, record['state'], center_format)
            sheet.write(row, 11, record['reason'], text_format)
            row += 1
        
        # Summary
        sheet.merge_range(f'A{row+2}:L{row+2}', 'TỔNG HỢP', subtitle_format)
        sheet.merge_range(f'A{row+3}:F{row+3}', 'Tổng số biến động:', info_format)
        sheet.merge_range(f'G{row+3}:L{row+3}', str(data['total_records']), info_format)
        sheet.merge_range(f'A{row+4}:F{row+4}', 'Trong đó:', info_format)
        sheet.merge_range(f'A{row+5}:F{row+5}', '- Tham gia mới:', info_format)
        sheet.merge_range(f'G{row+5}:L{row+5}', str(data['total_new']), info_format)
        sheet.merge_range(f'A{row+6}:F{row+6}', '- Kết thúc tham gia:', info_format)
        sheet.merge_range(f'G{row+6}:L{row+6}', str(data['total_end']), info_format)
        sheet.merge_range(f'A{row+7}:F{row+7}', '- Thay đổi thông tin:', info_format)
        sheet.merge_range(f'G{row+7}:L{row+7}', str(data['total_update']), info_format)
        
        # Signatures
        sheet.merge_range(f'A{row+9}:F{row+9}', 'Người lập biểu', subtitle_format)
        sheet.merge_range(f'G{row+9}:L{row+9}', 'Giám đốc', subtitle_format)
        sheet.merge_range(f'A{row+10}:F{row+10}', '(Ký, ghi rõ họ tên)', info_format)
        sheet.merge_range(f'G{row+10}:L{row+10}', '(Ký, đóng dấu, ghi rõ họ tên)', info_format)
        
        workbook.close()
        xlsx_data = output.getvalue()
        
        # Save to wizard
        filename = f'D03-TS_{self.date_from.strftime("%d%m%Y")}_{self.date_to.strftime("%d%m%Y")}.xlsx'
        self.write({
            'state': 'get',
            'file_data': base64.b64encode(xlsx_data),
            'file_name': filename
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        } 