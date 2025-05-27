# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from itertools import groupby
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import xlsxwriter
import io
import base64

class HrPayrollReportTaxVietnam(models.TransientModel):
    _name = 'hr.payroll.report.tax.vietnam'
    _description = 'Báo cáo thuế TNCN Việt Nam'

    date_from = fields.Date(string='Từ ngày', required=True, default=lambda self: fields.Date.to_string((datetime.now() - timedelta(days=90)).replace(day=1)))
    date_to = fields.Date(string='Đến ngày', required=True, default=lambda self: fields.Date.to_string((datetime.now() - timedelta(days=30)).replace(day=1) - timedelta(days=1)))
    company_id = fields.Many2one('res.company', string='Công ty', required=True, default=lambda self: self.env.company)
    department_id = fields.Many2one('hr.department', string='Phòng ban')
    report_type = fields.Selection([
        ('05_ds_tncn', 'Mẫu 05/DS-TNCN'),
        ('bk_tncn', 'Bảng kê chi tiết TNCN'),
        ('qtt_tncn', 'Quyết toán TNCN'),
    ], string='Loại báo cáo', default='05_ds_tncn', required=True)
    employee_ids = fields.Many2many('hr.employee', string='Nhân viên', domain="[('company_id', '=', company_id)]")
    file_data = fields.Binary('File dữ liệu')
    file_name = fields.Char('Tên file')
    state = fields.Selection([('choose', 'Chọn'), ('get', 'Tải xuống')], default='choose')

    @api.onchange('company_id', 'department_id')
    def _onchange_filter(self):
        domain = [('company_id', '=', self.company_id.id)]
        if self.department_id:
            domain += [('department_id', '=', self.department_id.id)]
        return {'domain': {'employee_ids': domain}}

    def action_generate_report(self):
        self.ensure_one()
        
        # Tìm tất cả các phiếu lương trong khoảng thời gian
        domain = [
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', '=', 'done'),
            ('employee_id.company_id', '=', self.company_id.id),
        ]
        
        if self.department_id:
            domain += [('employee_id.department_id', '=', self.department_id.id)]
            
        if self.employee_ids:
            domain += [('employee_id', 'in', self.employee_ids.ids)]
            
        payslips = self.env['hr.payslip'].search(domain)
        
        if not payslips:
            raise UserError(_("Không tìm thấy phiếu lương nào trong khoảng thời gian đã chọn."))
        
        # Tạo báo cáo theo loại
        if self.report_type == '05_ds_tncn':
            return self._generate_05_ds_tncn_report(payslips)
        elif self.report_type == 'bk_tncn':
            return self._generate_bk_tncn_report(payslips)
        elif self.report_type == 'qtt_tncn':
            return self._generate_qtt_tncn_report(payslips)
    
    def _generate_05_ds_tncn_report(self, payslips):
        """
        Tạo báo cáo theo mẫu 05/DS-TNCN - Bảng kê khai thuế TNCN theo tháng
        """
        # Sắp xếp phiếu lương theo nhân viên và tháng
        payslips_by_employee = {}
        for payslip in payslips:
            employee = payslip.employee_id
            if employee not in payslips_by_employee:
                payslips_by_employee[employee] = []
            payslips_by_employee[employee].append(payslip)
        
        # Tạo file Excel
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Mẫu 05/DS-TNCN')
        
        # Định dạng
        header_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_size': 12})
        title_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 16})
        subtitle_format = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 13})
        date_format = workbook.add_format({'num_format': 'dd/mm/yyyy', 'align': 'center', 'border': 1})
        number_format = workbook.add_format({'num_format': '#,##0', 'align': 'right', 'border': 1})
        text_format = workbook.add_format({'align': 'left', 'border': 1})
        text_center_format = workbook.add_format({'align': 'center', 'border': 1})
        
        # Thiết lập độ rộng cột
        worksheet.set_column('A:A', 5)  # STT
        worksheet.set_column('B:B', 25)  # Họ và tên
        worksheet.set_column('C:C', 15)  # Mã số thuế
        worksheet.set_column('D:D', 16)  # CMND/CCCD
        worksheet.set_column('E:E', 15)  # Từ tháng
        worksheet.set_column('F:F', 15)  # Đến tháng
        worksheet.set_column('G:G', 18)  # Tổng thu nhập
        worksheet.set_column('H:H', 18)  # Thu nhập chịu thuế
        worksheet.set_column('I:I', 18)  # Số thuế TNCN
        
        # Tiêu đề
        row = 0
        worksheet.merge_range('A1:I1', 'CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM', title_format)
        worksheet.merge_range('A2:I2', 'Độc lập - Tự do - Hạnh phúc', subtitle_format)
        worksheet.merge_range('A4:I4', 'DANH SÁCH CÁ NHÂN NHẬN THU NHẬP', title_format)
        worksheet.merge_range('A5:I5', f'Từ ngày {self.date_from.strftime("%d/%m/%Y")} đến ngày {self.date_to.strftime("%d/%m/%Y")}', subtitle_format)

        row = 7
        worksheet.write(row, 0, 'Đơn vị:', workbook.add_format({'bold': True}))
        worksheet.merge_range(f'B{row+1}:E{row+1}', self.company_id.name, workbook.add_format({'bold': True}))
        worksheet.write(row+1, 0, 'MST:', workbook.add_format({'bold': True}))
        worksheet.merge_range(f'B{row+2}:E{row+2}', self.company_id.vat or '', workbook.add_format({'bold': True}))
        
        # Header
        row = 10
        headers = [
            'STT', 'Họ và tên', 'Mã số thuế', 'Số CMND/CCCD', 'Từ tháng', 'Đến tháng', 
            'Tổng thu nhập', 'Thu nhập chịu thuế', 'Số thuế TNCN'
        ]
        
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        
        # Dữ liệu
        row += 1
        stt = 1
        for employee, emp_payslips in payslips_by_employee.items():
            min_date = min(emp_payslips, key=lambda p: p.date_from).date_from
            max_date = max(emp_payslips, key=lambda p: p.date_to).date_to
            
            total_gross = 0
            total_taxable = 0
            total_pit = 0
            
            for payslip in emp_payslips:
                # Tìm các khoản tính thuế
                gross_rule = payslip.line_ids.filtered(lambda l: l.code == 'VN_TOTAL_GROSS')
                taxable_rule = payslip.line_ids.filtered(lambda l: l.code == 'VN_TAXABLE')
                pit_rule = payslip.line_ids.filtered(lambda l: l.code == 'VN_PIT_TAX')
                
                if gross_rule:
                    total_gross += gross_rule.total
                if taxable_rule:
                    total_taxable += taxable_rule.total
                if pit_rule:
                    total_pit += abs(pit_rule.total)
            
            # Chỉ hiển thị nhân viên có thu nhập
            if total_gross > 0:
                # STT
                worksheet.write(row, 0, stt, text_center_format)
                # Họ và tên
                worksheet.write(row, 1, employee.name, text_format)
                # Mã số thuế
                worksheet.write(row, 2, employee.personal_tax_code or '', text_center_format)
                # CMND/CCCD
                worksheet.write(row, 3, employee.identification_id or '', text_center_format)
                # Từ tháng
                worksheet.write(row, 4, min_date.strftime('%m/%Y'), text_center_format)
                # Đến tháng
                worksheet.write(row, 5, max_date.strftime('%m/%Y'), text_center_format)
                # Tổng thu nhập
                worksheet.write(row, 6, total_gross, number_format)
                # Thu nhập chịu thuế
                worksheet.write(row, 7, total_taxable, number_format)
                # Số thuế TNCN
                worksheet.write(row, 8, total_pit, number_format)
                
                row += 1
                stt += 1
        
        # Tổng cộng
        worksheet.merge_range(f'A{row+1}:F{row+1}', 'Tổng cộng:', workbook.add_format({'bold': True, 'align': 'center', 'border': 1}))
        worksheet.write_formula(row, 6, f'=SUM(G12:G{row})', workbook.add_format({'bold': True, 'num_format': '#,##0', 'align': 'right', 'border': 1}))
        worksheet.write_formula(row, 7, f'=SUM(H12:H{row})', workbook.add_format({'bold': True, 'num_format': '#,##0', 'align': 'right', 'border': 1}))
        worksheet.write_formula(row, 8, f'=SUM(I12:I{row})', workbook.add_format({'bold': True, 'num_format': '#,##0', 'align': 'right', 'border': 1}))
        
        # Chữ ký
        row += 3
        worksheet.merge_range(f'A{row+1}:C{row+1}', '', workbook.add_format({'align': 'center'}))
        worksheet.merge_range(f'G{row+1}:I{row+1}', 'Ngày ... tháng ... năm ...', workbook.add_format({'align': 'center'}))
        worksheet.merge_range(f'G{row+2}:I{row+2}', 'NGƯỜI LẬP BIỂU', workbook.add_format({'bold': True, 'align': 'center'}))
        worksheet.merge_range(f'G{row+3}:I{row+3}', '(Ký, ghi rõ họ tên)', workbook.add_format({'italic': True, 'align': 'center'}))
        
        workbook.close()
        
        # Lưu file
        self.write({
            'file_data': base64.encodebytes(output.getvalue()),
            'file_name': f'Mau_05_DS_TNCN_{self.date_from.strftime("%d%m%Y")}_{self.date_to.strftime("%d%m%Y")}.xlsx',
            'state': 'get',
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.report.tax.vietnam',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'new',
        }
    
    def _generate_bk_tncn_report(self, payslips):
        """
        Tạo bảng kê chi tiết thu nhập cá nhân
        """
        # TODO: Implement chi tiết TNCN report
        raise UserError(_("Chức năng này đang được phát triển."))
    
    def _generate_qtt_tncn_report(self, payslips):
        """
        Tạo báo cáo quyết toán thuế thu nhập cá nhân
        """
        # TODO: Implement quyết toán TNCN report
        raise UserError(_("Chức năng này đang được phát triển.")) 