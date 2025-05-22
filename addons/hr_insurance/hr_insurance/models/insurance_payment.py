# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_compare
import base64
import logging

_logger = logging.getLogger(__name__)

class InsurancePayment(models.Model):
    _name = 'insurance.payment'
    _description = 'Insurance Payment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'payment_date desc, id desc'

    name = fields.Char(
        string='Mã thanh toán', 
        required=True, 
        copy=False, 
        readonly=True, 
        default=lambda self: _('New'))
    
    payment_date = fields.Date(
        string='Ngày thanh toán', 
        required=True, 
        default=fields.Date.context_today,
        tracking=True)
    
    period_month = fields.Selection([
        ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'),
        ('4', 'Tháng 4'), ('5', 'Tháng 5'), ('6', 'Tháng 6'),
        ('7', 'Tháng 7'), ('8', 'Tháng 8'), ('9', 'Tháng 9'),
        ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12')
    ], string='Tháng', required=True, tracking=True)
    
    period_year = fields.Integer(
        string='Năm', 
        required=True, 
        default=lambda self: fields.Date.today().year,
        tracking=True)
    
    insurance_type = fields.Selection([
        ('bhxh', 'Bảo hiểm xã hội (BHXH)'),
        ('bhyt', 'Bảo hiểm y tế (BHYT)'),
        ('bhtn', 'Bảo hiểm thất nghiệp (BHTN)'),
        ('combined', 'Tổng hợp (BHXH, BHYT, BHTN)'),
        ('other', 'Bảo hiểm khác')
    ], string='Loại bảo hiểm', required=True, default='combined', tracking=True)
    
    payment_amount = fields.Float(
        string='Số tiền thanh toán', 
        required=True,
        tracking=True)
    
    payment_method = fields.Selection([
        ('bank_transfer', 'Chuyển khoản'),
        ('cash', 'Tiền mặt'),
        ('online', 'Thanh toán trực tuyến')
    ], string='Phương thức thanh toán', required=True, default='bank_transfer', tracking=True)
    
    payment_ref = fields.Char(
        string='Số tham chiếu', 
        help='Số chứng từ/Mã giao dịch',
        tracking=True)
    
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('confirmed', 'Đã xác nhận'),
        ('paid', 'Đã thanh toán'),
        ('verified', 'Đã xác thực'),
        ('cancelled', 'Đã hủy')
    ], string='Trạng thái', default='draft', tracking=True)
    
    company_id = fields.Many2one(
        'res.company', 
        string='Công ty', 
        required=True, 
        default=lambda self: self.env.company)
    
    currency_id = fields.Many2one(
        'res.currency', 
        string='Tiền tệ', 
        related='company_id.currency_id',
        readonly=True)
    
    payment_line_ids = fields.One2many(
        'insurance.payment.line', 
        'payment_id', 
        string='Chi tiết thanh toán')
    
    employee_count = fields.Integer(
        string='Số nhân viên', 
        compute='_compute_employee_count',
        search='_search_employee_count',
        store=True)
    
    bhxh_amount = fields.Float(
        string='Tổng BHXH', 
        compute='_compute_insurance_amounts',
        search='_search_bhxh_amount',
        store=True)
    
    bhyt_amount = fields.Float(
        string='Tổng BHYT', 
        compute='_compute_insurance_amounts',
        search='_search_bhyt_amount', 
        store=True)
    
    bhtn_amount = fields.Float(
        string='Tổng BHTN', 
        compute='_compute_insurance_amounts',
        search='_search_bhtn_amount',
        store=True)
    
    expected_amount = fields.Float(
        string='Số tiền dự kiến', 
        compute='_compute_expected_amount',
        search='_search_expected_amount',
        store=True,
        help='Tổng số tiền dự kiến phải đóng dựa trên chi tiết bảo hiểm')
    
    difference_amount = fields.Float(
        string='Chênh lệch', 
        compute='_compute_difference_amount',
        search='_search_difference_amount',
        store=True,
        help='Chênh lệch giữa số tiền thanh toán và số tiền dự kiến')
    
    notes = fields.Text(
        string='Ghi chú',
        tracking=True)
    
    receipt_attachment = fields.Binary(
        string='File biên lai',
        attachment=True,
        help='Tải lên biên lai thanh toán')
    
    receipt_filename = fields.Char(
        string='Tên file biên lai')
    
    payment_authority = fields.Char(
        string='Cơ quan tiếp nhận', 
        default='BHXH Việt Nam',
        tracking=True)
    
    user_id = fields.Many2one(
        'res.users', 
        string='Người tạo', 
        default=lambda self: self.env.user, 
        tracking=True)
    
    @api.depends('payment_line_ids')
    def _compute_employee_count(self):
        for record in self:
            record.employee_count = len(record.payment_line_ids)
    
    @api.depends('payment_line_ids', 'payment_line_ids.bhxh_amount', 
                'payment_line_ids.bhyt_amount', 'payment_line_ids.bhtn_amount')
    def _compute_insurance_amounts(self):
        for record in self:
            record.bhxh_amount = sum(record.payment_line_ids.mapped('bhxh_amount'))
            record.bhyt_amount = sum(record.payment_line_ids.mapped('bhyt_amount'))
            record.bhtn_amount = sum(record.payment_line_ids.mapped('bhtn_amount'))
    
    @api.depends('bhxh_amount', 'bhyt_amount', 'bhtn_amount')
    def _compute_expected_amount(self):
        for record in self:
            record.expected_amount = record.bhxh_amount + record.bhyt_amount + record.bhtn_amount
    
    @api.depends('payment_amount', 'expected_amount')
    def _compute_difference_amount(self):
        for record in self:
            record.difference_amount = record.payment_amount - record.expected_amount
    
    @api.model
    def _search_employee_count(self, operator, value):
        if operator not in ('=', '!=', '<', '<=', '>', '>=', 'in', 'not in'):
            return []
        
        if operator in ('in', 'not in'):
            value = set(value)
            
        domain = []
        if operator == '=':
            domain = [('employee_count', '=', value)]
        elif operator == '!=':
            domain = [('employee_count', '!=', value)]
        elif operator == '>':
            domain = [('employee_count', '>', value)]
        elif operator == '>=':
            domain = [('employee_count', '>=', value)]
        elif operator == '<':
            domain = [('employee_count', '<', value)]
        elif operator == '<=':
            domain = [('employee_count', '<=', value)]
        elif operator == 'in':
            domain = [('employee_count', 'in', list(value))]
        elif operator == 'not in':
            domain = [('employee_count', 'not in', list(value))]
        
        return domain
    
    @api.model
    def _search_bhxh_amount(self, operator, value):
        if operator not in ('=', '!=', '<', '<=', '>', '>=', 'in', 'not in'):
            return []
        
        if operator in ('in', 'not in'):
            value = set(value)
            
        domain = []
        if operator == '=':
            domain = [('bhxh_amount', '=', value)]
        elif operator == '!=':
            domain = [('bhxh_amount', '!=', value)]
        elif operator == '>':
            domain = [('bhxh_amount', '>', value)]
        elif operator == '>=':
            domain = [('bhxh_amount', '>=', value)]
        elif operator == '<':
            domain = [('bhxh_amount', '<', value)]
        elif operator == '<=':
            domain = [('bhxh_amount', '<=', value)]
        elif operator == 'in':
            domain = [('bhxh_amount', 'in', list(value))]
        elif operator == 'not in':
            domain = [('bhxh_amount', 'not in', list(value))]
        
        return domain
    
    @api.model
    def _search_bhyt_amount(self, operator, value):
        if operator not in ('=', '!=', '<', '<=', '>', '>=', 'in', 'not in'):
            return []
        
        if operator in ('in', 'not in'):
            value = set(value)
            
        domain = []
        if operator == '=':
            domain = [('bhyt_amount', '=', value)]
        elif operator == '!=':
            domain = [('bhyt_amount', '!=', value)]
        elif operator == '>':
            domain = [('bhyt_amount', '>', value)]
        elif operator == '>=':
            domain = [('bhyt_amount', '>=', value)]
        elif operator == '<':
            domain = [('bhyt_amount', '<', value)]
        elif operator == '<=':
            domain = [('bhyt_amount', '<=', value)]
        elif operator == 'in':
            domain = [('bhyt_amount', 'in', list(value))]
        elif operator == 'not in':
            domain = [('bhyt_amount', 'not in', list(value))]
        
        return domain
    
    @api.model
    def _search_bhtn_amount(self, operator, value):
        if operator not in ('=', '!=', '<', '<=', '>', '>=', 'in', 'not in'):
            return []
        
        if operator in ('in', 'not in'):
            value = set(value)
            
        domain = []
        if operator == '=':
            domain = [('bhtn_amount', '=', value)]
        elif operator == '!=':
            domain = [('bhtn_amount', '!=', value)]
        elif operator == '>':
            domain = [('bhtn_amount', '>', value)]
        elif operator == '>=':
            domain = [('bhtn_amount', '>=', value)]
        elif operator == '<':
            domain = [('bhtn_amount', '<', value)]
        elif operator == '<=':
            domain = [('bhtn_amount', '<=', value)]
        elif operator == 'in':
            domain = [('bhtn_amount', 'in', list(value))]
        elif operator == 'not in':
            domain = [('bhtn_amount', 'not in', list(value))]
        
        return domain
    
    @api.model
    def _search_expected_amount(self, operator, value):
        if operator not in ('=', '!=', '<', '<=', '>', '>=', 'in', 'not in'):
            return []
        
        if operator in ('in', 'not in'):
            value = set(value)
            
        domain = []
        if operator == '=':
            domain = [('expected_amount', '=', value)]
        elif operator == '!=':
            domain = [('expected_amount', '!=', value)]
        elif operator == '>':
            domain = [('expected_amount', '>', value)]
        elif operator == '>=':
            domain = [('expected_amount', '>=', value)]
        elif operator == '<':
            domain = [('expected_amount', '<', value)]
        elif operator == '<=':
            domain = [('expected_amount', '<=', value)]
        elif operator == 'in':
            domain = [('expected_amount', 'in', list(value))]
        elif operator == 'not in':
            domain = [('expected_amount', 'not in', list(value))]
        
        return domain
    
    @api.model
    def _search_difference_amount(self, operator, value):
        if operator not in ('=', '!=', '<', '<=', '>', '>=', 'in', 'not in'):
            return []
        
        if operator in ('in', 'not in'):
            value = set(value)
            
        domain = []
        if operator == '=':
            domain = [('difference_amount', '=', value)]
        elif operator == '!=':
            domain = [('difference_amount', '!=', value)]
        elif operator == '>':
            domain = [('difference_amount', '>', value)]
        elif operator == '>=':
            domain = [('difference_amount', '>=', value)]
        elif operator == '<':
            domain = [('difference_amount', '<', value)]
        elif operator == '<=':
            domain = [('difference_amount', '<=', value)]
        elif operator == 'in':
            domain = [('difference_amount', 'in', list(value))]
        elif operator == 'not in':
            domain = [('difference_amount', 'not in', list(value))]
        
        return domain
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('insurance.payment') or _('New')
        return super().create(vals_list)
    
    def action_confirm(self):
        for rec in self:
            if not rec.payment_line_ids:
                raise ValidationError(_("Cannot confirm payment without employee details!"))
            rec.write({'state': 'confirmed'})
        return True
    
    def action_set_to_paid(self):
        for rec in self:
            expected_amount = rec.expected_amount
            payment_amount = rec.payment_amount
            
            # Check if payment amount matches expected amount with a small tolerance
            if float_compare(expected_amount, payment_amount, precision_digits=2) != 0:
                # Only show warning if the difference is significant
                diff = abs(payment_amount - expected_amount)
                if diff > 1.0:  # More than 1 currency unit difference
                    return {
                        'name': _('Warning'),
                        'type': 'ir.actions.act_window',
                        'res_model': 'insurance.payment.difference.wizard',
                        'view_mode': 'form',
                        'target': 'new',
                        'context': {
                            'default_payment_id': rec.id,
                            'default_difference_amount': diff,
                        }
                    }
            
            rec.write({'state': 'paid'})
        return True
    
    def action_verify(self):
        for rec in self:
            if not rec.receipt_attachment:
                raise ValidationError(_("Please upload receipt before verification!"))
            rec.write({'state': 'verified'})
        return True
    
    def action_cancel(self):
        for rec in self:
            rec.write({'state': 'cancelled'})
        return True
    
    def action_reset_to_draft(self):
        for rec in self:
            rec.write({'state': 'draft'})
        return True
    
    def action_add_employees(self):
        self.ensure_one()
        return {
            'name': _('Add Employees to Insurance Payment'),
            'type': 'ir.actions.act_window',
            'res_model': 'insurance.payment.employee.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_payment_id': self.id}
        }
    
    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'cancelled'):
                raise ValidationError(_("You cannot delete a payment that is not in draft or cancelled state!"))
        return super().unlink()


