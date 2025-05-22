# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta, date


class SocialInsuranceDocument(models.Model):
    _name = 'social.insurance.document'
    _description = 'Social Insurance Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(string='Mã tài liệu', required=True, copy=False, readonly=True, 
                       default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, tracking=True)
    insurance_id = fields.Many2one('hr.insurance', string='Bảo hiểm liên quan', 
                                 domain="[('employee_id', '=', employee_id), "
                                         "('insurance_type', '=', 'bhxh')]", 
                                 tracking=True)
    
    document_type = fields.Selection([
        ('registration', 'Đăng ký mới'),
        ('adjustment', 'Điều chỉnh thông tin'),
        ('termination', 'Chấm dứt tham gia'),
        ('unemployment', 'Trợ cấp thất nghiệp'),
        ('bhyt_card', 'Thẻ BHYT'),
        ('bhxh_book', 'Sổ BHXH'),
        ('tk1_ts', 'Mẫu TK1-TS'),
        ('tk3_ts', 'Mẫu TK3-TS'),
        ('other', 'Khác'),
    ], string='Loại tài liệu', required=True, tracking=True)
    
    adjustment_type = fields.Selection([
        ('personal_info', 'Thông tin cá nhân'),
        ('salary', 'Mức lương đóng BHXH'),
        ('workplace', 'Nơi làm việc'),
        ('other', 'Khác'),
    ], string='Loại điều chỉnh', tracking=True)
    
    reference = fields.Char(string='Số tham chiếu', tracking=True,
                          help='Số tham chiếu của cơ quan BHXH')
    date = fields.Date(string='Ngày tạo', required=True, default=fields.Date.today, tracking=True)
    deadline = fields.Date(string='Hạn nộp', tracking=True)
    submit_date = fields.Date(string='Ngày nộp', tracking=True)
    approval_date = fields.Date(string='Ngày duyệt', tracking=True)
    
    # Thông tin thẻ BHYT
    bhyt_number = fields.Char(string='Số thẻ BHYT', tracking=True)
    bhyt_issue_date = fields.Date(string='Ngày cấp thẻ BHYT', tracking=True)
    bhyt_expiry_date = fields.Date(string='Ngày hết hạn thẻ BHYT', tracking=True)
    bhyt_hospital = fields.Char(string='Nơi khám chữa bệnh ban đầu', tracking=True)
    is_bhyt_expired = fields.Boolean(string='Thẻ BHYT hết hạn', compute='_compute_bhyt_expired', store=True)
    days_to_expire = fields.Integer(string='Số ngày còn hạn', compute='_compute_bhyt_expired', store=True)
    
    # Thông tin sổ BHXH
    bhxh_book_number = fields.Char(string='Số sổ BHXH', tracking=True,
                                  help='Số sổ bảo hiểm xã hội của nhân viên')
    bhxh_book_issue_date = fields.Date(string='Ngày cấp sổ BHXH', tracking=True)
    bhxh_book_issue_place = fields.Char(string='Nơi cấp sổ BHXH', tracking=True)
    
    notes = fields.Text(string='Ghi chú')
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu đính kèm')
    
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('submitted', 'Đã nộp'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Bị từ chối'),
        ('cancelled', 'Đã hủy'),
    ], string='Trạng thái', default='draft', tracking=True)
    
    # Thông tin người phụ trách
    officer_id = fields.Many2one('res.users', string='Người phụ trách', 
                               default=lambda self: self.env.user, 
                               tracking=True)
    
    # Thông tin điều chỉnh
    old_value = fields.Char(string='Giá trị cũ', tracking=True)
    new_value = fields.Char(string='Giá trị mới', tracking=True)
    
    # Thông tin từ cơ quan BHXH
    agency_response = fields.Text(string='Phản hồi từ cơ quan BHXH', tracking=True)
    agency_officer = fields.Char(string='Cán bộ BHXH phụ trách', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    
    # Xử lý các trường liên quan đến mô hình tài liệu 
    # Lưu trữ nhưng không hiển thị trên giao diện để tránh lỗi
    related_document_model = fields.Char(string='Mã tài liệu liên quan', groups='base.group_no_one', store=True, default='social.insurance.document')
    related_document_id = fields.Integer(string='ID tài liệu liên quan', groups='base.group_no_one', store=True, default=0)
    related_partner = fields.Char(string='Đối tác liên quan', groups='base.group_no_one', store=True, default=False)
    
    @api.depends('bhyt_expiry_date')
    def _compute_bhyt_expired(self):
        today = fields.Date.today()
        for record in self:
            if record.bhyt_expiry_date:
                record.is_bhyt_expired = record.bhyt_expiry_date < today
                delta = record.bhyt_expiry_date - today
                record.days_to_expire = delta.days if delta.days > 0 else 0
            else:
                record.is_bhyt_expired = False
                record.days_to_expire = 0
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('social.insurance.document') or _('New')
            # Đảm bảo các trường related_document đều có giá trị
            if 'related_document_model' not in vals or not vals.get('related_document_model'):
                vals['related_document_model'] = 'social.insurance.document' 
            if 'related_document_id' not in vals or not vals.get('related_document_id'):
                vals['related_document_id'] = 0
            if 'related_partner' not in vals or not vals.get('related_partner'):
                vals['related_partner'] = False
        return super(SocialInsuranceDocument, self).create(vals_list)
    
    def action_submit(self):
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(_('Vui lòng đính kèm ít nhất một tài liệu trước khi nộp.'))
        
        self.write({
            'state': 'submitted',
            'submit_date': fields.Date.today(),
        })
        
        # Log activity for HR manager to follow up
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=_('Theo dõi tiến độ hồ sơ BHXH'),
            note=_('Hồ sơ %s của nhân viên %s đã được nộp lên cơ quan BHXH. Vui lòng theo dõi tiến độ.') % 
                 (self.name, self.employee_id.name),
            user_id=self.officer_id.id
        )
    
    def action_approve(self):
        self.ensure_one()
        
        self.write({
            'state': 'approved',
            'approval_date': fields.Date.today(),
        })
        
        # Cập nhật trạng thái BHXH của nhân viên tùy theo loại tài liệu
        if self.document_type == 'registration':
            self.employee_id.write({'social_insurance_status': 'active'})
        elif self.document_type == 'bhxh_book':
            self.employee_id.write({
                'social_insurance_status': 'active',
                'social_insurance_code': self.bhxh_book_number,
                'social_insurance_issue_date': self.bhxh_book_issue_date
            })
        elif self.document_type == 'bhyt_card':
            # Cập nhật thông tin thẻ BHYT cho nhân viên
            bhyt_insurance = self.env['hr.insurance'].search([
                ('employee_id', '=', self.employee_id.id),
                ('insurance_type', '=', 'bhyt'),
                ('state', '=', 'active')
            ], limit=1)
            
            if bhyt_insurance:
                bhyt_insurance.write({
                    'policy_number': self.bhyt_number,
                    'date_to': self.bhyt_expiry_date
                })
            
        elif self.document_type == 'termination':
            self.employee_id.write({'social_insurance_status': 'suspended'})
            
            # Cập nhật trạng thái hồ sơ bảo hiểm liên quan
            if self.insurance_id:
                self.insurance_id.action_expire()
    
    def action_reject(self):
        self.write({'state': 'rejected'})
        
        # Tạo hoạt động để xử lý lại hồ sơ
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=_('Hồ sơ BHXH bị từ chối'),
            note=_('Hồ sơ %s của nhân viên %s đã bị cơ quan BHXH từ chối. Vui lòng kiểm tra lại.') % 
                 (self.name, self.employee_id.name),
            user_id=self.create_uid.id
        )
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        self.write({'state': 'draft'})
    
    def action_generate_form(self):
        """Generate BHXH form based on document type"""
        self.ensure_one()
        
        if self.document_type in ['registration', 'tk1_ts']:
            return self._generate_registration_form()
        elif self.document_type in ['adjustment', 'tk3_ts']:
            return self._generate_adjustment_form()
        elif self.document_type == 'termination':
            return self._generate_termination_form()
        elif self.document_type == 'unemployment':
            return self._generate_unemployment_form()
        else:
            raise UserError(_('Không hỗ trợ tạo biểu mẫu cho loại tài liệu này.'))
    
    def _generate_registration_form(self):
        """Generate registration form"""
        # In real implementation, this would generate the appropriate TK1-TS form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'social.insurance.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_document_id': self.id, 'default_form_type': 'tk1_ts'}
        }
    
    def _generate_adjustment_form(self):
        """Generate adjustment form"""
        # In real implementation, this would generate the appropriate TK3-TS form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'social.insurance.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_document_id': self.id, 'default_form_type': 'tk3_ts'}
        }
    
    def _generate_termination_form(self):
        """Generate termination form"""
        # In real implementation, this would generate the appropriate form
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'social.insurance.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_document_id': self.id, 'default_form_type': 'termination'}
        }
    
    def _generate_unemployment_form(self):
        """Generate unemployment benefit form"""
        # In real implementation, this would generate the appropriate form for unemployment benefits
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'social.insurance.print.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_document_id': self.id, 'default_form_type': 'unemployment'}
        } 