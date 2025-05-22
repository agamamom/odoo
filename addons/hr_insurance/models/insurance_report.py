# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import base64
import csv
import io
import xlsxwriter


class InsuranceCostReport(models.Model):
    _name = 'insurance.cost.report'
    _description = 'Insurance Cost Report'
    _order = 'date_from desc, id desc'
    _inherit = ['mail.thread']

    name = fields.Char(string='Tên báo cáo', required=True, tracking=True)
    date_from = fields.Date(string='Từ ngày', required=True, tracking=True)
    date_to = fields.Date(string='Đến ngày', required=True, tracking=True)
    
    # Bỏ các fields không tồn tại 
    related_document_model = fields.Char(string='Related Document Model', store=False, compute="_compute_dummy")
    related_document_id = fields.Integer(string='Related Document ID', store=False, compute="_compute_dummy")
    
    @api.depends('name')
    def _compute_dummy(self):
        """Hàm tính toán giả để hỗ trợ các trường dummy"""
        for record in self:
            record.related_document_model = False
            record.related_document_id = False
    
    report_type = fields.Selection([
        ('department', 'Theo phòng ban'),
        ('company', 'Toàn công ty')
    ], string='Loại báo cáo', default='company', required=True, tracking=True)
    
    department_ids = fields.Many2many('hr.department', string='Phòng ban', 
                                     help='Chọn phòng ban cần tạo báo cáo. Để trống nếu tạo báo cáo toàn công ty.')
    
    include_unpaid = fields.Boolean(string='Bao gồm chưa đóng', default=True, 
                                   help='Bao gồm cả các khoản chưa được đóng trong kỳ báo cáo')
    
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Người tạo báo cáo', default=lambda self: self.env.user)
    
    # Chi tiết phát sinh
    line_ids = fields.One2many('insurance.cost.report.line', 'report_id', string='Chi tiết báo cáo')
    
    # Phân tích tiến độ thanh toán
    payment_timeline_ids = fields.One2many('insurance.payment.timeline', 'report_id', string='Tiến độ đóng BHXH')
    
    # Tổng kết theo loại bảo hiểm
    total_bhxh = fields.Float(string='Tổng BHXH', compute='_compute_totals', store=True)
    total_bhyt = fields.Float(string='Tổng BHYT', compute='_compute_totals', store=True)
    total_bhtn = fields.Float(string='Tổng BHTN', compute='_compute_totals', store=True)
    
    # Tổng kết theo bên đóng
    total_company = fields.Float(string='Công ty đóng', compute='_compute_totals', store=True)
    total_employee = fields.Float(string='Nhân viên đóng', compute='_compute_totals', store=True)
    grand_total = fields.Float(string='Tổng cộng', compute='_compute_totals', store=True)
    
    # Tiền phạt, phát sinh
    total_late_fee = fields.Float(string='Phí truy thu/phạt', compute='_compute_totals', store=True)
    
    # Quyền lợi nhận được
    total_benefit_received = fields.Float(string='Quyền lợi đã nhận', compute='_compute_benefits', store=True)
    
    # Các chỉ số phân tích xu hướng
    monthly_trend = fields.Float(string='Xu hướng theo tháng (%)', compute='_compute_trends', store=True)
    quarterly_comparison = fields.Float(string='So sánh quý (%)', compute='_compute_trends', store=True)
    yearly_growth = fields.Float(string='Tăng trưởng năm (%)', compute='_compute_trends', store=True)
    
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('generated', 'Đã tạo'),
        ('done', 'Hoàn thành')
    ], string='Trạng thái', default='draft', tracking=True)
    
    # Phân tích tỷ lệ
    total_employees = fields.Integer(string='Tổng số nhân viên', compute='_compute_statistics', store=True)
    insured_employees = fields.Integer(string='SL nhân viên tham gia BHXH', compute='_compute_statistics', store=True)
    late_payment_employees = fields.Integer(string='SL nhân viên truy đóng', compute='_compute_statistics', store=True)
    violation_employees = fields.Integer(string='SL nhân viên vi phạm', compute='_compute_statistics', store=True)
    new_registrations = fields.Integer(string='Đăng ký mới trong kỳ', compute='_compute_dynamics', store=True)
    terminated_insurances = fields.Integer(string='Chấm dứt BH trong kỳ', compute='_compute_dynamics', store=True)
    
    participation_rate = fields.Float(string='Tỷ lệ tham gia (%)', compute='_compute_statistics', store=True)
    late_payment_rate = fields.Float(string='Tỷ lệ truy đóng (%)', compute='_compute_statistics', store=True)
    violation_rate = fields.Float(string='Tỷ lệ vi phạm (%)', compute='_compute_statistics', store=True)
    
    # File export
    export_data = fields.Binary(string='Dữ liệu xuất', attachment=True)
    export_filename = fields.Char(string='Tên file')
    
    @api.depends('line_ids', 'line_ids.bhxh_amount', 'line_ids.bhyt_amount', 'line_ids.bhtn_amount',
                'line_ids.employee_amount', 'line_ids.company_amount', 'line_ids.late_fee_amount')
    def _compute_totals(self):
        for record in self:
            record.total_bhxh = sum(record.line_ids.mapped('bhxh_amount'))
            record.total_bhyt = sum(record.line_ids.mapped('bhyt_amount'))
            record.total_bhtn = sum(record.line_ids.mapped('bhtn_amount'))
            record.total_company = sum(record.line_ids.mapped('company_amount'))
            record.total_employee = sum(record.line_ids.mapped('employee_amount'))
            record.total_late_fee = sum(record.line_ids.mapped('late_fee_amount'))
            record.grand_total = record.total_company + record.total_employee + record.total_late_fee
    
    @api.depends('date_from', 'date_to')
    def _compute_benefits(self):
        for record in self:
            # Kiểm tra nếu chưa có ngày tháng
            if not record.date_from or not record.date_to:
                record.total_benefit_received = 0
                continue
                
            # Tính tổng quyền lợi đã nhận trong kỳ báo cáo
            benefits = record.env['social.insurance.benefit'].search([
                ('payment_date', '>=', record.date_from),
                ('payment_date', '<=', record.date_to),
                ('state', '=', 'paid')
            ])
            
            # Lọc theo phòng ban nếu báo cáo theo phòng ban
            if record.report_type == 'department' and record.department_ids:
                employee_ids = record.env['hr.employee'].search([
                    ('department_id', 'in', record.department_ids.ids)
                ]).ids
                benefits = benefits.filtered(lambda b: b.employee_id.id in employee_ids)
                
            record.total_benefit_received = sum(benefits.mapped('benefit_amount'))
    
    @api.depends('date_from', 'date_to')
    def _compute_trends(self):
        for record in self:
            # Tránh lỗi nếu date_from hoặc date_to chưa được nhập
            if not record.date_from or not record.date_to:
                record.monthly_trend = 0
                record.quarterly_comparison = 0
                record.yearly_growth = 0
                continue
                
            # Tính xu hướng theo tháng
            last_month_start = record.date_from - relativedelta(months=1)
            last_month_end = record.date_to - relativedelta(months=1)
            
            # Tìm báo cáo tháng trước (nếu có)
            previous_monthly_report = self.env['insurance.cost.report'].search([
                ('date_from', '=', last_month_start),
                ('date_to', '=', last_month_end),
                ('report_type', '=', record.report_type),
                ('state', 'in', ['generated', 'done'])
            ], limit=1)
            
            if previous_monthly_report:
                if previous_monthly_report.grand_total:
                    record.monthly_trend = ((record.grand_total - previous_monthly_report.grand_total) / 
                                          previous_monthly_report.grand_total) * 100
                else:
                    record.monthly_trend = 100  # Tăng 100% nếu kỳ trước bằng 0
            else:
                record.monthly_trend = 0
            
            # Tính xu hướng theo quý
            last_quarter_start = record.date_from - relativedelta(months=3)
            last_quarter_end = record.date_to - relativedelta(months=3)
            
            previous_quarterly_report = self.env['insurance.cost.report'].search([
                ('date_from', '=', last_quarter_start),
                ('date_to', '=', last_quarter_end),
                ('report_type', '=', record.report_type),
                ('state', 'in', ['generated', 'done'])
            ], limit=1)
            
            if previous_quarterly_report:
                if previous_quarterly_report.grand_total:
                    record.quarterly_comparison = ((record.grand_total - previous_quarterly_report.grand_total) / 
                                                previous_quarterly_report.grand_total) * 100
                else:
                    record.quarterly_comparison = 100
            else:
                record.quarterly_comparison = 0
            
            # Tính xu hướng theo năm
            last_year_start = record.date_from - relativedelta(years=1)
            last_year_end = record.date_to - relativedelta(years=1)
            
            previous_yearly_report = self.env['insurance.cost.report'].search([
                ('date_from', '=', last_year_start),
                ('date_to', '=', last_year_end),
                ('report_type', '=', record.report_type),
                ('state', 'in', ['generated', 'done'])
            ], limit=1)
            
            if previous_yearly_report:
                if previous_yearly_report.grand_total:
                    record.yearly_growth = ((record.grand_total - previous_yearly_report.grand_total) / 
                                          previous_yearly_report.grand_total) * 100
                else:
                    record.yearly_growth = 100
            else:
                record.yearly_growth = 0
    
    @api.depends('date_from', 'date_to', 'report_type', 'department_ids')
    def _compute_dynamics(self):
        for record in self:
            # Kiểm tra nếu chưa có ngày tháng
            if not record.date_from or not record.date_to:
                record.new_registrations = 0
                record.terminated_insurances = 0
                continue
                
            domain = [
                ('date_from', '>=', record.date_from),
                ('date_from', '<=', record.date_to),
                ('insurance_type', 'in', ['bhxh', 'bhyt', 'bhtn']),
            ]
            
            # Thêm điều kiện phòng ban nếu báo cáo theo phòng ban
            if record.report_type == 'department' and record.department_ids:
                employee_ids = record.env['hr.employee'].search([
                    ('department_id', 'in', record.department_ids.ids)
                ]).ids
                domain.append(('employee_id', 'in', employee_ids))
                
            # Đếm số lượng đăng ký mới
            record.new_registrations = record.env['hr.insurance'].search_count(domain)
            
            # Đếm số lượng chấm dứt
            domain_terminated = [
                ('date_to', '>=', record.date_from),
                ('date_to', '<=', record.date_to),
                ('state', '=', 'expired'),
                ('insurance_type', 'in', ['bhxh', 'bhyt', 'bhtn']),
            ]
            
            if record.report_type == 'department' and record.department_ids:
                domain_terminated.append(('employee_id', 'in', employee_ids))
                
            record.terminated_insurances = record.env['hr.insurance'].search_count(domain_terminated)
    
    @api.depends('line_ids', 'line_ids.employee_id', 'line_ids.has_late_payment', 'line_ids.has_violation')
    def _compute_statistics(self):
        for record in self:
            # Lấy danh sách tất cả nhân viên thuộc phạm vi báo cáo
            domain = []
            if record.report_type == 'department' and record.department_ids:
                domain.append(('department_id', 'in', record.department_ids.ids))
            
            all_employees = self.env['hr.employee'].search(domain)
            record.total_employees = len(all_employees)
            
            # Nhân viên tham gia BHXH
            insured_employee_ids = record.line_ids.mapped('employee_id').ids
            record.insured_employees = len(insured_employee_ids)
            
            # Nhân viên truy đóng
            late_payment_employees = record.line_ids.filtered(lambda l: l.has_late_payment).mapped('employee_id').ids
            record.late_payment_employees = len(late_payment_employees)
            
            # Nhân viên vi phạm
            violation_employees = record.line_ids.filtered(lambda l: l.has_violation).mapped('employee_id').ids
            record.violation_employees = len(violation_employees)
            
            # Tính tỷ lệ
            if record.total_employees:
                record.participation_rate = (record.insured_employees / record.total_employees) * 100
                record.late_payment_rate = (record.late_payment_employees / record.total_employees) * 100
                record.violation_rate = (record.violation_employees / record.total_employees) * 100
            else:
                record.participation_rate = 0
                record.late_payment_rate = 0
                record.violation_rate = 0
    
    def action_generate_report(self):
        """Tạo dữ liệu báo cáo dựa trên các thông số đã chọn"""
        self.ensure_one()
        
        # Xóa các dòng báo cáo cũ
        self.line_ids.unlink()
        self.payment_timeline_ids.unlink()
        
        # Tìm tất cả nhân viên thuộc phạm vi báo cáo
        employee_domain = []
        if self.report_type == 'department' and self.department_ids:
            employee_domain.append(('department_id', 'in', self.department_ids.ids))
        
        employees = self.env['hr.employee'].search(employee_domain)
        
        # Tạo dòng báo cáo cho mỗi nhân viên có bảo hiểm
        for employee in employees:
            # Kiểm tra nhân viên có bảo hiểm không
            insurance = self.env['hr.insurance'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'active'),
                '|', ('date_from', '<=', self.date_to),
                ('date_to', '>=', self.date_from)
            ], limit=1)
            
            if not insurance and not self.include_unpaid:
                continue
                
            # Tính toán số tiền đóng bảo hiểm trong kỳ
            bhxh_amount = 0
            bhyt_amount = 0
            bhtn_amount = 0
            employee_amount = 0
            company_amount = 0
            late_fee_amount = 0
            has_late_payment = False
            has_violation = False
            
            # Tìm lịch sử đóng bảo hiểm trong khoảng thời gian
            history_entries = self.env['social.insurance.history'].search([
                ('employee_id', '=', employee.id),
                ('payment_date', '>=', self.date_from),
                ('payment_date', '<=', self.date_to)
            ])
            
            for entry in history_entries:
                bhxh_amount += entry.bhxh_employee_amount + entry.bhxh_company_amount
                bhyt_amount += entry.bhyt_employee_amount + entry.bhyt_company_amount
                bhtn_amount += entry.bhtn_employee_amount + entry.bhtn_company_amount
                employee_amount += entry.bhxh_employee_amount + entry.bhyt_employee_amount + entry.bhtn_employee_amount
                company_amount += entry.bhxh_company_amount + entry.bhyt_company_amount + entry.bhtn_company_amount
            
            # Kiểm tra phí truy thu
            late_fees = self.env['social.insurance.late.fee'].search([
                ('employee_id', '=', employee.id),
                ('payment_date', '>=', self.date_from),
                ('payment_date', '<=', self.date_to),
                ('state', 'in', ['confirmed', 'paid'])
            ])
            
            if late_fees:
                has_late_payment = True
                late_fee_amount = sum(late_fees.mapped('total_payment'))
            
            # Kiểm tra các vi phạm (ví dụ: trường hợp nhân viên phải có BHXH nhưng không có)
            if not insurance and employee.contract_id and employee.contract_id.date_start and \
               (fields.Date.today() - employee.contract_id.date_start).days > 30:
                has_violation = True
            
            # Tạo dòng báo cáo
            vals = {
                'report_id': self.id,
                'employee_id': employee.id,
                'department_id': employee.department_id.id,
                'job_id': employee.job_id.id,
                'bhxh_amount': bhxh_amount,
                'bhyt_amount': bhyt_amount,
                'bhtn_amount': bhtn_amount,
                'employee_amount': employee_amount,
                'company_amount': company_amount,
                'late_fee_amount': late_fee_amount,
                'has_late_payment': has_late_payment,
                'has_violation': has_violation,
            }
            self.env['insurance.cost.report.line'].create(vals)
        
        # Tạo dữ liệu phân tích tiến độ đóng BHXH
        self._generate_payment_timeline()
        
        self.state = 'generated'
        return True
    
    def _generate_payment_timeline(self):
        """Tạo dữ liệu phân tích tiến độ đóng BHXH theo tháng"""
        # Tính số tháng trong khoảng thời gian báo cáo
        date_start = fields.Date.from_string(self.date_from)
        date_end = fields.Date.from_string(self.date_to)
        
        # Tạo timeline theo tháng
        current_date = date(date_start.year, date_start.month, 1)
        while current_date <= date_end:
            month_start = current_date
            if current_date.month == 12:
                month_end = date(current_date.year + 1, 1, 1) - relativedelta(days=1)
            else:
                month_end = date(current_date.year, current_date.month + 1, 1) - relativedelta(days=1)
            
            # Ngày đến hạn đóng BHXH là ngày cuối tháng + 10 ngày
            due_date = month_end + relativedelta(days=10)
            
            # Tìm tất cả các giao dịch thanh toán trong tháng
            domain = [
                ('month', '=', str(current_date.month)),
                ('year', '=', str(current_date.year))
            ]
            
            # Lọc theo phòng ban nếu cần
            if self.report_type == 'department' and self.department_ids:
                employee_ids = self.env['hr.employee'].search([
                    ('department_id', 'in', self.department_ids.ids)
                ]).ids
                domain.append(('employee_id', 'in', employee_ids))
            
            history_entries = self.env['social.insurance.history'].search(domain)
            
            # Tính tổng khoản phải đóng
            amount_due = sum(history_entries.mapped('total_amount'))
            
            # Tìm các khoản đã đóng
            paid_entries = history_entries.filtered(lambda h: h.state == 'paid')
            amount_paid = sum(paid_entries.mapped('total_amount'))
            
            # Xác định ngày thanh toán (ngày gần nhất)
            payment_date = False
            if paid_entries:
                payment_dates = paid_entries.mapped('payment_date')
                if payment_dates:
                    payment_date = max(payment_dates)
            
            # Tính số ngày trễ hạn
            days_late = 0
            if payment_date and payment_date > due_date:
                days_late = (payment_date - due_date).days
            elif not payment_date and fields.Date.today() > due_date:
                days_late = (fields.Date.today() - due_date).days
            
            # Xác định trạng thái thanh toán
            payment_status = 'not_paid'
            if amount_paid >= amount_due:
                payment_status = 'paid'
            elif amount_paid > 0:
                payment_status = 'partial'
            elif days_late > 0:
                payment_status = 'overdue'
            
            # Tạo bản ghi timeline
            period_name = f"{current_date.month}/{current_date.year}"
            self.env['insurance.payment.timeline'].create({
                'report_id': self.id,
                'period_name': period_name,
                'due_date': due_date,
                'payment_date': payment_date,
                'amount_due': amount_due,
                'amount_paid': amount_paid,
                'days_late': days_late,
                'payment_status': payment_status,
            })
            
            # Chuyển sang tháng tiếp theo
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)
    
    def action_export_data(self):
        """Xuất dữ liệu báo cáo sang file CSV để tích hợp với phần mềm kế toán"""
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_("Không có dữ liệu để xuất. Vui lòng tạo báo cáo trước."))
            
        # Chuẩn bị dữ liệu csv
        import csv
        import base64
        from io import StringIO
        
        output = StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_ALL, delimiter=',')
        
        # Tiêu đề
        header = [
            'Mã nhân viên', 'Tên nhân viên', 'Phòng ban', 'Vị trí', 
            'BHXH', 'BHYT', 'BHTN', 
            'Nhân viên đóng', 'Công ty đóng', 'Phí phạt/truy thu',
            'Tổng cộng', 'Truy đóng', 'Vi phạm'
        ]
        writer.writerow(header)
        
        # Dữ liệu
        for line in self.line_ids:
            row = [
                line.employee_id.barcode or '',
                line.employee_id.name,
                line.department_id.name or '',
                line.job_id.name or '',
                line.bhxh_amount,
                line.bhyt_amount,
                line.bhtn_amount,
                line.employee_amount,
                line.company_amount,
                line.late_fee_amount,
                line.total_amount,
                'Có' if line.has_late_payment else 'Không',
                'Có' if line.has_violation else 'Không',
            ]
            writer.writerow(row)
        
        # Thêm dòng tổng cộng
        total_row = [
            'TỔNG CỘNG', '', '', '',
            self.total_bhxh,
            self.total_bhyt,
            self.total_bhtn,
            self.total_employee,
            self.total_company,
            self.total_late_fee,
            self.grand_total,
            f"{self.late_payment_rate:.2f}%",
            f"{self.violation_rate:.2f}%"
        ]
        writer.writerow(total_row)
        
        # Lưu và kết thúc
        content = output.getvalue().encode('utf-8')
        filename = f"{self.name.replace(' ', '_')}_{fields.Date.today().strftime('%d%m%Y')}.csv"
        
        self.export_data = base64.b64encode(content)
        self.export_filename = filename
        self.state = 'done'
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'insurance.cost.report',
            'view_mode': 'form',
            'res_id': self.id,
            'views': [(False, 'form')],
            'target': 'current',
        }
    
    def action_export_accounting(self):
        """Xuất dữ liệu kế toán chuyên biệt cho phần mềm kế toán"""
        self.ensure_one()
        
        if not self.line_ids:
            raise UserError(_("Không có dữ liệu để xuất. Vui lòng tạo báo cáo trước."))
        
        # Tạo wizard xuất dữ liệu kế toán
        wizard = self.env['insurance.data.export.wizard'].create({
            'name': f"KTOAN_{self.name}_{fields.Date.today().strftime('%d%m%Y')}",
            'date_from': self.date_from,
            'date_to': self.date_to,
            'export_type': 'accounting',
            'file_format': 'xlsx',
        })
        
        return {
            'name': _('Xuất dữ liệu kế toán'),
            'view_mode': 'form',
            'res_model': 'insurance.data.export.wizard',
            'res_id': wizard.id,
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'default_report_id': self.id}
        }
    
    def action_view_graph(self):
        """Hiển thị biểu đồ phân tích"""
        self.ensure_one()
        return {
            'name': _('Biểu đồ phân tích'),
            'res_model': 'insurance.cost.report',
            'type': 'ir.actions.act_window',
            'view_mode': 'graph,pivot',
            'domain': [('id', '=', self.id)],
            'target': 'current',
        }
    
    def action_reset_to_draft(self):
        """Đặt lại báo cáo về trạng thái dự thảo"""
        self.state = 'draft'


