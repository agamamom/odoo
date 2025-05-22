# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError


class InsuranceDocumentTemplate(models.Model):
    _name = 'insurance.document.template'
    _description = 'Mẫu tài liệu bảo hiểm'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Tên mẫu', required=True, tracking=True)
    code = fields.Char(string='Mã mẫu', tracking=True)
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
    
    # Hide document relationship fields
    related_document_model = fields.Char(invisible=True)
    related_document_id = fields.Integer(invisible=True)
    related_partner = fields.Many2one('res.partner', invisible=True)
    
    description = fields.Text(string='Mô tả', tracking=True)
    
    # Thông tin điều chỉnh mặc định
    adjustment_type = fields.Selection([
        ('personal', 'Thông tin cá nhân'),
        ('salary', 'Lương đóng bảo hiểm'),
        ('position', 'Vị trí công việc'),
        ('other', 'Thông tin khác'),
    ], string='Loại điều chỉnh', tracking=True)
    
    # Thông tin thẻ BHYT mặc định
    default_bhyt_hospital = fields.Char(string='Bệnh viện đăng ký BHYT mặc định', tracking=True)
    
    # Thông tin sổ BHXH mặc định
    default_bhxh_book_issue_place = fields.Char(string='Nơi cấp sổ BHXH mặc định', tracking=True)
    
    # Thiết lập tự động
    auto_set_deadline = fields.Boolean(string='Tự động thiết lập hạn nộp', default=False, tracking=True)
    days_deadline = fields.Integer(string='Số ngày hạn nộp', default=7, tracking=True)
    auto_set_officer = fields.Boolean(string='Tự động chỉ định nhân viên xử lý', default=False, tracking=True)
    default_officer_id = fields.Many2one('hr.employee', string='Nhân viên xử lý mặc định', tracking=True)
    
    # Ghi chú mặc định
    default_notes = fields.Text(string='Ghi chú mặc định', tracking=True)
    
    # Tài liệu mặc định
    default_attachment_ids = fields.Many2many('ir.attachment', 
                                            string='Tài liệu mẫu đính kèm',
                                            relation='insurance_document_template_attachment_rel',
                                            column1='template_id', column2='attachment_id')
    
    # Thiết lập an ninh
    company_id = fields.Many2one('res.company', string='Công ty', 
                               default=lambda self: self.env.company,
                               tracking=True)
    active = fields.Boolean(string='Đang hoạt động', default=True, tracking=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('code'):
                vals['code'] = self.env['ir.sequence'].next_by_code('insurance.document.template') or _('New')
        return super(InsuranceDocumentTemplate, self).create(vals_list)
    
    def action_create_document(self):
        """Open wizard to create document from template"""
        self.ensure_one()
        return {
            'name': _('Tạo tài liệu từ mẫu'),
            'type': 'ir.actions.act_window',
            'res_model': 'insurance.document.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
            }
        } 