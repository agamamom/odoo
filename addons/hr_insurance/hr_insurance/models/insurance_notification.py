# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError
from datetime import datetime, date
from dateutil.relativedelta import relativedelta
import logging
import pytz

_logger = logging.getLogger(__name__)


class InsuranceNotification(models.Model):
    _name = 'insurance.notification'
    _description = 'Thông báo bảo hiểm xã hội'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Tiêu đề', required=True, tracking=True)
    date = fields.Date(string='Ngày thông báo', required=True, default=fields.Date.today, tracking=True)
    
    # Bỏ các fields không tồn tại 
    related_document_model = fields.Char(string='Related Document Model', store=False, compute="_compute_dummy")
    related_document_id = fields.Integer(string='Related Document ID', store=False, compute="_compute_dummy")
    
    @api.depends('name')
    def _compute_dummy(self):
        """Hàm tính toán giả để hỗ trợ các trường dummy"""
        for record in self:
            record.related_document_model = False
            record.related_document_id = False
    
    type = fields.Selection([
        ('deadline', 'Hạn nộp báo cáo/hồ sơ'),
        ('policy_change', 'Thay đổi chính sách'),
        ('payment_reminder', 'Nhắc nhở thanh toán'),
        ('document_reminder', 'Nhắc nhở hồ sơ'),
        ('quarterly_report', 'Báo cáo quý BHXH'),
        ('annual_adjust', 'Điều chỉnh mức đóng hằng năm'),
        ('form_changes', 'Thay đổi mẫu biểu BHXH'),
        ('giam_dinh', 'Giám định BHXH/BHYT'),
        ('other', 'Khác')
    ], string='Loại thông báo', required=True, default='deadline', tracking=True)
    
    content = fields.Html(string='Nội dung', required=True, tracking=True)
    notification_date = fields.Datetime(string='Thời điểm gửi thông báo', tracking=True)
    
    deadline_date = fields.Date(string='Ngày hạn chót', tracking=True)
    days_before = fields.Integer(string='Số ngày thông báo trước hạn', default=5,
                              help='Số ngày gửi thông báo trước ngày hạn chót')
    
    department_ids = fields.Many2many('hr.department', string='Phòng ban',
                                     help='Để trống nếu áp dụng cho tất cả phòng ban')
    
    employee_ids = fields.Many2many('hr.employee', string='Nhân viên',
                                   help='Để trống nếu áp dụng cho tất cả nhân viên')
    
    recipient_ids = fields.Many2many('res.users', string='Người nhận',
                                    help='Người nhận thông báo')
    
    is_hr_only = fields.Boolean(string='Chỉ gửi cho HR', default=False,
                              help='Nếu được chọn, thông báo chỉ gửi cho nhân viên HR')
    
    is_urgent = fields.Boolean(string='Khẩn cấp', default=False, tracking=True,
                               help='Đánh dấu nếu thông báo có tính chất khẩn cấp')
    
    document_type = fields.Selection([
        ('form_d01_ts', 'Mẫu D01-TS'),
        ('form_d02_ts', 'Mẫu D02-TS'),
        ('form_d03_ts', 'Mẫu D03-TS'),
        ('form_01_bhyt', 'Mẫu 01-BHYT'),
        ('form_01_bhxh', 'Mẫu 01-BHXH'),
        ('form_thoilao', 'Mẫu thôi lao động'),
        ('form_c12_bhxh', 'Mẫu C12-BHXH'),
        ('none', 'Không liên quan')
    ], string='Liên quan đến mẫu', default='none', tracking=True)
    
    related_agency = fields.Selection([
        ('bhxh_quan', 'BHXH Quận/Huyện'),
        ('bhxh_tinh', 'BHXH Tỉnh/Thành phố'),
        ('bhxh_vn', 'BHXH Việt Nam'),
        ('bo_ldtbxh', 'Bộ LĐTBXH'),
        ('none', 'Không liên quan')
    ], string='Cơ quan liên quan', default='none', tracking=True)
    
    recurrence_type = fields.Selection([
        ('none', 'Không lặp lại'),
        ('daily', 'Hàng ngày'),
        ('weekly', 'Hàng tuần'),
        ('monthly', 'Hàng tháng'),
        ('quarterly', 'Hàng quý'),
        ('yearly', 'Hàng năm')
    ], string='Lặp lại', default='none', tracking=True,
       help='Thiết lập lịch lặp lại cho thông báo')
    
    recurrence_interval = fields.Integer(string='Khoảng thời gian', default=1,
                                      help='Khoảng thời gian giữa các lần lặp lại')
    
    next_recurrence_date = fields.Date(string='Ngày lặp lại tiếp theo', tracking=True)
    
    state = fields.Selection([
        ('draft', 'Dự thảo'),
        ('scheduled', 'Đã lên lịch'),
        ('sent', 'Đã gửi'),
        ('cancelled', 'Đã hủy')
    ], string='Trạng thái', default='draft', tracking=True)
    
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu đính kèm')
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    
    send_email = fields.Boolean(string='Gửi email', default=True,
                             help='Gửi thông báo qua email')
    
    send_notification = fields.Boolean(string='Gửi thông báo hệ thống', default=True,
                                    help='Gửi thông báo qua hệ thống Odoo')
    
    send_sms = fields.Boolean(string='Gửi SMS', default=False, 
                            help='Gửi thông báo qua tin nhắn SMS')
    
    sms_template_id = fields.Many2one('sms.template', string='Mẫu SMS',
                                    domain="[('model', '=', 'insurance.notification')]")
    
    @api.model
    def _get_default_recipients(self):
        """Lấy danh sách người dùng mặc định nhận thông báo (nhân viên HR)"""
        hr_group = self.env.ref('hr.group_hr_manager', raise_if_not_found=False)
        if hr_group:
            return hr_group.users.ids
        return []
    
    @api.onchange('is_hr_only')
    def _onchange_is_hr_only(self):
        """Cập nhật danh sách người nhận khi chọn chỉ gửi cho HR"""
        if self.is_hr_only:
            self.recipient_ids = [(6, 0, self._get_default_recipients())]
        else:
            self.recipient_ids = False
    
    @api.onchange('type', 'document_type')
    def _onchange_type(self):
        """Thiết lập các giá trị mặc định dựa trên loại thông báo"""
        if self.type == 'deadline':
            self.name = 'Nhắc nhở: Hạn nộp hồ sơ BHXH tháng ' + fields.Date.today().strftime('%m/%Y')
            
            # Tính toán ngày hạn chót (mặc định là 10 ngày sau ngày cuối tháng)
            last_day = date(fields.Date.today().year, fields.Date.today().month, 1) + relativedelta(months=1, days=-1)
            self.deadline_date = last_day + relativedelta(days=10)
            
            self.content = """
                <p>Kính gửi các anh/chị,</p>
                <p>Phòng Nhân sự trân trọng thông báo:</p>
                <p>Hạn nộp báo cáo và đóng BHXH cho tháng {month}/{year} là ngày <strong>{deadline}</strong>.</p>
                <p>Vui lòng chuẩn bị đầy đủ hồ sơ và thanh toán đúng hạn để tránh phát sinh phí phạt chậm nộp.</p>
                <p>Trân trọng thông báo.</p>
            """.format(
                month=self.deadline_date.strftime('%m'),
                year=self.deadline_date.strftime('%Y'),
                deadline=self.deadline_date.strftime('%d/%m/%Y')
            )
        
        elif self.type == 'policy_change':
            self.name = 'Thông báo: Thay đổi chính sách BHXH'
            self.content = """
                <p>Kính gửi các anh/chị,</p>
                <p>Phòng Nhân sự trân trọng thông báo về những thay đổi trong chính sách BHXH mới nhất:</p>
                <ul>
                    <li>Điểm thay đổi 1</li>
                    <li>Điểm thay đổi 2</li>
                </ul>
                <p>Những thay đổi này sẽ có hiệu lực từ ngày [Ngày hiệu lực].</p>
                <p>Mọi thắc mắc vui lòng liên hệ phòng Nhân sự để được giải đáp.</p>
                <p>Trân trọng thông báo.</p>
            """
            
        elif self.type == 'payment_reminder':
            self.name = 'Nhắc nhở: Thanh toán BHXH tháng ' + fields.Date.today().strftime('%m/%Y')
            self.content = """
                <p>Kính gửi các anh/chị,</p>
                <p>Phòng Nhân sự trân trọng nhắc nhở:</p>
                <p>Vui lòng hoàn tất thanh toán BHXH cho tháng {month}/{year} trước ngày <strong>{deadline}</strong>.</p>
                <p>Hiện tại còn [X] ngày nữa đến hạn.</p>
                <p>Trân trọng thông báo.</p>
            """.format(
                month=fields.Date.today().strftime('%m'),
                year=fields.Date.today().strftime('%Y'),
                deadline=self.deadline_date.strftime('%d/%m/%Y') if self.deadline_date else "[Ngày hạn chót]"
            )
        
        elif self.type == 'quarterly_report':
            quarter = (fields.Date.today().month - 1) // 3 + 1
            year = fields.Date.today().year
            self.name = f'Nhắc nhở: Báo cáo quý {quarter}/{year} BHXH'
            
            # Deadline is 15 days after the end of quarter
            quarter_end_month = quarter * 3
            quarter_end = date(year, quarter_end_month, 1) + relativedelta(months=1, days=-1)
            self.deadline_date = quarter_end + relativedelta(days=15)
            
            self.content = f"""
                <p>Kính gửi các anh/chị,</p>
                <p>Phòng Nhân sự trân trọng thông báo:</p>
                <p>Hạn nộp báo cáo BHXH quý {quarter}/{year} là ngày <strong>{self.deadline_date.strftime('%d/%m/%Y')}</strong>.</p>
                <p>Các báo cáo cần nộp bao gồm:</p>
                <ul>
                    <li>Báo cáo tình hình sử dụng lao động</li>
                    <li>Báo cáo tăng giảm lao động</li>
                    <li>Báo cáo điều chỉnh mức đóng (nếu có)</li>
                </ul>
                <p>Vui lòng chuẩn bị đầy đủ hồ sơ để nộp đúng hạn.</p>
                <p>Trân trọng thông báo.</p>
            """
        
        elif self.type == 'annual_adjust':
            year = fields.Date.today().year
            self.name = f'Thông báo: Điều chỉnh mức đóng BHXH năm {year}'
            self.deadline_date = date(year, 1, 31)
            
            self.content = f"""
                <p>Kính gửi các anh/chị,</p>
                <p>Phòng Nhân sự trân trọng thông báo:</p>
                <p>Theo quy định, đầu năm {year} công ty sẽ điều chỉnh mức đóng BHXH theo lương cơ sở mới.</p>
                <p>Vui lòng rà soát thông tin lương và cập nhật mức đóng BHXH cho tất cả nhân viên trước ngày <strong>{self.deadline_date.strftime('%d/%m/%Y')}</strong>.</p>
                <p>Trân trọng thông báo.</p>
            """
            
        elif self.type == 'form_changes':
            self.name = 'Thông báo: Thay đổi mẫu biểu BHXH'
            
            if self.document_type != 'none':
                doc_type_name = dict(self._fields['document_type'].selection).get(self.document_type)
                self.name = f'Thông báo: Thay đổi {doc_type_name}'
                
                self.content = f"""
                    <p>Kính gửi các anh/chị,</p>
                    <p>Phòng Nhân sự trân trọng thông báo:</p>
                    <p>Cơ quan BHXH đã có thông báo về việc thay đổi mẫu biểu <strong>{doc_type_name}</strong>.</p>
                    <p>Vui lòng sử dụng mẫu mới đính kèm khi nộp hồ sơ kể từ ngày <strong>{fields.Date.today().strftime('%d/%m/%Y')}</strong>.</p>
                    <p>Trân trọng thông báo.</p>
                """

    def action_schedule(self):
        """Lên lịch gửi thông báo"""
        self.ensure_one()
        
        if not self.deadline_date:
            raise UserError(_("Vui lòng thiết lập ngày hạn chót trước khi lên lịch thông báo."))
            
        # Tính toán thời gian gửi thông báo
        schedule_date = self.deadline_date - relativedelta(days=self.days_before)
        schedule_time = fields.Datetime.now().replace(
            year=schedule_date.year,
            month=schedule_date.month,
            day=schedule_date.day,
            hour=8,  # Gửi lúc 8 giờ sáng
            minute=0,
            second=0
        )
        
        # Cập nhật thời gian gửi thông báo
        self.notification_date = schedule_time
        self.state = 'scheduled'
        
        # Tạo hoạt động nhắc nhở
        self.activity_schedule(
            'mail.mail_activity_data_todo', 
            summary=_("Gửi thông báo BHXH: %s", self.name),
            user_id=self.env.user.id,
            date_deadline=schedule_date,
        )
        
        # Xử lý thông báo lặp lại
        if self.recurrence_type != 'none':
            self._schedule_next_recurrence()
        
        return True
    
    def _schedule_next_recurrence(self):
        """Lên lịch cho lần lặp lại tiếp theo"""
        if self.recurrence_type == 'none':
            return
            
        if self.recurrence_type == 'daily':
            next_date = fields.Date.today() + relativedelta(days=self.recurrence_interval)
        elif self.recurrence_type == 'weekly':
            next_date = fields.Date.today() + relativedelta(weeks=self.recurrence_interval)
        elif self.recurrence_type == 'monthly':
            next_date = fields.Date.today() + relativedelta(months=self.recurrence_interval)
        elif self.recurrence_type == 'quarterly':
            next_date = fields.Date.today() + relativedelta(months=3*self.recurrence_interval)
        elif self.recurrence_type == 'yearly':
            next_date = fields.Date.today() + relativedelta(years=self.recurrence_interval)
        else:
            return
            
        self.next_recurrence_date = next_date
    
    def action_send_now(self):
        """Gửi thông báo ngay lập tức"""
        self.ensure_one()
        
        # Xác định danh sách người nhận
        recipients = self.recipient_ids
        
        if not self.is_hr_only:
            # Nếu có chọn phòng ban cụ thể
            if self.department_ids:
                employees = self.env['hr.employee'].search([
                    ('department_id', 'in', self.department_ids.ids)
                ])
                # Lấy user liên kết với nhân viên
                user_ids = [e.user_id.id for e in employees if e.user_id]
                recipients |= self.env['res.users'].browse(user_ids)
                
            # Nếu có chọn nhân viên cụ thể
            if self.employee_ids:
                user_ids = [e.user_id.id for e in self.employee_ids if e.user_id]
                recipients |= self.env['res.users'].browse(user_ids)
                
            # Nếu không chọn gì: gửi cho tất cả nhân viên có liên kết với user
            if not self.department_ids and not self.employee_ids:
                employees = self.env['hr.employee'].search([
                    ('user_id', '!=', False),
                    ('company_id', '=', self.company_id.id)
                ])
                user_ids = [e.user_id.id for e in employees]
                recipients |= self.env['res.users'].browse(user_ids)
        
        if not recipients:
            raise UserError(_("Không tìm thấy người nhận thông báo."))
            
        # Gửi email
        if self.send_email:
            email_template = self.env.ref('hr_insurance.insurance_notification_email_template', raise_if_not_found=False)
            if email_template:
                for recipient in recipients:
                    if recipient.partner_id and recipient.partner_id.email:
                        email_template.with_context(lang=recipient.lang).send_mail(
                            self.id,
                            force_send=True,
                            email_values={'email_to': recipient.partner_id.email}
                        )
                        
        # Gửi thông báo hệ thống
        if self.send_notification:
            for recipient in recipients:
                self.env['mail.message'].create({
                    'body': self.content,
                    'subject': self.name,
                    'message_type': 'notification',
                    'res_id': self.id,
                    'model': 'insurance.notification',
                    'partner_ids': [(4, recipient.partner_id.id)],
                    'notification_ids': [(0, 0, {
                        'res_partner_id': recipient.partner_id.id,
                        'notification_type': 'inbox'
                    })]
                })
                
        # Gửi SMS (tính năng mới)
        if self.send_sms and self.sms_template_id:
            for employee in self.employee_ids or self.env['hr.employee'].search([]):
                if employee.mobile_phone:
                    try:
                        self.sms_template_id.with_context(lang=employee.user_id.lang if employee.user_id else None).send_sms(self.id)
                    except Exception as e:
                        _logger.error(f"Error sending SMS to {employee.name}: {str(e)}")
        
        # Cập nhật trạng thái
        self.write({
            'state': 'sent',
        })
        
        return True
    
    def action_cancel(self):
        """Hủy thông báo"""
        self.write({'state': 'cancelled'})
        return True
    
    def action_reset_to_draft(self):
        """Chuyển về trạng thái dự thảo"""
        self.write({'state': 'draft'})
        return True
    
    @api.model
    def _send_scheduled_notifications(self):
        """Hàm chạy định kỳ để gửi thông báo đã lên lịch"""
        now = fields.Datetime.now()
        notifications = self.search([
            ('state', '=', 'scheduled'),
            ('notification_date', '<=', now)
        ])
        
        for notification in notifications:
            try:
                notification.action_send_now()
                _logger.info(f"Sent scheduled notification: {notification.name}")
            except Exception as e:
                _logger.error(f"Error sending notification {notification.name}: {str(e)}")
        
        # Xử lý các thông báo lặp lại
        self._process_recurring_notifications()
                
        return True
    
    @api.model
    def _process_recurring_notifications(self):
        """Xử lý các thông báo lặp lại đến hạn"""
        today = fields.Date.today()
        recurring_notifications = self.search([
            ('recurrence_type', '!=', 'none'),
            ('next_recurrence_date', '<=', today),
            ('state', 'in', ['sent', 'scheduled'])
        ])
        
        for notification in recurring_notifications:
            # Tạo bản sao thông báo mới
            new_values = notification.copy_data()[0]
            new_values.update({
                'state': 'draft',
                'date': fields.Date.today(),
            })
            
            # Xử lý loại thông báo đặc biệt
            if notification.type == 'quarterly_report':
                quarter = (fields.Date.today().month - 1) // 3 + 1
                year = fields.Date.today().year
                new_values.update({
                    'name': f'Nhắc nhở: Báo cáo quý {quarter}/{year} BHXH'
                })
            
            # Tạo thông báo mới
            new_notification = self.create(new_values)
            _logger.info(f"Created recurring notification: {new_notification.name}")
            
            # Cập nhật ngày lặp lại tiếp theo
            notification._schedule_next_recurrence()
        
        return True
    
    @api.model
    def create_deadline_notification(self):
        """
        Tạo thông báo tự động về hạn chót BHXH hàng tháng
        Được gọi từ cron job
        """
        today = fields.Date.today()
        # Ngày hạn chót là ngày 10 của tháng tiếp theo
        next_month = today + relativedelta(months=1)
        deadline = date(next_month.year, next_month.month, 10)
        
        # Kiểm tra xem đã có thông báo cho tháng này chưa
        existing = self.search([
            ('type', '=', 'deadline'),
            ('deadline_date', '=', deadline),
            ('state', 'in', ['draft', 'scheduled', 'sent'])
        ], limit=1)
        
        if not existing:
            # Tạo thông báo mới
            notification = self.create({
                'name': f'Nhắc nhở: Hạn nộp hồ sơ BHXH tháng {today.month}/{today.year}',
                'type': 'deadline',
                'deadline_date': deadline,
                'days_before': 5,
                'content': f"""
                    <p>Kính gửi các anh/chị,</p>
                    <p>Phòng Nhân sự trân trọng thông báo:</p>
                    <p>Hạn nộp báo cáo và đóng BHXH cho tháng {today.month}/{today.year} là ngày <strong>{deadline.strftime('%d/%m/%Y')}</strong>.</p>
                    <p>Vui lòng chuẩn bị đầy đủ hồ sơ và thanh toán đúng hạn để tránh phát sinh phí phạt chậm nộp.</p>
                    <p>Trân trọng thông báo.</p>
                """,
                'is_hr_only': True,
                'send_email': True,
                'send_notification': True
            })
            
            # Tự động lên lịch gửi thông báo
            notification.action_schedule()
            
            _logger.info(f"Created automatic deadline notification for {today.month}/{today.year}")
        
        return True
    
    @api.model
    def notify_vn_policy_changes(self, policy_type, effective_date, changes_dict):
        """
        Tạo thông báo về thay đổi chính sách BHXH của Việt Nam
        
        :param policy_type: Loại chính sách ('bhxh', 'bhyt', 'bhtn')
        :param effective_date: Ngày có hiệu lực
        :param changes_dict: Dictionary chứa các thay đổi {'title': 'description'}
        """
        policy_names = {
            'bhxh': 'Bảo hiểm xã hội',
            'bhyt': 'Bảo hiểm y tế',
            'bhtn': 'Bảo hiểm thất nghiệp'
        }
        
        policy_name = policy_names.get(policy_type, 'Bảo hiểm')
        
        # Tạo nội dung HTML
        changes_html = ""
        for title, description in changes_dict.items():
            changes_html += f"<li><strong>{title}</strong>: {description}</li>"
            
        content = f"""
            <p>Kính gửi các anh/chị,</p>
            <p>Phòng Nhân sự trân trọng thông báo về những thay đổi mới trong chính sách {policy_name}:</p>
            <ul>
                {changes_html}
            </ul>
            <p>Những thay đổi này sẽ có hiệu lực từ ngày <strong>{effective_date.strftime('%d/%m/%Y')}</strong>.</p>
            <p>Mọi thắc mắc vui lòng liên hệ phòng Nhân sự để được giải đáp.</p>
            <p>Trân trọng thông báo.</p>
        """
        
        # Tạo thông báo mới
        notification = self.create({
            'name': f'Thông báo: Thay đổi chính sách {policy_name} từ {effective_date.strftime("%d/%m/%Y")}',
            'type': 'policy_change',
            'deadline_date': effective_date,
            'days_before': 15,  # Thông báo trước 15 ngày
            'content': content,
            'is_hr_only': False,  # Gửi cho tất cả nhân viên
            'send_email': True,
            'send_notification': True,
            'is_urgent': True
        })
        
        # Tự động lên lịch gửi thông báo
        notification.action_schedule()
        
        return notification 