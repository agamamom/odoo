# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta


class SocialInsuranceBenefit(models.Model):
    _name = 'social.insurance.benefit'
    _description = 'Social Insurance Benefit'
    _order = 'date_from desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Mã', readonly=True, copy=False, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, tracking=True)
    insurance_id = fields.Many2one('hr.insurance', string='Bảo hiểm liên quan', 
                                  domain="[('employee_id', '=', employee_id)]", tracking=True)
    
    # Bỏ các fields không tồn tại 
    related_document_model = fields.Char(string='Related Document Model', store=False, compute="_compute_dummy")
    related_document_id = fields.Integer(string='Related Document ID', store=False, compute="_compute_dummy")
    
    @api.depends('name')
    def _compute_dummy(self):
        """Hàm tính toán giả để hỗ trợ các trường dummy"""
        for record in self:
            record.related_document_model = False
            record.related_document_id = False
    
    benefit_type = fields.Selection([
        ('sickness', 'Ốm đau'),
        ('maternity', 'Thai sản'),
        ('maternity_leave', 'Nghỉ thai sản 6 tháng'),
        ('prenatal_care', 'Khám thai'),
        ('miscarriage', 'Sẩy thai/Nạo, hút thai'),
        ('birth_support', 'Sinh con'),
        ('adoption', 'Nhận con nuôi'),
        ('ivf', 'Thụ tinh ống nghiệm'),
        ('work_accident', 'Tai nạn lao động'),
        ('occupational_disease', 'Bệnh nghề nghiệp'),
        ('unemployment', 'Thất nghiệp'),
        ('retirement', 'Hưu trí'),
        ('death', 'Tử tuất'),
        ('other', 'Khác')
    ], string='Loại trợ cấp', required=True, tracking=True)
    
    date_from = fields.Date(string='Từ ngày', required=True, tracking=True)
    date_to = fields.Date(string='Đến ngày', required=True, tracking=True)
    benefit_days = fields.Integer(string='Số ngày hưởng', compute='_compute_benefit_days', store=True)
    
    # Thông tin đặc thù cho lao động nước ngoài
    is_foreign_worker = fields.Boolean(string='Lao động nước ngoài', tracking=True)
    nationality_id = fields.Many2one('res.country', string='Quốc tịch', tracking=True)
    passport_id = fields.Char(string='Số hộ chiếu', tracking=True)
    work_permit_id = fields.Char(string='Số giấy phép lao động', tracking=True)
    voluntary_insurance = fields.Boolean(string='BHXH tự nguyện', tracking=True,
                                       help='Đánh dấu nếu người lao động đóng BHXH tự nguyện')
    
    # Thông tin đặc thù cho thai sản
    # Số con, tuổi con cho chế độ thai sản
    number_of_children = fields.Integer(string='Số con (sinh đôi/ba)', default=1, tracking=True)
    child_under_12_months = fields.Boolean(string='Con dưới 12 tháng tuổi', tracking=True)
    cesarean_section = fields.Boolean(string='Sinh mổ', tracking=True)
    
    # Additional maternity benefit fields
    is_birth_benefit = fields.Boolean(string='Trợ cấp sinh con', tracking=True)
    has_participated_enough = fields.Boolean(
        string='Đóng BHXH đủ thời gian', 
        tracking=True,
        help='Đã đóng BHXH đủ 6 tháng trong 12 tháng trước khi sinh'
    )
    birth_certificate_number = fields.Char(string='Số giấy khai sinh', tracking=True)
    birth_certificate_date = fields.Date(string='Ngày cấp giấy khai sinh', tracking=True)
    labor_book_number = fields.Char(string='Số sổ lao động', tracking=True)
    labor_book_date = fields.Date(string='Ngày cấp sổ lao động', tracking=True)
    child_name = fields.Char(string='Tên trẻ', tracking=True)
    child_birth_date = fields.Date(string='Ngày sinh của trẻ', tracking=True)
    child_gender = fields.Selection([
        ('male', 'Nam'),
        ('female', 'Nữ')
    ], string='Giới tính trẻ', tracking=True)
    is_premature_birth = fields.Boolean(string='Sinh non', tracking=True)
    is_multiple_birth = fields.Boolean(string='Sinh đôi/ba', tracking=True)
    multiple_birth_count = fields.Integer(string='Số trẻ sinh ra', default=1, tracking=True)
    
    salary_base = fields.Float(string='Lương cơ sở tính trợ cấp', tracking=True)
    benefit_rate = fields.Float(string='Tỷ lệ hưởng (%)', default=75, tracking=True)
    benefit_amount = fields.Float(string='Số tiền trợ cấp', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('submitted', 'Đã nộp hồ sơ'),
        ('approved', 'Đã duyệt'),
        ('paid', 'Đã chi trả'),
        ('rejected', 'Bị từ chối'),
        ('cancelled', 'Đã hủy')
    ], string='Trạng thái', default='draft', tracking=True)
    
    document_id = fields.Many2one('social.insurance.document', string='Tài liệu BHXH liên quan', 
                                  tracking=True)
    
    payment_date = fields.Date(string='Ngày chi trả', tracking=True)
    payment_method = fields.Selection([
        ('bank_transfer', 'Chuyển khoản'),
        ('cash', 'Tiền mặt'),
        ('other', 'Khác')
    ], string='Phương thức chi trả', default='bank_transfer', tracking=True)
    
    agency_reference = fields.Char(string='Số hiệu hồ sơ BHXH', tracking=True)
    agency_officer = fields.Char(string='Cán bộ BHXH phụ trách', tracking=True)
    
    notes = fields.Text(string='Ghi chú')
    description = fields.Text(string='Mô tả chi tiết')
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu đính kèm')
    
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    
    @api.depends('date_from', 'date_to')
    def _compute_benefit_days(self):
        for record in self:
            if record.date_from and record.date_to and record.date_to >= record.date_from:
                delta = record.date_to - record.date_from
                record.benefit_days = delta.days + 1
            else:
                record.benefit_days = 0
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = f"TC/{self.env['ir.sequence'].next_by_code('social.insurance.benefit') or '00001'}"
                
            # Tự động thiết lập thời gian nghỉ thai sản 6 tháng nếu chọn loại trợ cấp là nghỉ thai sản
            if vals.get('benefit_type') == 'maternity_leave' and vals.get('date_from'):
                from_date = fields.Date.from_string(vals.get('date_from'))
                to_date = from_date + timedelta(days=180)  # 6 tháng (180 ngày)
                vals['date_to'] = fields.Date.to_string(to_date)
                vals['benefit_rate'] = 100  # 100% lương
                
        return super(SocialInsuranceBenefit, self).create(vals_list)
    
    def action_submit(self):
        self.write({'state': 'submitted'})
    
    def action_approve(self):
        self.write({'state': 'approved'})
    
    def action_mark_as_paid(self):
        self.write({
            'state': 'paid',
            'payment_date': fields.Date.today() if not self.payment_date else self.payment_date
        })
    
    def action_reject(self):
        self.write({'state': 'rejected'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_reset_to_draft(self):
        self.write({'state': 'draft'})
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from and record.date_to and record.date_to < record.date_from:
                raise ValidationError(_('Ngày kết thúc không thể trước ngày bắt đầu!'))
    
    @api.constrains('date_from', 'date_to', 'employee_id', 'benefit_type')
    def _check_overlapping(self):
        for record in self:
            if record.date_from and record.date_to and record.employee_id and record.benefit_type:
                overlapping = self.search([
                    ('id', '!=', record.id),
                    ('employee_id', '=', record.employee_id.id),
                    ('benefit_type', '=', record.benefit_type),
                    ('date_from', '<=', record.date_to),
                    ('date_to', '>=', record.date_from),
                    ('state', 'not in', ['rejected', 'cancelled'])
                ])
                
                if overlapping:
                    raise ValidationError(_('Đã tồn tại quyền lợi %s cho nhân viên này trong khoảng thời gian từ %s đến %s!') 
                                  % (dict(self._fields['benefit_type'].selection).get(record.benefit_type),
                                    record.date_from.strftime('%d/%m/%Y'), 
                                    record.date_to.strftime('%d/%m/%Y')))
    
    def name_get(self):
        result = []
        for record in self:
            benefit_type_str = dict(self._fields['benefit_type'].selection).get(record.benefit_type)
            name = f"{record.employee_id.name} - {benefit_type_str} ({record.date_from.strftime('%d/%m/%Y')})"
            result.append((record.id, name))
        return result
    
    @api.onchange('benefit_type')
    def _onchange_benefit_type(self):
        if self.benefit_type == 'maternity_leave':
            if self.date_from:
                self.date_to = self.date_from + timedelta(days=180)  # 6 tháng (180 ngày)
            self.benefit_rate = 100  # 100% lương
        elif self.benefit_type == 'sickness':
            self.benefit_rate = 75  # 75% lương
        elif self.benefit_type == 'work_accident':
            self.benefit_rate = 100  # 100% lương
    
    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id:
            # Kiểm tra xem nhân viên có phải là người nước ngoài không
            if self.employee_id.country_id and self.employee_id.country_id.id != self.env.company.country_id.id:
                self.is_foreign_worker = True
                self.nationality_id = self.employee_id.country_id.id
                self.passport_id = self.employee_id.passport_id
            else:
                self.is_foreign_worker = False
                self.nationality_id = False
                self.passport_id = False
                
            # Tìm bảo hiểm đang hoạt động
            insurance = self.env['hr.insurance'].search([
                ('employee_id', '=', self.employee_id.id),
                ('insurance_type', '=', 'bhxh'),
                ('state', '=', 'active')
            ], limit=1)
            
            if insurance:
                self.insurance_id = insurance.id
                self.salary_base = insurance.salary_base
    
    @api.onchange('number_of_children', 'child_under_12_months', 'cesarean_section', 'benefit_type', 'is_multiple_birth', 'multiple_birth_count')
    def _onchange_maternity_info(self):
        # Theo quy định đặc thù về thai sản
        if self.benefit_type in ['maternity_leave', 'birth_support']:
            base_days = 180  # 6 tháng (180 ngày) nghỉ thai sản cơ bản
            
            # Nghỉ thai sản - thêm ngày cho sinh đôi trở lên
            if self.benefit_type == 'maternity_leave' and self.is_multiple_birth:
                extra_days = (self.multiple_birth_count - 1) * 30  # Thêm 30 ngày cho mỗi con
                if self.date_from:
                    self.date_to = self.date_from + timedelta(days=base_days + extra_days)
            
            # Nghỉ sinh con - thêm ngày cho sinh mổ
            elif self.benefit_type == 'birth_support' and self.cesarean_section:
                if self.date_from:
                    self.date_to = self.date_from + timedelta(days=7)  # 7 ngày cho sinh mổ thay vì 5 ngày
        
        # Khi đánh dấu là sinh đôi/ba
        if self.is_multiple_birth and self.multiple_birth_count < 2:
            self.multiple_birth_count = 2
    
    @api.onchange('is_birth_benefit')
    def _onchange_is_birth_benefit(self):
        # Tính toán tiền hỗ trợ sinh con theo quy định
        if self.is_birth_benefit:
            # Tiền hỗ trợ sinh con là 2 lần lương cơ sở (cố định theo quy định)
            base_salary = self.env['ir.config_parameter'].sudo().get_param(
                'hr_insurance.base_benefit_salary', default=1800000
            )
            try:
                base_salary = float(base_salary)
            except ValueError:
                base_salary = 1800000  # Giá trị mặc định là 1.8 triệu VND
            
            # Tiền hỗ trợ sinh con là 2 lần lương cơ sở cho mỗi con
            self.benefit_amount = base_salary * 2 * max(1, self.multiple_birth_count if self.is_multiple_birth else 1)
    
    @api.constrains('is_foreign_worker', 'voluntary_insurance')
    def _check_foreign_worker_insurance(self):
        for record in self:
            if record.is_foreign_worker and not record.voluntary_insurance:
                # Kiểm tra xem người lao động nước ngoài có đủ điều kiện hưởng BHXH không
                if record.benefit_type not in ['work_accident', 'retirement']:
                    raise ValidationError(_(
                        'Lao động nước ngoài không tham gia BHXH tự nguyện chỉ được hưởng '
                        'chế độ tai nạn lao động và hưu trí. Vui lòng kiểm tra lại loại trợ cấp.'
                    )) 