class InsuranceCostReportLine(models.Model):
    _name = 'insurance.cost.report.line'
    _description = 'Insurance Cost Report Line'
    
    report_id = fields.Many2one('insurance.cost.report', string='Báo cáo', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    department_id = fields.Many2one('hr.department', string='Phòng ban')
    job_id = fields.Many2one('hr.job', string='Vị trí')
    
    # Bỏ các fields không tồn tại 
    related_document_model = fields.Char(string='Related Document Model', store=False, compute="_compute_dummy")
    related_document_id = fields.Integer(string='Related Document ID', store=False, compute="_compute_dummy")
    
    @api.depends('employee_id')
    def _compute_dummy(self):
        """Hàm tính toán giả để hỗ trợ các trường dummy"""
        for record in self:
            record.related_document_model = False
            record.related_document_id = False
    
    bhxh_amount = fields.Float(string='BHXH')
    bhyt_amount = fields.Float(string='BHYT')
    bhtn_amount = fields.Float(string='BHTN')
    
    employee_amount = fields.Float(string='Nhân viên đóng')
    company_amount = fields.Float(string='Công ty đóng')
    late_fee_amount = fields.Float(string='Phí phạt/truy thu')
    
    total_amount = fields.Float(string='Tổng cộng', compute='_compute_total', store=True)
    
    has_late_payment = fields.Boolean(string='Có truy đóng', default=False)
    has_violation = fields.Boolean(string='Có vi phạm', default=False)
    
    @api.depends('employee_amount', 'company_amount', 'late_fee_amount')
    def _compute_total(self):
        for record in self:
            record.total_amount = record.employee_amount + record.company_amount + record.late_fee_amount


class InsurancePaymentTimeline(models.Model):
    _name = 'insurance.payment.timeline'
    _description = 'Insurance Payment Timeline'
    _order = 'due_date desc'
    
    report_id = fields.Many2one('insurance.cost.report', string='Báo cáo', required=True, ondelete='cascade')
    period_name = fields.Char(string='Kỳ đóng', required=True)
    
    # Bỏ các fields không tồn tại 
    related_document_model = fields.Char(string='Related Document Model', store=False, compute="_compute_dummy")
    related_document_id = fields.Integer(string='Related Document ID', store=False, compute="_compute_dummy")
    
    @api.depends('period_name')
    def _compute_dummy(self):
        """Hàm tính toán giả để hỗ trợ các trường dummy"""
        for record in self:
            record.related_document_model = False
            record.related_document_id = False
    
    due_date = fields.Date(string='Ngày đến hạn')
    payment_date = fields.Date(string='Ngày đóng thực tế')
    days_late = fields.Integer(string='Số ngày trễ')
    amount_due = fields.Float(string='Số tiền phải đóng')
    amount_paid = fields.Float(string='Số tiền đã đóng')
    payment_status = fields.Selection([
        ('paid', 'Đã đóng đủ'),
        ('partial', 'Đóng một phần'),
        ('overdue', 'Trễ hạn'),
        ('not_paid', 'Chưa đóng')
    ], string='Trạng thái', default='not_paid') 