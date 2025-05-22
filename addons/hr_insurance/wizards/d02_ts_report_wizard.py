# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import date, datetime
import base64
import io
try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class D02TsReportWizard(models.TransientModel):
    _name = 'hr_insurance.d02_ts_report_wizard'
    _description = 'D02-TS Report Wizard'

    company_id = fields.Many2one('res.company', string='Công ty', required=True, default=lambda self: self.env.company)
    date_from = fields.Date(string='Từ ngày', required=True, default=lambda self: date(date.today().year, date.today().month, 1))
    date_to = fields.Date(string='Đến ngày', required=True, default=lambda self: date.today())
    include_expired = fields.Boolean(string='Bao gồm bảo hiểm hết hạn', default=False)
    department_ids = fields.Many2many('hr.department', string='Phòng ban')
    insurance_type = fields.Selection([
        ('all', 'Tất cả'),
        ('bhxh', 'BHXH'),
        ('bhyt', 'BHYT'),
        ('bhtn', 'BHTN')
    ], string='Loại bảo hiểm', default='all', required=True)
    
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
    
    def _get_insurance_domain(self):
        domain = [
            ('date_from', '<=', self.date_to),
            '|',
            ('date_to', '>=', self.date_from),
            ('date_to', '=', False)
        ]
        
        if not self.include_expired:
            domain.append(('state', '=', 'active'))
        else:
            domain.append(('state', 'in', ['active', 'expired']))
        
        if self.department_ids:
            domain.append(('employee_id.department_id', 'in', self.department_ids.ids))
            
        if self.insurance_type != 'all':
            domain.append(('insurance_type', '=', self.insurance_type))
            
        return domain
    
    def _get_report_data(self):
        insurances = self.env['hr.insurance'].search(self._get_insurance_domain())
        
        if not insurances:
            raise UserError(_("Không tìm thấy dữ liệu bảo hiểm cho các điều kiện đã chọn."))
        
        insurance_data = []
        for insurance in insurances:
            insurance_data.append({
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
                'amount': insurance.amount,
                'employee_contribution': insurance.employee_contribution,
                'company_contribution': insurance.company_contribution,
                'total_contribution': insurance.total_contribution,
                'salary_base': insurance.salary_base,
                'employee_rate': insurance.policy_id.employee_rate if insurance.policy_id else 0,
                'company_rate': insurance.policy_id.company_rate if insurance.policy_id else 0
            })
        
        # Tính tổng số
        total_salary_base = sum(item['salary_base'] for item in insurance_data)
        total_employee = sum(item['employee_contribution'] for item in insurance_data)
        total_company = sum(item['company_contribution'] for item in insurance_data)
        total_all = sum(item['total_contribution'] for item in insurance_data)
        
        return {
            'company': self.company_id,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'insurance_type': self.insurance_type,
            'department_ids': self.department_ids,
            'insurance_records': insurance_data,
            'total_records': len(insurance_data),
            'total_salary_base': total_salary_base,
            'total_employee': total_employee,
            'total_company': total_company,
            'total_all': total_all,
        }
    
    def action_print_pdf(self):
        self.ensure_one()
        
        data = {
            'ids': self.ids,
            'model': self._name,
            'form': self._get_report_data(),
        }
        
        return self.env.ref('hr_insurance.action_d02_ts_report').report_action(self, data=data)
    
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
        
        total_format = workbook.add_format({
            'bold': True,
            'align': 'right',
            'valign': 'vcenter',
            'font_size': 11,
            'num_format': '#,##0',
            'border': 1
        })
        
        # Worksheet
        sheet = workbook.add_worksheet('D02-TS')
        sheet.set_column('A:A', 5)
        sheet.set_column('B:C', 20)
        sheet.set_column('D:H', 15)
        sheet.set_column('I:L', 18)
        
        # Title
        sheet.merge_range('A1:L1', 'BÁO CÁO TÌNH HÌNH SỬ DỤNG LAO ĐỘNG VÀ ĐÓNG BẢO HIỂM XÃ HỘI', title_format)
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
            'Lương đóng BH', 'NV đóng (%)', 'Công ty đóng (%)', 'NV đóng', 'Công ty đóng', 'Tổng cộng'
        ]
        
        for col, header in enumerate(headers):
            sheet.write(6, col, header, header_format)
        
        # Data
        row = 7
        for idx, record in enumerate(data['insurance_records']):
            sheet.write(row, 0, idx + 1, text_format)
            sheet.write(row, 1, record['employee_code'], text_format)
            sheet.write(row, 2, record['employee_name'], text_format)
            sheet.write(row, 3, record['social_insurance_code'], text_format)
            sheet.write(row, 4, record['identification_id'], text_format)
            sheet.write(row, 5, record['department'], text_format)
            sheet.write(row, 6, record['salary_base'], number_format)
            sheet.write(row, 7, record['employee_rate'], number_format)
            sheet.write(row, 8, record['company_rate'], number_format)
            sheet.write(row, 9, record['employee_contribution'], number_format)
            sheet.write(row, 10, record['company_contribution'], number_format)
            sheet.write(row, 11, record['total_contribution'], number_format)
            row += 1
        
        # Totals
        sheet.merge_range(f'A{row+1}:F{row+1}', 'TỔNG CỘNG', total_format)
        sheet.write(row, 6, data['total_salary_base'], total_format)
        sheet.write(row, 9, data['total_employee'], total_format)
        sheet.write(row, 10, data['total_company'], total_format)
        sheet.write(row, 11, data['total_all'], total_format)
        
        # Signatures
        sheet.merge_range(f'A{row+3}:F{row+3}', 'Người lập biểu', subtitle_format)
        sheet.merge_range(f'G{row+3}:L{row+3}', 'Giám đốc', subtitle_format)
        sheet.merge_range(f'A{row+4}:F{row+4}', '(Ký, ghi rõ họ tên)', info_format)
        sheet.merge_range(f'G{row+4}:L{row+4}', '(Ký, đóng dấu, ghi rõ họ tên)', info_format)
        
        workbook.close()
        xlsx_data = output.getvalue()
        
        # Save to wizard
        filename = f'D02-TS_{self.date_from.strftime("%d%m%Y")}_{self.date_to.strftime("%d%m%Y")}.xlsx'
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