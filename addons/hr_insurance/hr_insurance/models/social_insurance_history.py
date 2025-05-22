# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import date


class SocialInsuranceHistory(models.Model):
    _name = 'social.insurance.history'
    _description = 'Social Insurance History'
    _order = 'year desc, month desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Mã', readonly=True, copy=False, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, tracking=True)
    insurance_id = fields.Many2one('hr.insurance', string='Bảo hiểm liên quan',
                                  domain="[('employee_id', '=', employee_id), "
                                         "('insurance_type', 'in', ['bhxh', 'bhyt', 'bhtn'])]",
                                  tracking=True)

    # Bỏ các fields không tồn tại 
    related_document_model = fields.Char(string='Related Document Model', store=False, compute="_compute_dummy")
    related_document_id = fields.Integer(string='Related Document ID', store=False, compute="_compute_dummy")
    
    @api.depends('name')
    def _compute_dummy(self):
        """Hàm tính toán giả để hỗ trợ các trường dummy"""
        for record in self:
            record.related_document_model = False
            record.related_document_id = False

    year = fields.Char(string='Năm', required=True, tracking=True)
    month = fields.Selection([
        ('1', 'Tháng 1'),
        ('2', 'Tháng 2'),
        ('3', 'Tháng 3'),
        ('4', 'Tháng 4'),
        ('5', 'Tháng 5'),
        ('6', 'Tháng 6'),
        ('7', 'Tháng 7'),
        ('8', 'Tháng 8'),
        ('9', 'Tháng 9'),
        ('10', 'Tháng 10'),
        ('11', 'Tháng 11'),
        ('12', 'Tháng 12'),
    ], string='Tháng', required=True, tracking=True)

    salary_base = fields.Float(string='Lương cơ bản đóng BH', required=True, tracking=True)

    # BHXH
    bhxh_employee_amount = fields.Float(string='BHXH NV đóng', tracking=True)
    bhxh_company_amount = fields.Float(string='BHXH công ty đóng', tracking=True)
    bhxh_total_amount = fields.Float(string='Tổng BHXH', compute='_compute_insurance_totals', store=True)

    # BHYT
    bhyt_employee_amount = fields.Float(string='BHYT NV đóng', tracking=True)
    bhyt_company_amount = fields.Float(string='BHYT công ty đóng', tracking=True)
    bhyt_total_amount = fields.Float(string='Tổng BHYT', compute='_compute_insurance_totals', store=True)

    # BHTN
    bhtn_employee_amount = fields.Float(string='BHTN NV đóng', tracking=True)
    bhtn_company_amount = fields.Float(string='BHTN công ty đóng', tracking=True)
    bhtn_total_amount = fields.Float(string='Tổng BHTN', compute='_compute_insurance_totals', store=True)

    # Totals
    total_employee_amount = fields.Float(string='Tổng NV đóng', compute='_compute_insurance_totals', store=True)
    total_company_amount = fields.Float(string='Tổng công ty đóng', compute='_compute_insurance_totals', store=True)
    total_amount = fields.Float(string='Tổng cộng', compute='_compute_insurance_totals', store=True)

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

    notes = fields.Text(string='Ghi chú')
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu đính kèm')

    is_confirmed = fields.Boolean(compute='_compute_is_confirmed', store=False)
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)

    @api.depends('bhxh_employee_amount', 'bhxh_company_amount',
                 'bhyt_employee_amount', 'bhyt_company_amount',
                 'bhtn_employee_amount', 'bhtn_company_amount')
    def _compute_insurance_totals(self):
        for record in self:
            # Calculate BHXH, BHYT, BHTN totals
            record.bhxh_total_amount = record.bhxh_employee_amount + record.bhxh_company_amount
            record.bhyt_total_amount = record.bhyt_employee_amount + record.bhyt_company_amount
            record.bhtn_total_amount = record.bhtn_employee_amount + record.bhtn_company_amount

            # Calculate overall totals
            record.total_employee_amount = (record.bhxh_employee_amount +
                                          record.bhyt_employee_amount +
                                          record.bhtn_employee_amount)
            record.total_company_amount = (record.bhxh_company_amount +
                                         record.bhyt_company_amount +
                                         record.bhtn_company_amount)
            record.total_amount = record.total_employee_amount + record.total_company_amount

    @api.depends('state')
    def _compute_is_confirmed(self):
        for record in self:
            record.is_confirmed = record.state != 'draft'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('social.insurance.history') or _('New')
        return super(SocialInsuranceHistory, self).create(vals_list)

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

    @api.constrains('year', 'month', 'employee_id')
    def _check_unique_month_year(self):
        for record in self:
            duplicate = self.search([
                ('id', '!=', record.id),
                ('employee_id', '=', record.employee_id.id),
                ('year', '=', record.year),
                ('month', '=', record.month),
                ('state', '!=', 'cancelled')
            ])
            if duplicate:
                raise UserError(_('Đã tồn tại bản ghi đóng BHXH cho nhân viên %s trong tháng %s/%s!')
                               % (record.employee_id.name, record.month, record.year))

    @api.onchange('employee_id', 'year', 'month')
    def _onchange_employee_month_year(self):
        if self.employee_id and not self.insurance_id:
            # Try to find an active insurance policy for this employee
            insurance = self.env['hr.insurance'].search([
                ('employee_id', '=', self.employee_id.id),
                ('insurance_type', '=', 'bhxh'),
                ('state', '=', 'active')
            ], limit=1)
            if insurance:
                self.insurance_id = insurance.id
                self.salary_base = insurance.salary_base

                # Calculate insurance amounts based on policy rates
                if insurance.policy_id:
                    policy = insurance.policy_id
                    self.bhxh_employee_amount = self.salary_base * policy.employee_rate / 100
                    self.bhxh_company_amount = self.salary_base * policy.company_rate / 100

                    # For BHYT and BHTN, try to find related insurance policies
                    bhyt_insurance = self.env['hr.insurance'].search([
                        ('employee_id', '=', self.employee_id.id),
                        ('insurance_type', '=', 'bhyt'),
                        ('state', '=', 'active')
                    ], limit=1)

                    bhtn_insurance = self.env['hr.insurance'].search([
                        ('employee_id', '=', self.employee_id.id),
                        ('insurance_type', '=', 'bhtn'),
                        ('state', '=', 'active')
                    ], limit=1)

                    if bhyt_insurance and bhyt_insurance.policy_id:
                        self.bhyt_employee_amount = self.salary_base * bhyt_insurance.policy_id.employee_rate / 100
                        self.bhyt_company_amount = self.salary_base * bhyt_insurance.policy_id.company_rate / 100

                    if bhtn_insurance and bhtn_insurance.policy_id:
                        self.bhtn_employee_amount = self.salary_base * bhtn_insurance.policy_id.employee_rate / 100
                        self.bhtn_company_amount = self.salary_base * bhtn_insurance.policy_id.company_rate / 100

    @api.onchange('insurance_id')
    def _onchange_insurance_id(self):
        if self.insurance_id:
            self.salary_base = self.insurance_id.salary_base

            # Set insurance amounts based on the selected insurance policy
            if self.insurance_id.policy_id:
                if self.insurance_id.insurance_type == 'bhxh':
                    self.bhxh_employee_amount = self.salary_base * self.insurance_id.policy_id.employee_rate / 100
                    self.bhxh_company_amount = self.salary_base * self.insurance_id.policy_id.company_rate / 100
                elif self.insurance_id.insurance_type == 'bhyt':
                    self.bhyt_employee_amount = self.salary_base * self.insurance_id.policy_id.employee_rate / 100
                    self.bhyt_company_amount = self.salary_base * self.insurance_id.policy_id.company_rate / 100
                elif self.insurance_id.insurance_type == 'bhtn':
                    self.bhtn_employee_amount = self.salary_base * self.insurance_id.policy_id.employee_rate / 100
                    self.bhtn_company_amount = self.salary_base * self.insurance_id.policy_id.company_rate / 100