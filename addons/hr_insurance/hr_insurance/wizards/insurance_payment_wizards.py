# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
from datetime import date
import calendar


class InsurancePaymentWizard(models.TransientModel):
    _name = 'insurance.payment.wizard'
    _description = 'Insurance Payment Wizard'

    name = fields.Char(string='Mô tả', compute='_compute_name', store=True)
    payment_date = fields.Date(string='Ngày thanh toán', required=True, default=fields.Date.today)
    payment_method = fields.Selection([
        ('bank', 'Chuyển khoản'),
        ('cash', 'Tiền mặt'),
        ('payroll', 'Qua lương'),
        ('other', 'Khác')
    ], string='Phương thức thanh toán', required=True, default='bank')
    reference = fields.Char(string='Tham chiếu', help="Số chứng từ hoặc số tham chiếu thanh toán")
    payment_type = fields.Selection([
        ('employee', 'Phần nhân viên đóng'),
        ('company', 'Phần công ty đóng'),
        ('both', 'Cả hai')
    ], string='Loại thanh toán', required=True, default='both')
    month = fields.Selection([
        ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'),
        ('4', 'Tháng 4'), ('5', 'Tháng 5'), ('6', 'Tháng 6'),
        ('7', 'Tháng 7'), ('8', 'Tháng 8'), ('9', 'Tháng 9'),
        ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12')
    ], string='Tháng', required=True, default=lambda self: str(fields.Date.today().month))
    year = fields.Integer(string='Năm', required=True, default=lambda self: fields.Date.today().year)
    
    insurance_type = fields.Selection([
        ('bhxh', 'BHXH'),
        ('bhyt', 'BHYT'),
        ('bhtn', 'BHTN'),
        ('combined', 'Tổng hợp')
    ], string='Loại bảo hiểm', required=True, default='combined')
    
    line_ids = fields.One2many('insurance.payment.wizard.line', 'wizard_id', string='Chi tiết thanh toán')
    total_amount = fields.Float(string='Tổng tiền', compute='_compute_total_amount', store=True)
    notes = fields.Text(string='Ghi chú')
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)

    @api.depends('month', 'year', 'payment_type')
    def _compute_name(self):
        for wizard in self:
            month = wizard.month
            year = wizard.year
            payment_type = wizard.payment_type
            payment_type_names = {
                'employee': 'Phần nhân viên',
                'company': 'Phần công ty',
                'both': 'Cả hai'
            }
            wizard.name = f"Thanh toán BHXH {month}/{year} - {payment_type_names.get(payment_type, '')}"

    @api.depends('line_ids.amount')
    def _compute_total_amount(self):
        for wizard in self:
            wizard.total_amount = sum(line.amount for line in wizard.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        # Generate a unique name for the wizard based on month, year, and payment type
        for vals in vals_list:
            month = vals.get('month', str(date.today().month))
            year = vals.get('year', date.today().year)
            payment_type = vals.get('payment_type', 'both')
            payment_type_names = {
                'employee': 'Phần nhân viên',
                'company': 'Phần công ty',
                'both': 'Cả hai'
            }
            vals['name'] = f"Thanh toán BHXH {month}/{year} - {payment_type_names.get(payment_type)}"
        return super(InsurancePaymentWizard, self).create(vals_list)

    def action_confirm_payment(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Không có chi tiết thanh toán nào được chọn."))
            
        # Validate payment amount
        if self.total_amount <= 0:
            raise UserError(_("Tổng số tiền thanh toán phải lớn hơn 0."))
            
        # Create payment record
        payment_vals = {
            'name': self.name,
            'payment_date': self.payment_date,
            'payment_method': self.payment_method,
            'reference': self.reference,
            'payment_type': self.payment_type,
            'month': self.month,
            'year': self.year,
            'insurance_type': self.insurance_type,
            'payment_amount': self.total_amount,
            'notes': self.notes,
            'company_id': self.company_id.id,
            'state': 'draft',
        }
        
        payment = self.env['insurance.payment'].create(payment_vals)
        
        # Create payment lines
        payment_line_vals = []
        for line in self.line_ids:
            # Get salary base and other data from insurance
            salary_base = 0
            if line.insurance_id:
                salary_base = line.insurance_id.salary_base
                
            payment_line_vals.append({
                'payment_id': payment.id,
                'employee_id': line.employee_id.id,
                'insurance_id': line.insurance_id.id,
                'amount': line.amount,
                'salary_base': salary_base,
            })
            
        self.env['insurance.payment.line'].create(payment_line_vals)
        
        # Return the view of the created payment
        return {
            'name': _('Thanh toán bảo hiểm'),
            'type': 'ir.actions.act_window',
            'res_model': 'insurance.payment',
            'view_mode': 'form',
            'res_id': payment.id,
            'target': 'current',
        }
        

class InsurancePaymentWizardLine(models.TransientModel):
    _name = 'insurance.payment.wizard.line'
    _description = 'Insurance Payment Wizard Line'

    wizard_id = fields.Many2one('insurance.payment.wizard', string='Wizard')
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True)
    insurance_id = fields.Many2one('hr.insurance', string='Bảo hiểm', required=True,
                                   domain="[('employee_id', '=', employee_id), ('state', '=', 'active')]")
    amount = fields.Float(string='Số tiền', required=True)
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('paid', 'Đã thanh toán'),
        ('cancelled', 'Đã hủy')
    ], string='Trạng thái', default='draft')
    
    @api.onchange('insurance_id')
    def _onchange_insurance_id(self):
        if self.insurance_id:
            wizard = self.wizard_id
            if wizard.payment_type == 'employee':
                self.amount = self.insurance_id.employee_contribution
            elif wizard.payment_type == 'company':
                self.amount = self.insurance_id.company_contribution
            else:
                self.amount = self.insurance_id.total_contribution


