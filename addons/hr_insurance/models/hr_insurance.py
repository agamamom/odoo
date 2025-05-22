# -*- coding: utf-8 -*-
#############################################################################
#   A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#    Copyright (C) 2025-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Raneesha M K (<https://www.cybrosys.com>)
#
#    You can modify it under the terms of the GNU LESSER
#    GENERAL PUBLIC LICENSE (LGPL v3), Version 3.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU LESSER GENERAL PUBLIC LICENSE (LGPL v3) for more details.
#
#    You should have received a copy of the GNU LESSER GENERAL PUBLIC LICENSE
#    (LGPL v3) along with this program.
#    If not, see <http://www.gnu.org/licenses/>.
#
#############################################################################
from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta, date
from dateutil.relativedelta import relativedelta


class HrInsurance(models.Model):
    """Created a new model for employee insurance"""
    _name = 'hr.insurance'
    _description = 'HR Insurance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'
    _rec_name = 'employee_id'

    name = fields.Char(string='Mã tham chiếu', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, tracking=True)
    
    # Xử lý các trường liên quan đến mô hình tài liệu 
    # Lưu trữ nhưng không hiển thị trên giao diện để tránh lỗi
    related_document_model = fields.Char(string='Mã tài liệu liên quan', groups='base.group_no_one', store=True, default='hr.insurance')
    related_document_id = fields.Integer(string='ID tài liệu liên quan', groups='base.group_no_one', store=True, default=0)
    related_partner = fields.Char(string='Đối tác liên quan', groups='base.group_no_one', store=True, default=False)
    
    policy_id = fields.Many2one('insurance.policy', string='Hợp đồng bảo hiểm', required=True, tracking=True)
    insurance_type = fields.Selection([
        ('bhxh', 'Bảo hiểm xã hội (BHXH)'),
        ('bhyt', 'Bảo hiểm y tế (BHYT)'),
        ('bhtn', 'Bảo hiểm thất nghiệp (BHTN)'),
    ], string='Loại bảo hiểm', required=True, tracking=True)
    
    # Extended insurance coverage types
    insurance_coverage_type = fields.Selection([
        ('none', 'Tiêu chuẩn'),
        ('sickness', 'Ốm đau'),
        ('maternity', 'Thai sản'),
        ('work_accident', 'Tai nạn lao động'),
        ('occupational_disease', 'Bệnh nghề nghiệp'),
        ('retirement', 'Hưu trí'),
        ('death', 'Tử tuất'),
        ('voluntary', 'Tự nguyện')
    ], string='Phạm vi bảo hiểm', default='none', tracking=True)
    
    is_voluntary = fields.Boolean(string='Bảo hiểm tự nguyện', default=False, tracking=True,
        help='Đánh dấu nếu đây là bảo hiểm tự nguyện nhân viên tham gia thêm')
    
    policy_number = fields.Char(string='Số hợp đồng/Mã bảo hiểm', tracking=True)
    social_insurance_code = fields.Char(string='Mã số BHXH', tracking=True)
    date_from = fields.Date(string='Từ ngày', required=True, default=fields.Date.today, tracking=True)
    date_to = fields.Date(string='Đến ngày', tracking=True)
    
    amount = fields.Float(string='Số tiền bảo hiểm', tracking=True)
    sum_insured = fields.Float(string="Tổng giá trị BH", required=True,
                              help="Tổng giá trị được bảo hiểm")
    is_social_insurance = fields.Boolean(string='Là BHXH', compute='_compute_is_social_insurance', store=True)
    wage_base = fields.Float(string='Lương cơ bản', help="Lương cơ bản dùng để tính bảo hiểm")
    allowances = fields.Float(string='Phụ cấp chịu bảo hiểm', 
                              help="Các khoản phụ cấp chịu đóng bảo hiểm")
    salary_base = fields.Float(string='Lương cơ bản đóng BH', required=True, tracking=True,
                             help='Lương cơ bản dùng để tính bảo hiểm')
    # Contributions
    employee_contribution = fields.Float(string='NV đóng', compute='_compute_contributions', store=True)
    company_contribution = fields.Float(string='Công ty đóng', compute='_compute_contributions', store=True)
    total_contribution = fields.Float(string='Tổng cộng', compute='_compute_contributions', store=True)
    
    policy_coverage = fields.Selection([('monthly', 'Hàng tháng'),
                                        ('yearly', 'Hàng năm')],
                                       required=True, default='monthly',
                                       string='Chính sách bảo hiểm',
                                       help="Duration of the policy")
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('active', 'Đang hoạt động'),
        ('expired', 'Hết hạn'),
        ('cancelled', 'Đã hủy'),
    ], string='Trạng thái', default='draft', tracking=True)
    
    notes = fields.Text(string='Ghi chú')
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu')
    
    # Company
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    
    # Allowance tracking
    allowance_ids = fields.One2many('insurance.allowance', 'insurance_id', string='Trợ cấp')
    
    @api.depends('insurance_type')
    def _compute_is_social_insurance(self):
        for insurance in self:
            insurance.is_social_insurance = insurance.insurance_type == 'bhxh'
    
    @api.depends('policy_id', 'salary_base')
    def _compute_contributions(self):
        for insurance in self:
            if insurance.policy_id and insurance.salary_base:
                insurance.employee_contribution = insurance.salary_base * insurance.policy_id.employee_rate / 100
                insurance.company_contribution = insurance.salary_base * insurance.policy_id.company_rate / 100
                insurance.total_contribution = insurance.employee_contribution + insurance.company_contribution
            else:
                insurance.employee_contribution = 0.0
                insurance.company_contribution = 0.0
                insurance.total_contribution = 0.0
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('hr.insurance') or _('New')
            # Đảm bảo các trường related_document đều có giá trị
            if 'related_document_model' not in vals or not vals.get('related_document_model'):
                vals['related_document_model'] = 'hr.insurance' 
            if 'related_document_id' not in vals or not vals.get('related_document_id'):
                vals['related_document_id'] = 0
            if 'related_partner' not in vals or not vals.get('related_partner'):
                vals['related_partner'] = False
        return super(HrInsurance, self).create(vals_list)
    
    def action_confirm(self):
        self.write({'state': 'active'})
    
    def action_expire(self):
        self.write({'state': 'expired'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        self.write({'state': 'draft'})
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for insurance in self:
            if insurance.date_to and insurance.date_from > insurance.date_to:
                raise ValidationError(_("Ngày kết thúc phải sau ngày bắt đầu."))
    
    def _compute_check_expired(self):
        today = fields.Date.today()
        for insurance in self:
            if insurance.date_to and insurance.date_to < today and insurance.state == 'active':
                insurance.state = 'expired'
                
    @api.model
    def _cron_check_insurance_expiry(self):
        """Scheduled action to check insurance expiry"""
        to_expire = self.search([
            ('state', '=', 'active'),
            ('date_to', '<', fields.Date.today())
        ])
        if to_expire:
            to_expire.write({'state': 'expired'})
            
        # Notify about insurance expiring soon
        soon_to_expire = self.search([
            ('state', '=', 'active'),
            ('date_to', '>=', fields.Date.today()),
            ('date_to', '<=', fields.Date.today() + timedelta(days=30))
        ])
        
        for insurance in soon_to_expire:
            remaining_days = (insurance.date_to - fields.Date.today()).days
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'note': _('Bảo hiểm của nhân viên %s sẽ hết hạn sau %s ngày. Vui lòng gia hạn kịp thời.') % 
                        (insurance.employee_id.name, remaining_days),
                'res_id': insurance.id,
                'res_model_id': self.env['ir.model'].search([('model', '=', 'hr.insurance')], limit=1).id,
                'user_id': self.env.user.id,
                'summary': _('Bảo hiểm sắp hết hạn'),
            })
        
        # Check BHYT card expiration
        self._check_bhyt_card_expiration()
        
        return True
    
    @api.model
    def _check_bhyt_card_expiration(self):
        """Check and notify about BHYT card expiration"""
        bhyt_cards = self.env['social.insurance.document'].search([
            ('document_type', '=', 'bhyt_card'),
            ('state', '=', 'approved'),
            ('bhyt_expiry_date', '>=', fields.Date.today()),
            ('bhyt_expiry_date', '<=', fields.Date.today() + timedelta(days=30))
        ])
        
        for card in bhyt_cards:
            remaining_days = (card.bhyt_expiry_date - fields.Date.today()).days
            
            # Create activity for HR responsible
            hr_manager = self.env.ref('hr.group_hr_manager').users[0] if self.env.ref('hr.group_hr_manager').users else self.env.user
            
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'note': _('Thẻ BHYT của nhân viên %s sẽ hết hạn sau %s ngày. Vui lòng gia hạn kịp thời.') % 
                        (card.employee_id.name, remaining_days),
                'res_id': card.id,
                'res_model_id': self.env['ir.model'].search([('model', '=', 'social.insurance.document')], limit=1).id,
                'user_id': hr_manager.id,
                'summary': _('Thẻ BHYT sắp hết hạn'),
                'date_deadline': fields.Date.today() + timedelta(days=5)
            })
            
        # Check for expired BHYT cards
        expired_cards = self.env['social.insurance.document'].search([
            ('document_type', '=', 'bhyt_card'),
            ('state', '=', 'approved'),
            ('bhyt_expiry_date', '<', fields.Date.today()),
            ('is_bhyt_expired', '=', True)
        ])
        
        for card in expired_cards:
            # Find BHYT insurance and mark as expired
            bhyt_insurance = self.search([
                ('employee_id', '=', card.employee_id.id),
                ('insurance_type', '=', 'bhyt'),
                ('state', '=', 'active')
            ], limit=1)
            
            if bhyt_insurance:
                bhyt_insurance.write({'state': 'expired'})
                
                # Create notification
                self.env['mail.activity'].create({
                    'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                    'note': _('Thẻ BHYT của nhân viên %s đã hết hạn. Cần gia hạn ngay lập tức!') % 
                            (card.employee_id.name),
                    'res_id': card.id,
                    'res_model_id': self.env['ir.model'].search([('model', '=', 'social.insurance.document')], limit=1).id,
                    'user_id': self.env.user.id,
                    'summary': _('Thẻ BHYT đã hết hạn'),
                    'date_deadline': fields.Date.today()
                })
        
        return True
    
    @api.model
    def _cron_remind_d02_ts_report(self):
        """Nhắc nhở nộp báo cáo D02-TS định kỳ hàng tháng"""
        # Tìm những người dùng có quyền quản lý báo cáo bảo hiểm
        users = self.env.ref('hr_insurance.group_insurance_manager').users
        if not users:
            users = self.env.ref('hr.group_hr_manager').users
            
        # Xác định tháng cần báo cáo (tháng trước)
        current_date = fields.Date.today()
        previous_month = current_date - relativedelta(months=1)
        month_str = previous_month.strftime('%m/%Y')
        
        # Thời hạn nộp báo cáo (thường là ngày 10 hàng tháng)
        deadline = current_date.replace(day=10)
        if current_date.day > 10:
            deadline = (current_date + relativedelta(months=1)).replace(day=10)
            
        # Tạo thông báo nhắc nhở
        note = _("Cần nộp báo cáo D02-TS (Tình hình sử dụng lao động và đóng BHXH) của tháng %s trước ngày %s") % (
            month_str, deadline.strftime('%d/%m/%Y')
        )
        
        # Tạo hoạt động nhắc nhở cho từng người dùng
        activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
        for user in users:
            self.env['mail.activity'].create({
                'activity_type_id': activity_type_id,
                'note': note,
                'user_id': user.id,
                'res_id': self.env.company.id,
                'res_model_id': self.env.ref('base.model_res_company').id,
                'summary': _('Nhắc nhở nộp báo cáo D02-TS'),
                'date_deadline': deadline,
            })
            
    @api.model
    def _cron_remind_d03_ts_report(self):
        """Nhắc nhở nộp báo cáo D03-TS định kỳ hàng quý"""
        # Tìm những người dùng có quyền quản lý báo cáo bảo hiểm
        users = self.env.ref('hr_insurance.group_insurance_manager').users
        if not users:
            users = self.env.ref('hr.group_hr_manager').users
            
        # Xác định quý cần báo cáo
        current_date = fields.Date.today()
        current_month = current_date.month
        current_quarter = (current_month - 1) // 3 + 1
        
        # Nếu đang ở tháng đầu quý, báo cáo quý trước, ngược lại thì báo cáo quý hiện tại
        if current_month in [1, 4, 7, 10]:
            # Báo cáo quý trước
            if current_month == 1:
                quarter = 4
                year = current_date.year - 1
            else:
                quarter = current_quarter - 1
                year = current_date.year
        else:
            # Báo cáo quý hiện tại
            quarter = current_quarter
            year = current_date.year
            
        # Thời hạn nộp báo cáo (thường là ngày 15 của tháng đầu tiên trong quý tiếp theo)
        deadline_month = (quarter * 3) % 12 + 1
        deadline_year = year if deadline_month > 1 else year + 1
        deadline = date(deadline_year, deadline_month, 15)
        
        if deadline < current_date:
            deadline = deadline + relativedelta(months=3)
            
        # Tạo thông báo nhắc nhở
        note = _("Cần nộp báo cáo D03-TS (Thay đổi thông tin người tham gia BHXH) của quý %s/%s trước ngày %s") % (
            quarter, year, deadline.strftime('%d/%m/%Y')
        )
        
        # Tạo hoạt động nhắc nhở cho từng người dùng
        activity_type_id = self.env.ref('mail.mail_activity_data_todo').id
        for user in users:
            self.env['mail.activity'].create({
                'activity_type_id': activity_type_id,
                'note': note,
                'user_id': user.id,
                'res_id': self.env.company.id,
                'res_model_id': self.env.ref('base.model_res_company').id,
                'summary': _('Nhắc nhở nộp báo cáo D03-TS'),
                'date_deadline': deadline,
            })

