# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, datetime, timedelta
import math


class SocialInsuranceLateFee(models.Model):
    _name = 'social.insurance.late.fee'
    _description = 'Social Insurance Late Payment Fee'
    _order = 'create_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Mã truy thu', readonly=True, copy=False, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, tracking=True)
    
    # Bỏ các fields không tồn tại 
    related_document_model = fields.Char(string='Related Document Model', store=False, compute="_compute_dummy")
    related_document_id = fields.Integer(string='Related Document ID', store=False, compute="_compute_dummy")
    
    @api.depends('name')
    def _compute_dummy(self):
        """Hàm tính toán giả để hỗ trợ các trường dummy"""
        for record in self:
            record.related_document_model = False
            record.related_document_id = False
            
    insurance_id = fields.Many2one('hr.insurance', string='Bảo hiểm liên quan', 
                                  domain="[('employee_id', '=', employee_id), "
                                         "('insurance_type', 'in', ['bhxh', 'bhyt', 'bhtn'])]",
                                  tracking=True)
    
    # Thời gian truy thu
    period_type = fields.Selection([
        ('month', 'Theo tháng'),
        ('range', 'Theo thời gian'),
    ], string='Loại kỳ truy thu', default='month', required=True, tracking=True)
    
    year = fields.Char(string='Năm', tracking=True)
    month = fields.Selection([
        ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'), ('4', 'Tháng 4'),
        ('5', 'Tháng 5'), ('6', 'Tháng 6'), ('7', 'Tháng 7'), ('8', 'Tháng 8'),
        ('9', 'Tháng 9'), ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12'),
    ], string='Tháng', tracking=True)
    
    date_from = fields.Date(string='Từ ngày', tracking=True)
    date_to = fields.Date(string='Đến ngày', tracking=True)
    days_late = fields.Integer(string='Số ngày chậm nộp', compute='_compute_days_late', store=True)
    
    # Thông tin thanh toán
    salary_base = fields.Float(string='Lương cơ bản đóng BH', required=True, tracking=True)
    
    # BHXH
    bhxh_amount_due = fields.Float(string='BHXH phải đóng', tracking=True)
    bhxh_amount_paid = fields.Float(string='BHXH đã đóng', tracking=True)
    bhxh_amount_pending = fields.Float(string='BHXH còn thiếu', compute='_compute_pending_amounts', store=True)
    
    # BHYT
    bhyt_amount_due = fields.Float(string='BHYT phải đóng', tracking=True)
    bhyt_amount_paid = fields.Float(string='BHYT đã đóng', tracking=True)
    bhyt_amount_pending = fields.Float(string='BHYT còn thiếu', compute='_compute_pending_amounts', store=True)
    
    # BHTN
    bhtn_amount_due = fields.Float(string='BHTN phải đóng', tracking=True)
    bhtn_amount_paid = fields.Float(string='BHTN đã đóng', tracking=True)
    bhtn_amount_pending = fields.Float(string='BHTN còn thiếu', compute='_compute_pending_amounts', store=True)
    
    # Tổng cộng
    total_amount_due = fields.Float(string='Tổng phải đóng', compute='_compute_total_amounts', store=True)
    total_amount_paid = fields.Float(string='Tổng đã đóng', compute='_compute_total_amounts', store=True)
    total_amount_pending = fields.Float(string='Tổng còn thiếu', compute='_compute_total_amounts', store=True)
    
    # Lãi suất và tiền lãi
    interest_rate = fields.Float(string='Lãi suất (%/ngày)', default=0.03, 
                                help='Lãi suất mặc định 0.03%/ngày theo quy định hiện hành')
    
    interest_amount = fields.Float(string='Tiền lãi phạt (VNĐ)', compute='_compute_interest_amount', store=True)
    
    total_payment = fields.Float(string='Tổng cần thanh toán', 
                                compute='_compute_total_payment', store=True,
                                help='Tổng số tiền phải đóng bao gồm gốc và lãi')
    
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('confirmed', 'Đã xác nhận'),
        ('paid', 'Đã đóng'),
        ('cancelled', 'Đã hủy')
    ], string='Trạng thái', default='draft', tracking=True)
    
    payment_date = fields.Date(string='Ngày đóng', tracking=True)
    payment_method = fields.Selection([
        ('bank_transfer', 'Chuyển khoản'),
        ('cash', 'Tiền mặt'),
        ('other', 'Khác')
    ], string='Phương thức đóng', default='bank_transfer', tracking=True)
    payment_reference = fields.Char(string='Số tham chiếu', tracking=True)
    
    reason = fields.Text(string='Lý do truy thu', required=True, tracking=True,
                         help='Lý do phát sinh khoản truy thu BHXH')
    notes = fields.Text(string='Ghi chú')
    is_company_responsibility = fields.Boolean(string='Trách nhiệm công ty', default=False, tracking=True,
                                              help='Đánh dấu nếu nghĩa vụ đóng này thuộc trách nhiệm của công ty')
    
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu đính kèm')
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    
    @api.depends('bhxh_amount_due', 'bhxh_amount_paid', 
                 'bhyt_amount_due', 'bhyt_amount_paid',
                 'bhtn_amount_due', 'bhtn_amount_paid')
    def _compute_pending_amounts(self):
        for record in self:
            record.bhxh_amount_pending = record.bhxh_amount_due - record.bhxh_amount_paid
            record.bhyt_amount_pending = record.bhyt_amount_due - record.bhyt_amount_paid
            record.bhtn_amount_pending = record.bhtn_amount_due - record.bhtn_amount_paid
    
    @api.depends('bhxh_amount_due', 'bhxh_amount_paid', 'bhxh_amount_pending',
                 'bhyt_amount_due', 'bhyt_amount_paid', 'bhyt_amount_pending',
                 'bhtn_amount_due', 'bhtn_amount_paid', 'bhtn_amount_pending')
    def _compute_total_amounts(self):
        for record in self:
            record.total_amount_due = record.bhxh_amount_due + record.bhyt_amount_due + record.bhtn_amount_due
            record.total_amount_paid = record.bhxh_amount_paid + record.bhyt_amount_paid + record.bhtn_amount_paid
            record.total_amount_pending = record.total_amount_due - record.total_amount_paid
    
    @api.depends('total_amount_pending', 'interest_rate', 'days_late')
    def _compute_interest_amount(self):
        for record in self:
            if record.days_late and record.total_amount_pending and record.interest_rate:
                # Tính lãi theo công thức: Số tiền * lãi suất %/ngày * số ngày chậm nộp
                record.interest_amount = record.total_amount_pending * (record.interest_rate / 100) * record.days_late
            else:
                record.interest_amount = 0.0
    
    @api.depends('total_amount_pending', 'interest_amount')
    def _compute_total_payment(self):
        for record in self:
            record.total_payment = record.total_amount_pending + record.interest_amount
    
    @api.depends('period_type', 'month', 'year', 'date_from', 'date_to')
    def _compute_days_late(self):
        today = fields.Date.today()
        
        for record in self:
            if record.period_type == 'month' and record.year and record.month:
                # Xác định deadline đóng BHXH: ngày cuối của tháng + 10 ngày
                year = int(record.year)
                month = int(record.month)
                
                # Tính ngày cuối tháng
                if month == 12:
                    next_month = date(year + 1, 1, 1)
                else:
                    next_month = date(year, month + 1, 1)
                
                last_day = next_month - timedelta(days=1)
                deadline = last_day + timedelta(days=10)  # Thời hạn 10 ngày sau cuối tháng
                
                # Tính số ngày chậm nộp
                if today > deadline:
                    days_late = (today - deadline).days
                else:
                    days_late = 0
                    
            elif record.period_type == 'range' and record.date_from and record.date_to:
                # Đối với khoảng thời gian, deadline là ngày kết thúc + 10 ngày
                deadline = record.date_to + timedelta(days=10)
                
                # Tính số ngày chậm nộp
                if today > deadline:
                    days_late = (today - deadline).days
                else:
                    days_late = 0
            else:
                days_late = 0
                
            record.days_late = max(0, days_late)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = f"TT/{self.env['ir.sequence'].next_by_code('social.insurance.late.fee') or '00001'}"
        return super(SocialInsuranceLateFee, self).create(vals_list)
    
    def action_confirm(self):
        self.write({'state': 'confirmed'})
    
    def action_mark_as_paid(self):
        self.write({
            'state': 'paid',
            'payment_date': fields.Date.today() if not self.payment_date else self.payment_date
        })
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
    
    @api.onchange('insurance_id')
    def _onchange_insurance_id(self):
        if self.insurance_id:
            self.salary_base = self.insurance_id.salary_base

    @api.constrains('bhxh_amount_paid', 'bhyt_amount_paid', 'bhtn_amount_paid')
    def _check_payment_amounts(self):
        for record in self:
            if record.bhxh_amount_paid > record.bhxh_amount_due:
                raise ValidationError(_('Số tiền BHXH đã đóng không thể lớn hơn số tiền phải đóng!'))
            if record.bhyt_amount_paid > record.bhyt_amount_due:
                raise ValidationError(_('Số tiền BHYT đã đóng không thể lớn hơn số tiền phải đóng!'))
            if record.bhtn_amount_paid > record.bhtn_amount_due:
                raise ValidationError(_('Số tiền BHTN đã đóng không thể lớn hơn số tiền phải đóng!'))
    
    @api.onchange('employee_id', 'year', 'month', 'date_from', 'date_to')
    def _onchange_employee_period(self):
        if self.employee_id:
            # Tìm các hợp đồng bảo hiểm hiện tại của nhân viên
            insurances = self.env['hr.insurance'].search([
                ('employee_id', '=', self.employee_id.id),
                ('insurance_type', 'in', ['bhxh', 'bhyt', 'bhtn']),
                ('state', '=', 'active')
            ])
            
            # Thiết lập mức lương cơ sở từ hợp đồng BHXH
            bhxh_insurance = insurances.filtered(lambda r: r.insurance_type == 'bhxh')
            if bhxh_insurance:
                self.salary_base = bhxh_insurance[0].salary_base
            elif insurances:
                self.salary_base = insurances[0].salary_base
            
            # Thiết lập các khoản phải đóng dựa trên chính sách bảo hiểm
            if self.salary_base:
                for insurance in insurances:
                    if insurance.policy_id:
                        if insurance.insurance_type == 'bhxh':
                            self.bhxh_amount_due = self.salary_base * (insurance.policy_id.employee_rate + 
                                                                      insurance.policy_id.company_rate) / 100
                        elif insurance.insurance_type == 'bhyt':
                            self.bhyt_amount_due = self.salary_base * (insurance.policy_id.employee_rate + 
                                                                      insurance.policy_id.company_rate) / 100
                        elif insurance.insurance_type == 'bhtn':
                            self.bhtn_amount_due = self.salary_base * (insurance.policy_id.employee_rate + 
                                                                      insurance.policy_id.company_rate) / 100 