class InsurancePaymentDifferenceWizard(models.TransientModel):
    _name = 'insurance.payment.difference.wizard'
    _description = 'Xử lý chênh lệch thanh toán bảo hiểm'

    payment_id = fields.Many2one(
        'insurance.payment', 
        string='Thanh toán', 
        required=True)
    
    difference_amount = fields.Float(
        string='Số tiền chênh lệch',
        readonly=True)
    
    reason = fields.Selection([
        ('adjustment', 'Điều chỉnh lương/mức đóng'),
        ('penalty', 'Phí phạt chậm đóng'),
        ('correction', 'Điều chỉnh kỳ trước'),
        ('other', 'Lý do khác')
    ], string='Lý do chênh lệch', required=True, default='other')
    
    notes = fields.Text(
        string='Ghi chú',
        required=True,
        help='Ghi rõ lý do chênh lệch')
    
    def action_confirm(self):
        self.ensure_one()
        if not self.notes:
            raise ValidationError(_('Vui lòng cung cấp ghi chú giải thích lý do chênh lệch.'))
        
        payment = self.payment_id
        
        # Cập nhật ghi chú với lý do chênh lệch
        reason_text = dict(self._fields['reason'].selection).get(self.reason)
        new_note = f"[Chênh lệch: {self.difference_amount:,.2f}] - {reason_text}: {self.notes}"
        
        if payment.notes:
            payment.notes = f"{payment.notes}\n\n{new_note}"
        else:
            payment.notes = new_note
            
        # Chuyển thanh toán sang trạng thái "Đã thanh toán"
        payment.state = 'paid'
        
        return {'type': 'ir.actions.act_window_close'}