class InsuranceAllowance(models.Model):
    _name = 'insurance.allowance'
    _description = 'Insurance Allowance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(string='Mã trợ cấp', required=True, copy=False, readonly=True, 
                      default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, tracking=True)
    
    # Xử lý các trường liên quan đến mô hình tài liệu 
    # Lưu trữ nhưng không hiển thị trên giao diện để tránh lỗi
    related_document_model = fields.Char(string='Mã tài liệu liên quan', groups='base.group_no_one', store=True, default='insurance.allowance')
    related_document_id = fields.Integer(string='ID tài liệu liên quan', groups='base.group_no_one', store=True, default=0)
    related_partner = fields.Char(string='Đối tác liên quan', groups='base.group_no_one', store=True, default=False)
    
    insurance_id = fields.Many2one('hr.insurance', string='Bảo hiểm liên quan', 
                                  domain="[('employee_id', '=', employee_id)]", tracking=True)
    allowance_type = fields.Selection([
        ('sickness', 'Ốm đau'),
        ('maternity', 'Thai sản'),
        ('work_accident', 'Tai nạn lao động'),
        ('occupational_disease', 'Bệnh nghề nghiệp'),
        ('unemployment', 'Thất nghiệp'),
        ('other', 'Khác'),
    ], string='Loại trợ cấp', required=True, tracking=True)
    
    date = fields.Date(string='Ngày nhận', required=True, default=fields.Date.today, tracking=True)
    amount = fields.Float(string='Số tiền', required=True, tracking=True)
    payment_method = fields.Selection([
        ('bank', 'Chuyển khoản'),
        ('cash', 'Tiền mặt'),
        ('other', 'Khác'),
    ], string='Phương thức thanh toán', default='bank', tracking=True)
    
    reference = fields.Char(string='Số tham chiếu', tracking=True)
    notes = fields.Text(string='Ghi chú')
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu đính kèm')
    
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('approved', 'Đã duyệt'),
        ('paid', 'Đã trả'),
        ('cancelled', 'Đã hủy'),
    ], string='Trạng thái', default='draft', tracking=True)
    
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('insurance.allowance') or _('New')
            # Đảm bảo các trường related_document đều có giá trị
            if 'related_document_model' not in vals or not vals.get('related_document_model'):
                vals['related_document_model'] = 'insurance.allowance' 
            if 'related_document_id' not in vals or not vals.get('related_document_id'):
                vals['related_document_id'] = 0
            if 'related_partner' not in vals or not vals.get('related_partner'):
                vals['related_partner'] = False
        return super(InsuranceAllowance, self).create(vals_list)
    
    def action_approve(self):
        self.write({'state': 'approved'})
    
    def action_pay(self):
        self.write({'state': 'paid'})
    
    def action_cancel(self):
        self.write({'state': 'cancelled'})
    
    def action_draft(self):
        self.write({'state': 'draft'})