class InsurancePaymentLine(models.Model):
    _name = 'insurance.payment.line'
    _description = 'Insurance Payment Line'
    
    payment_id = fields.Many2one(
        'insurance.payment', 
        string='Thanh toán', 
        required=True, 
        ondelete='cascade')
    
    employee_id = fields.Many2one(
        'hr.employee', 
        string='Nhân viên', 
        required=True)
    
    social_insurance_code = fields.Char(
        related='employee_id.social_insurance_code', 
        string='Mã số BHXH', 
        readonly=True)
    
    department_id = fields.Many2one(
        related='employee_id.department_id', 
        string='Phòng ban', 
        readonly=True)
    
    salary_base = fields.Float(
        string='Lương đóng BH', 
        required=True,
        help='Lương làm căn cứ đóng bảo hiểm')
    
    bhxh_amount = fields.Float(
        string='BHXH (Tổng)', 
        compute='_compute_insurance_amounts',
        search='_search_bhxh_amount',
        store=True)
    
    bhyt_amount = fields.Float(
        string='BHYT (Tổng)', 
        compute='_compute_insurance_amounts',
        search='_search_bhyt_amount',
        store=True)
    
    bhtn_amount = fields.Float(
        string='BHTN (Tổng)', 
        compute='_compute_insurance_amounts',
        search='_search_bhtn_amount',
        store=True)
    
    total_amount = fields.Float(
        string='Tổng cộng', 
        compute='_compute_total_amount',
        search='_search_total_amount',
        store=True)
    
    employee_bhxh_rate = fields.Float(
        string='Tỷ lệ BHXH NV', 
        default=8.0)
    
    employer_bhxh_rate = fields.Float(
        string='Tỷ lệ BHXH CT', 
        default=17.5)
    
    employee_bhyt_rate = fields.Float(
        string='Tỷ lệ BHYT NV', 
        default=1.5)
    
    employer_bhyt_rate = fields.Float(
        string='Tỷ lệ BHYT CT', 
        default=3.0)
    
    employee_bhtn_rate = fields.Float(
        string='Tỷ lệ BHTN NV', 
        default=1.0)
    
    employer_bhtn_rate = fields.Float(
        string='Tỷ lệ BHTN CT', 
        default=1.0)
    
    notes = fields.Text(
        string='Ghi chú')
    
    currency_id = fields.Many2one(
        related='payment_id.currency_id', 
        string='Tiền tệ', 
        readonly=True)
    
    @api.depends('salary_base', 'employee_bhxh_rate', 'employer_bhxh_rate', 
                'employee_bhyt_rate', 'employer_bhyt_rate', 
                'employee_bhtn_rate', 'employer_bhtn_rate')
    def _compute_insurance_amounts(self):
        for record in self:
            # BHXH = (employee + employer) * salary_base
            record.bhxh_amount = (record.employee_bhxh_rate + record.employer_bhxh_rate) * record.salary_base / 100
            # BHYT
            record.bhyt_amount = (record.employee_bhyt_rate + record.employer_bhyt_rate) * record.salary_base / 100
            # BHTN
            record.bhtn_amount = (record.employee_bhtn_rate + record.employer_bhtn_rate) * record.salary_base / 100
    
    @api.depends('bhxh_amount', 'bhyt_amount', 'bhtn_amount')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = record.bhxh_amount + record.bhyt_amount + record.bhtn_amount
    
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            # Get active insurances for this employee
            active_insurances = self.env['hr.insurance'].search([
                ('employee_id', '=', self.employee_id.id),
                ('state', '=', 'active'),
                ('is_social_insurance', '=', True)
            ])
            
            # Calculate salary base from active insurances
            total_salary_base = 0
            for insurance in active_insurances:
                total_salary_base += insurance.salary_base
            
            if total_salary_base > 0:
                self.salary_base = total_salary_base
            else:
                # Try to get from contract
                contract = self.env['hr.contract'].search([
                    ('employee_id', '=', self.employee_id.id),
                    ('state', '=', 'open')
                ], limit=1)
                if contract:
                    self.salary_base = contract.wage
    
    @api.constrains('employee_id', 'payment_id')
    def _check_duplicate_employee(self):
        for record in self:
            if record.employee_id and record.payment_id:
                duplicate = self.search([
                    ('id', '!=', record.id),
                    ('employee_id', '=', record.employee_id.id),
                    ('payment_id', '=', record.payment_id.id)
                ])
                if duplicate:
                    raise ValidationError(_('Employee %s is already included in this payment!') % record.employee_id.name)
    
    @api.model
    def _search_bhxh_amount(self, operator, value):
        if operator not in ('=', '!=', '<', '<=', '>', '>=', 'in', 'not in'):
            return []
        
        if operator in ('in', 'not in'):
            value = set(value)
            
        domain = []
        if operator == '=':
            domain = [('bhxh_amount', '=', value)]
        elif operator == '!=':
            domain = [('bhxh_amount', '!=', value)]
        elif operator == '>':
            domain = [('bhxh_amount', '>', value)]
        elif operator == '>=':
            domain = [('bhxh_amount', '>=', value)]
        elif operator == '<':
            domain = [('bhxh_amount', '<', value)]
        elif operator == '<=':
            domain = [('bhxh_amount', '<=', value)]
        elif operator == 'in':
            domain = [('bhxh_amount', 'in', list(value))]
        elif operator == 'not in':
            domain = [('bhxh_amount', 'not in', list(value))]
        
        return domain
    
    @api.model
    def _search_bhyt_amount(self, operator, value):
        if operator not in ('=', '!=', '<', '<=', '>', '>=', 'in', 'not in'):
            return []
        
        if operator in ('in', 'not in'):
            value = set(value)
            
        domain = []
        if operator == '=':
            domain = [('bhyt_amount', '=', value)]
        elif operator == '!=':
            domain = [('bhyt_amount', '!=', value)]
        elif operator == '>':
            domain = [('bhyt_amount', '>', value)]
        elif operator == '>=':
            domain = [('bhyt_amount', '>=', value)]
        elif operator == '<':
            domain = [('bhyt_amount', '<', value)]
        elif operator == '<=':
            domain = [('bhyt_amount', '<=', value)]
        elif operator == 'in':
            domain = [('bhyt_amount', 'in', list(value))]
        elif operator == 'not in':
            domain = [('bhyt_amount', 'not in', list(value))]
        
        return domain
    
    @api.model
    def _search_bhtn_amount(self, operator, value):
        if operator not in ('=', '!=', '<', '<=', '>', '>=', 'in', 'not in'):
            return []
        
        if operator in ('in', 'not in'):
            value = set(value)
            
        domain = []
        if operator == '=':
            domain = [('bhtn_amount', '=', value)]
        elif operator == '!=':
            domain = [('bhtn_amount', '!=', value)]
        elif operator == '>':
            domain = [('bhtn_amount', '>', value)]
        elif operator == '>=':
            domain = [('bhtn_amount', '>=', value)]
        elif operator == '<':
            domain = [('bhtn_amount', '<', value)]
        elif operator == '<=':
            domain = [('bhtn_amount', '<=', value)]
        elif operator == 'in':
            domain = [('bhtn_amount', 'in', list(value))]
        elif operator == 'not in':
            domain = [('bhtn_amount', 'not in', list(value))]
        
        return domain
    
    @api.model
    def _search_total_amount(self, operator, value):
        if operator not in ('=', '!=', '<', '<=', '>', '>=', 'in', 'not in'):
            return []
        
        if operator in ('in', 'not in'):
            value = set(value)
            
        domain = []
        if operator == '=':
            domain = [('total_amount', '=', value)]
        elif operator == '!=':
            domain = [('total_amount', '!=', value)]
        elif operator == '>':
            domain = [('total_amount', '>', value)]
        elif operator == '>=':
            domain = [('total_amount', '>=', value)]
        elif operator == '<':
            domain = [('total_amount', '<', value)]
        elif operator == '<=':
            domain = [('total_amount', '<=', value)]
        elif operator == 'in':
            domain = [('total_amount', 'in', list(value))]
        elif operator == 'not in':
            domain = [('total_amount', 'not in', list(value))]
        
        return domain 