class InsurancePaymentEmployeeWizard(models.TransientModel):
    _name = 'insurance.payment.employee.wizard'
    _description = 'Thêm nhân viên vào thanh toán bảo hiểm'

    payment_id = fields.Many2one(
        'insurance.payment', 
        string='Thanh toán', 
        required=True)
    
    department_id = fields.Many2one(
        'hr.department', 
        string='Phòng ban')
    
    employee_ids = fields.Many2many(
        'hr.employee', 
        string='Nhân viên',
        required=True,
        help='Chọn nhân viên để thêm vào thanh toán')
    
    include_with_insurance_only = fields.Boolean(
        string='Chỉ nhân viên có bảo hiểm', 
        default=True,
        help='Chỉ hiển thị nhân viên đã có bảo hiểm xã hội')
    
    @api.onchange('include_with_insurance_only', 'department_id')
    def _onchange_filters(self):
        domain = []
        
        # Lọc theo phòng ban
        if self.department_id:
            domain.append(('department_id', '=', self.department_id.id))
        
        # Lọc theo bảo hiểm
        if self.include_with_insurance_only:
            domain.append(('has_social_insurance', '=', True))
        
        # Lấy danh sách nhân viên đã có trong thanh toán
        if self.payment_id:
            existing_employees = self.env['insurance.payment.line'].search([
                ('payment_id', '=', self.payment_id.id)
            ]).mapped('employee_id.id')
            
            if existing_employees:
                domain.append(('id', 'not in', existing_employees))
        
        return {'domain': {'employee_ids': domain}}
    
    def action_add_employees(self):
        self.ensure_one()
        if not self.employee_ids:
            raise ValidationError(_('Vui lòng chọn ít nhất một nhân viên.'))
        
        payment = self.payment_id
        
        # Kiểm tra trạng thái thanh toán
        if payment.state not in ('draft', 'confirmed'):
            raise ValidationError(_('Chỉ có thể thêm nhân viên cho thanh toán ở trạng thái "Dự thảo" hoặc "Đã xác nhận".'))
        
        lines_to_create = []
        
        for employee in self.employee_ids:
            # Tìm bảo hiểm BHXH đang hoạt động của nhân viên
            insurance = self.env['hr.insurance'].search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'active'),
                ('insurance_type', '=', 'bhxh')
            ], limit=1)
            
            salary_base = 0
            
            # Nếu có bảo hiểm, sử dụng lương cơ bản từ bảo hiểm
            if insurance:
                salary_base = insurance.salary_base
            else:
                # Nếu không tìm thấy, sử dụng lương từ hợp đồng
                contract = self.env['hr.contract'].search([
                    ('employee_id', '=', employee.id),
                    ('state', '=', 'open')
                ], limit=1)
                if contract:
                    salary_base = contract.wage
            
            if salary_base <= 0:
                continue
                
            lines_to_create.append({
                'payment_id': payment.id,
                'employee_id': employee.id,
                'salary_base': salary_base,
            })
        
        # Tạo các dòng chi tiết thanh toán
        if lines_to_create:
            self.env['insurance.payment.line'].create(lines_to_create)
        
        # Refresh lại view
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
        
        
# Mở rộng chức năng report cho báo cáo bảo hiểm kết hợp với lịch sử thanh toán
class InsurancePaymentReport(models.AbstractModel):
    _name = 'insurance.payment.report'
    _description = 'Các chức năng báo cáo bảo hiểm với lịch sử thanh toán'
    
    @api.model
    def get_payment_history(self, from_date, to_date, insurance_type=None, department_id=None):
        """
        Lấy lịch sử thanh toán bảo hiểm trong khoảng thời gian
        
        :param from_date: Từ ngày
        :param to_date: Đến ngày
        :param insurance_type: Loại bảo hiểm ('bhxh', 'bhyt', 'bhtn', 'all')
        :param department_id: ID phòng ban
        :return: dict dữ liệu lịch sử thanh toán cho báo cáo
        """
        # Tìm các thanh toán BHXH trong khoảng thời gian
        domain = [
            ('payment_date', '>=', from_date),
            ('payment_date', '<=', to_date),
            ('state', 'in', ['paid', 'verified'])
        ]
        
        if insurance_type and insurance_type != 'all':
            domain.append(('insurance_type', 'in', [insurance_type, 'combined']))
            
        if department_id:
            # Lấy nhân viên thuộc phòng ban
            employees = self.env['hr.employee'].search([('department_id', '=', department_id)])
            # Lấy các thanh toán có dòng chi tiết chứa nhân viên thuộc phòng ban
            payment_ids = self.env['insurance.payment.line'].search([
                ('employee_id', 'in', employees.ids)
            ]).mapped('payment_id.id')
            if payment_ids:
                domain.append(('id', 'in', payment_ids))
            else:
                domain.append(('id', '=', False))
        
        payments = self.env['insurance.payment'].search(domain)
        
        # Chuẩn bị dữ liệu cho báo cáo
        payment_history = [{
            'name': payment.name,
            'payment_date': payment.payment_date,
            'period': f"{payment.period_month}/{payment.period_year}",
            'payment_amount': payment.payment_amount,
            'payment_ref': payment.payment_ref,
            'state': dict(payment._fields['state'].selection).get(payment.state),
            'bhxh_amount': payment.bhxh_amount,
            'bhyt_amount': payment.bhyt_amount,
            'bhtn_amount': payment.bhtn_amount,
            'employee_count': payment.employee_count
        } for payment in payments]
        
        return {
            'payment_history': payment_history,
            'total_payments': len(payments),
            'total_payment_amount': sum(payments.mapped('payment_amount')),
        } 