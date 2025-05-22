# -*- coding: utf-8 -*-
#############################################################################
#    A part of Open HRMS Project <https://www.openhrms.com>
#
#    Cybrosys Technologies Pvt. Ltd.
#
#    Copyright (C) 2024-TODAY Cybrosys Technologies(<https://www.cybrosys.com>)
#    Author: Cybrosys Techno Solutions(<https://www.cybrosys.com>)
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
from odoo import api, fields, models, _
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz
import logging

_logger = logging.getLogger(__name__)

# Thiết lập múi giờ mặc định cho Việt Nam
VN_TIMEZONE = 'Asia/Ho_Chi_Minh'

class HrLeaveNotification(models.Model):
    """Mở rộng model hr.leave để thêm chức năng gửi thông báo tự động"""
    _inherit = 'hr.leave'

    needs_medical_note = fields.Boolean(
        string="Yêu cầu giấy khám bệnh",
        compute="_compute_needs_medical_note",
        store=True,
        help="Tự động đánh dấu nếu nghỉ ốm vượt quá ngưỡng quy định")
    
    medical_note_provided = fields.Boolean(
        string="Đã nộp giấy khám bệnh",
        default=False,
        help="Đánh dấu khi nhân viên đã nộp giấy khám bệnh")
    
    notification_sent = fields.Boolean(
        string="Đã gửi thông báo",
        default=False,
        help="Đánh dấu đã gửi thông báo cho nhân viên")
    
    approval_reminder_sent = fields.Boolean(
        string="Đã gửi nhắc phê duyệt",
        default=False,
        help="Đánh dấu đã gửi thông báo nhắc phê duyệt cho quản lý")
    
    @api.depends('holiday_status_id', 'number_of_days')
    def _compute_needs_medical_note(self):
        """Tính toán xem có cần giấy khám bệnh không dựa trên cấu hình"""
        sick_leave_medical_threshold = int(self.env['ir.config_parameter'].sudo().get_param(
            'hr_leave_request_aliasing.sick_leave_medical_threshold', default=2))
        
        for leave in self:
            # Kiểm tra xem có phải nghỉ ốm không (dựa vào loại nghỉ phép)
            is_sick_leave = leave.holiday_status_id and leave.holiday_status_id.name and (
                'ốm' in leave.holiday_status_id.name.lower() or 
                'bệnh' in leave.holiday_status_id.name.lower() or
                'sick' in leave.holiday_status_id.name.lower()
            )
            
            # Đánh dấu cần giấy khám bệnh nếu là nghỉ ốm và số ngày vượt ngưỡng
            leave.needs_medical_note = is_sick_leave and leave.number_of_days >= sick_leave_medical_threshold
    
    def _send_leave_reminders(self):
        """Gửi thông báo nhắc nhở về đơn nghỉ phép"""
        try:
            # Lấy cấu hình từ tham số hệ thống
            reminder_days_before = int(self.env['ir.config_parameter'].sudo().get_param(
                'hr_leave_request_aliasing.reminder_days_before', default=1))
            reminder_remaining_days = int(self.env['ir.config_parameter'].sudo().get_param(
                'hr_leave_request_aliasing.reminder_remaining_days', default=3))
            
            today = fields.Date.today()
            tomorrow = today + timedelta(days=1)
            upcoming_date = today + timedelta(days=reminder_days_before)
            
            # 1. Nhắc nhở về đơn nghỉ phép sắp đến
            upcoming_leaves = self.search([
                ('state', '=', 'validate'),
                ('date_from', '>=', fields.Datetime.to_string(tomorrow)),
                ('date_from', '<=', fields.Datetime.to_string(upcoming_date)),
                ('notification_sent', '=', False)
            ])
            
            for leave in upcoming_leaves:
                # Gửi thông báo đến nhân viên
                self._notify_upcoming_leave(leave)
                # Đánh dấu đã gửi thông báo
                leave.notification_sent = True
            
            # 2. Nhắc nhở về số ngày phép còn lại
            holiday_status_ids = self.env['hr.leave.type'].search([
                ('requires_allocation', '=', 'yes')
            ])
            
            for holiday_status in holiday_status_ids:
                allocations = self.env['hr.leave.allocation'].search([
                    ('holiday_status_id', '=', holiday_status.id),
                    ('state', '=', 'validate')
                ])
                
                for allocation in allocations:
                    # Tính số ngày phép còn lại
                    leaves = self.search([
                        ('employee_id', '=', allocation.employee_id.id),
                        ('holiday_status_id', '=', holiday_status.id),
                        ('state', '=', 'validate')
                    ])
                    
                    total_leaves = sum(leaves.mapped('number_of_days'))
                    remaining_leaves = allocation.number_of_days - total_leaves
                    
                    # Nếu số ngày phép còn lại thấp hơn hoặc bằng ngưỡng cảnh báo
                    if 0 < remaining_leaves <= reminder_remaining_days:
                        # Gửi thông báo cảnh báo về số ngày phép còn lại
                        self._notify_remaining_leaves(
                            allocation.employee_id, 
                            holiday_status,
                            remaining_leaves
                        )
            
            # 3. Nhắc nhở nộp giấy khám bệnh nếu cần
            sick_leaves_needing_note = self.search([
                ('needs_medical_note', '=', True),
                ('medical_note_provided', '=', False),
                ('state', '=', 'validate')
            ])
            
            for leave in sick_leaves_needing_note:
                # Gửi thông báo yêu cầu nộp giấy khám bệnh
                self._notify_medical_note_required(leave)

            return True
        
        except Exception as e:
            _logger.error("Lỗi khi gửi thông báo nhắc nhở: %s", e)
            return False
    
    def _send_approval_reminders(self):
        """Gửi thông báo nhắc nhở quản lý phê duyệt đơn nghỉ phép"""
        try:
            # Lấy cấu hình từ tham số hệ thống
            approval_reminder_days = int(self.env['ir.config_parameter'].sudo().get_param(
                'hr_leave_request_aliasing.approval_reminder_days', default=2))
            
            today = fields.Date.today()
            threshold_date = today - timedelta(days=approval_reminder_days)
            
            # Tìm các đơn nghỉ phép đang chờ phê duyệt quá thời gian quy định
            pending_leaves = self.search([
                ('state', '=', 'confirm'),
                ('create_date', '<=', fields.Datetime.to_string(threshold_date)),
                ('approval_reminder_sent', '=', False)
            ])
            
            for leave in pending_leaves:
                # Gửi thông báo đến người quản lý
                self._notify_pending_approval(leave)
                # Đánh dấu đã gửi thông báo
                leave.approval_reminder_sent = True
            
            return True
            
        except Exception as e:
            _logger.error("Lỗi khi gửi thông báo nhắc phê duyệt: %s", e)
            return False
    
    def _notify_upcoming_leave(self, leave):
        """Gửi thông báo cho nhân viên về đơn nghỉ phép sắp đến"""
        if not leave.employee_id or not leave.employee_id.user_id:
            return False
        
        employee = leave.employee_id
        leave_date = self._get_vn_formatted_date(leave.date_from)
        
        # Tạo tin nhắn thông báo
        message = _("""
            <p>Xin chào %s,</p>
            <p>Xác nhận bạn sẽ bắt đầu kỳ nghỉ phép vào ngày <strong>%s</strong>.</p>
            <p>Loại nghỉ phép: <strong>%s</strong></p>
            <p>Số ngày: <strong>%s</strong></p>
            <ul>
                <li>Vui lòng sắp xếp công việc hiện tại trước khi nghỉ</li>
                <li>Đảm bảo bàn giao công việc cho người thay thế (nếu có)</li>
                <li>Cập nhật trạng thái vắng mặt trong các ứng dụng liên lạc nội bộ</li>
            </ul>
            <p>Chúc bạn có kỳ nghỉ tốt!</p>
        """) % (
            employee.name,
            leave_date,
            leave.holiday_status_id.name,
            leave.number_of_days
        )
        
        # Gửi thông báo qua Odoo (tuân thủ API mới của Odoo 18)
        self.env['bus.bus']._sendone(
            employee.user_id.partner_id, 
            'mail.simple_notification', 
            {
                'title': _("Nhắc nhở: Kỳ nghỉ phép sắp đến"),
                'message': message,
                'sticky': True,
                'warning': False,
            }
        )
        
        # Gửi email thông báo
        mail_template = self.env.ref('hr_holidays.mail_act_leave_approval', raise_if_not_found=False)
        if mail_template:
            email_values = {
                'subject': _("Nhắc nhở: Kỳ nghỉ phép sắp đến"),
                'email_to': employee.work_email,
                'body_html': message,
            }
            mail_template.send_mail(leave.id, email_values=email_values, force_send=True)
        
        return True
    
    def _notify_remaining_leaves(self, employee, leave_type, remaining_days):
        """Gửi thông báo cho nhân viên về số ngày phép còn lại"""
        if not employee or not employee.user_id:
            return False
        
        # Tạo tin nhắn thông báo
        message = _("""
            <p>Xin chào %s,</p>
            <p>Thông báo số ngày nghỉ phép còn lại:</p>
            <p>Loại nghỉ phép: <strong>%s</strong></p>
            <p>Số ngày còn lại: <strong>%s</strong> ngày</p>
            <p>Lưu ý sắp xếp thời gian nghỉ phép hợp lý. Nếu có thắc mắc, vui lòng liên hệ phòng nhân sự.</p>
        """) % (
            employee.name,
            leave_type.name,
            remaining_days
        )
        
        # Gửi thông báo qua Odoo (tuân thủ API mới của Odoo 18)
        self.env['bus.bus']._sendone(
            employee.user_id.partner_id, 
            'mail.simple_notification', 
            {
                'title': _("Thông báo số ngày phép còn lại"),
                'message': message,
                'sticky': False,
                'warning': False,
            }
        )
        
        # Gửi email thông báo
        template = self.env.ref('hr_holidays.mail_act_leave_allocation_approval', raise_if_not_found=False)
        if template:
            ctx = dict(self.env.context or {})
            ctx.update({
                'email_to': employee.work_email,
                'subject': _("Thông báo số ngày phép còn lại"),
                'body_html': message,
            })
            template.with_context(ctx).send_mail(employee.id, force_send=True)
        
        return True
    
    def _notify_medical_note_required(self, leave):
        """Gửi thông báo yêu cầu nộp giấy khám bệnh"""
        if not leave.employee_id or not leave.employee_id.user_id:
            return False
        
        employee = leave.employee_id
        leave_date = self._get_vn_formatted_date(leave.date_from)
        
        # Tạo tin nhắn thông báo
        message = _("""
            <p>Xin chào %s,</p>
            <p>Theo quy định của công ty và pháp luật lao động Việt Nam, đối với đơn nghỉ ốm kéo dài 
            từ <strong>%s</strong> ngày trở lên, người lao động cần nộp giấy khám bệnh/giấy xác nhận của cơ sở y tế.</p>
            <p>Thông tin đơn nghỉ phép của bạn:</p>
            <ul>
                <li>Ngày bắt đầu: <strong>%s</strong></li>
                <li>Số ngày nghỉ: <strong>%s</strong> ngày</li>
            </ul>
            <p>Vui lòng nộp giấy khám bệnh cho phòng nhân sự trong thời gian sớm nhất để hoàn tất thủ tục, đảm bảo quyền lợi và chế độ BHXH.</p>
            <p>Lưu ý: Nếu không nộp giấy khám bệnh, thời gian nghỉ có thể được tính vào nghỉ không lương hoặc nghỉ phép năm.</p>
        """) % (
            employee.name,
            self.env['ir.config_parameter'].sudo().get_param('hr_leave_request_aliasing.sick_leave_medical_threshold', default=2),
            leave_date,
            leave.number_of_days
        )
        
        # Gửi thông báo qua Odoo (sử dụng API bus.bus của Odoo 18)
        self.env['bus.bus']._sendone(
            employee.user_id.partner_id, 
            'mail.simple_notification', 
            {
                'title': _("Yêu cầu nộp giấy khám bệnh"),
                'message': message,
                'sticky': True,
                'warning': True,
            }
        )
        
        # Gửi email thông báo
        mail_template = self.env.ref('hr_holidays.mail_act_leave_approval', raise_if_not_found=False)
        if mail_template:
            email_values = {
                'subject': _("Yêu cầu nộp giấy khám bệnh"),
                'email_to': employee.work_email,
                'body_html': message,
            }
            mail_template.send_mail(leave.id, email_values=email_values, force_send=True)
        
        # Gửi thông báo cho quản lý HR
        hr_managers = self.env.ref('hr_holidays.group_hr_holidays_manager').users
        if hr_managers:
            hr_message = _("""
                <p>Thông báo:</p>
                <p>Nhân viên <strong>%s</strong> có đơn nghỉ ốm kéo dài <strong>%s</strong> ngày, cần nộp giấy khám bệnh.</p>
                <p>Vui lòng theo dõi và nhắc nhở nhân viên nộp giấy tờ theo quy định.</p>
            """) % (
                employee.name,
                leave.number_of_days
            )
            
            for hr_manager in hr_managers:
                if hr_manager.partner_id:
                    self.env['bus.bus']._sendone(
                        hr_manager.partner_id, 
                        'mail.simple_notification', 
                        {
                            'title': _("Theo dõi giấy khám bệnh"),
                            'message': hr_message,
                            'sticky': False,
                            'warning': False,
                        }
                    )
        
        return True
    
    def _notify_pending_approval(self, leave):
        """Gửi thông báo nhắc nhở quản lý phê duyệt đơn nghỉ phép"""
        # Kiểm tra xem đơn nghỉ phép có manager được gán không
        if not leave.employee_id or not leave.employee_id.parent_id or not leave.employee_id.parent_id.user_id:
            # Gửi thông báo cho tất cả HR Manager
            hr_managers = self.env.ref('hr_holidays.group_hr_holidays_manager').users
            if not hr_managers:
                return False
                
            recipients = hr_managers
        else:
            # Gửi thông báo cho quản lý trực tiếp
            recipients = [leave.employee_id.parent_id.user_id]
            
            # Thêm HR Manager vào CC nếu đơn đã chờ quá lâu
            days_waiting = (fields.Date.today() - fields.Date.from_string(leave.create_date)).days
            if days_waiting >= 4:  # Nếu đã chờ hơn 4 ngày, CC đến HR Manager
                hr_managers = self.env.ref('hr_holidays.group_hr_holidays_manager').users
                for hr_manager in hr_managers:
                    if hr_manager not in recipients:
                        recipients.append(hr_manager)
        
        # Tạo tin nhắn thông báo
        employee_name = leave.employee_id.name
        leave_date = self._get_vn_formatted_date(leave.date_from)
        days_waiting = (fields.Date.today() - fields.Date.from_string(leave.create_date)).days
        
        message = _("""
            <p>Xin chào,</p>
            <p>Đơn nghỉ phép của nhân viên <strong>%s</strong> đang chờ phê duyệt.</p>
            <p>Thông tin chi tiết:</p>
            <ul>
                <li>Loại nghỉ phép: <strong>%s</strong></li>
                <li>Ngày bắt đầu: <strong>%s</strong></li>
                <li>Số ngày nghỉ: <strong>%s</strong></li>
                <li>Thời gian chờ: <strong>%s</strong> ngày</li>
            </ul>
            <p>Vui lòng xem xét và phê duyệt/từ chối đơn này để nhân viên có thể sắp xếp kế hoạch làm việc.</p>
        """) % (
            employee_name,
            leave.holiday_status_id.name,
            leave_date,
            leave.number_of_days,
            days_waiting
        )
        
        # Gửi thông báo cho từng người nhận
        for recipient in recipients:
            if recipient.partner_id:
                # Sử dụng API bus.bus của Odoo 18
                self.env['bus.bus']._sendone(
                    recipient.partner_id, 
                    'mail.simple_notification', 
                    {
                        'title': _("Nhắc nhở: Đơn nghỉ phép đang chờ phê duyệt"),
                        'message': message,
                        'sticky': True,
                        'warning': days_waiting >= 3,  # Đánh dấu Warning nếu chờ quá lâu
                    }
                )
                
                # Gửi email
                self.env['mail.mail'].sudo().create({
                    'subject': _("Nhắc nhở: Đơn nghỉ phép đang chờ phê duyệt"),
                    'body_html': message,
                    'recipient_ids': [(4, recipient.partner_id.id)],
                    'email_from': self.env.company.email or self.env.user.email_formatted,
                }).send()
        
        return True
        
    def check_medical_certificate_requirement(self):
        """Kiểm tra và cập nhật yêu cầu giấy khám bệnh cho các đơn nghỉ ốm mới"""
        try:
            sick_leave_medical_threshold = int(self.env['ir.config_parameter'].sudo().get_param(
                'hr_leave_request_aliasing.sick_leave_medical_threshold', default=2))
            
            # Tìm các đơn nghỉ ốm mới được tạo trong 24 giờ qua
            yesterday = fields.Datetime.now() - timedelta(days=1)
            
            # Tìm các loại nghỉ ốm
            sick_leave_types = self.env['hr.leave.type'].search([
                '|', '|', '|',
                ('name', 'ilike', 'ốm'),
                ('name', 'ilike', 'bệnh'),
                ('name', 'ilike', 'sick'),
                ('code', 'ilike', 'SICK')
            ])
            
            if not sick_leave_types:
                return True
                
            sick_leave_ids = sick_leave_types.ids
            
            # Tìm các đơn mới có loại là nghỉ ốm và số ngày >= ngưỡng
            new_sick_leaves = self.search([
                ('holiday_status_id', 'in', sick_leave_ids),
                ('create_date', '>=', yesterday),
                ('number_of_days', '>=', sick_leave_medical_threshold),
                ('needs_medical_note', '=', False)  # Chưa được đánh dấu
            ])
            
            # Cập nhật trạng thái needs_medical_note
            for leave in new_sick_leaves:
                leave.needs_medical_note = True
                
                # Gửi thông báo cho nhân viên và HR
                self._notify_medical_note_required(leave)
            
            return True
            
        except Exception as e:
            _logger.error("Lỗi khi kiểm tra yêu cầu giấy khám bệnh: %s", e)
            return False
    
    def _send_month_end_balance_notification(self):
        """Gửi thông báo số ngày phép còn lại vào cuối tháng"""
        try:
            # Lấy tất cả nhân viên đang làm việc
            employees = self.env['hr.employee'].search([
                ('active', '=', True),
                ('user_id', '!=', False)  # Chỉ gửi cho những người có tài khoản trong hệ thống
            ])
            
            # Lấy tất cả loại nghỉ phép yêu cầu phân bổ và có giới hạn
            leave_types = self.env['hr.leave.type'].search([
                ('requires_allocation', '=', 'yes')
            ])
            
            current_date = fields.Date.today()
            current_month = current_date.strftime('%m/%Y')
            
            # Xử lý từng nhân viên
            for employee in employees:
                user = employee.user_id
                if not user or not user.partner_id:
                    continue
                    
                # Tạo bảng thông tin số ngày phép còn lại
                leave_balance_info = []
                
                for leave_type in leave_types:
                    # Tìm tổng số ngày phép được phân bổ
                    allocations = self.env['hr.leave.allocation'].search([
                        ('employee_id', '=', employee.id),
                        ('holiday_status_id', '=', leave_type.id),
                        ('state', '=', 'validate')
                    ])
                    
                    total_allocated = sum(allocations.mapped('number_of_days'))
                    
                    # Tìm tổng số ngày phép đã sử dụng
                    leaves = self.search([
                        ('employee_id', '=', employee.id),
                        ('holiday_status_id', '=', leave_type.id),
                        ('state', '=', 'validate')
                    ])
                    
                    total_used = sum(leaves.mapped('number_of_days'))
                    
                    # Tính số ngày phép còn lại
                    remaining = total_allocated - total_used
                    
                    if total_allocated > 0:  # Chỉ thêm các loại nghỉ phép có phân bổ
                        leave_balance_info.append({
                            'name': leave_type.name,
                            'allocated': total_allocated,
                            'used': total_used,
                            'remaining': remaining
                        })
                
                # Nếu có thông tin để hiển thị
                if leave_balance_info:
                    # Tạo bảng HTML
                    table_rows = ""
                    for info in leave_balance_info:
                        table_rows += """
                            <tr>
                                <td style="padding: 8px; border: 1px solid #ddd;">%s</td>
                                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">%s</td>
                                <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">%s</td>
                                <td style="padding: 8px; border: 1px solid #ddd; text-align: center; 
                                    %s">%s</td>
                            </tr>
                        """ % (
                            info['name'],
                            info['allocated'],
                            info['used'],
                            "color: red;" if info['remaining'] <= 0 else (
                                "color: orange;" if info['remaining'] < 3 else ""
                            ),
                            info['remaining']
                        )
                    
                    # Tạo thông báo
                    message = _("""
                        <p>Xin chào %s,</p>
                        <p>Dưới đây là thông tin số ngày phép còn lại của bạn tính đến cuối tháng %s:</p>
                        
                        <table style="border-collapse: collapse; width: 100%%;">
                            <tr style="background-color: #f2f2f2;">
                                <th style="padding: 8px; border: 1px solid #ddd;">Loại nghỉ phép</th>
                                <th style="padding: 8px; border: 1px solid #ddd;">Tổng ngày được cấp</th>
                                <th style="padding: 8px; border: 1px solid #ddd;">Đã sử dụng</th>
                                <th style="padding: 8px; border: 1px solid #ddd;">Còn lại</th>
                            </tr>
                            %s
                        </table>
                        
                        <p style="margin-top: 15px;">Lưu ý:</p>
                        <ul>
                            <li>Số ngày phép hiển thị trên đã được cập nhật đến thời điểm hiện tại</li>
                            <li>Một số loại phép có thể có quy định riêng về thời hạn sử dụng</li>
                            <li>Vui lòng liên hệ phòng nhân sự nếu bạn có bất kỳ thắc mắc nào</li>
                        </ul>
                    """) % (
                        employee.name,
                        current_month,
                        table_rows
                    )
                    
                    # Gửi thông báo qua Odoo (sử dụng API bus.bus của Odoo 18)
                    self.env['bus.bus']._sendone(
                        user.partner_id, 
                        'mail.simple_notification', 
                        {
                            'title': _("Thông báo số ngày phép còn lại - Tháng %s") % current_month,
                            'message': message,
                            'sticky': False,
                            'warning': False,
                        }
                    )
                    
                    # Gửi email thông báo
                    if employee.work_email:
                        self.env['mail.mail'].sudo().create({
                            'subject': _("Thông báo số ngày phép còn lại - Tháng %s") % current_month,
                            'body_html': message,
                            'email_to': employee.work_email,
                            'email_from': self.env.company.email or self.env.user.email_formatted,
                        }).send()
            
            return True
            
        except Exception as e:
            _logger.error("Lỗi khi gửi thông báo số ngày phép cuối tháng: %s", e)
            return False
    
    def _get_vn_formatted_date(self, dt_obj):
        """Chuyển đổi sang định dạng ngày giờ Việt Nam"""
        if not dt_obj:
            return ''
            
        local_tz = pytz.timezone(VN_TIMEZONE)
        
        if dt_obj.tzinfo:
            local_dt = dt_obj.astimezone(local_tz)
        else:
            local_dt = pytz.utc.localize(dt_obj).astimezone(local_tz)
            
        return local_dt.strftime('%d/%m/%Y')
    
    def _get_vn_formatted_datetime(self, dt_obj, include_seconds=False):
        """Chuyển đổi sang định dạng ngày giờ Việt Nam với thời gian"""
        if not dt_obj:
            return ''
            
        local_tz = pytz.timezone(VN_TIMEZONE)
        
        if dt_obj.tzinfo:
            local_dt = dt_obj.astimezone(local_tz)
        else:
            local_dt = pytz.utc.localize(dt_obj).astimezone(local_tz)
            
        if include_seconds:
            return local_dt.strftime('%d/%m/%Y %H:%M:%S')
        else:
            return local_dt.strftime('%d/%m/%Y %H:%M')
        
    def _get_now_vn(self):
        """Trả về thời gian hiện tại theo múi giờ Việt Nam"""
        local_tz = pytz.timezone(VN_TIMEZONE)
        return datetime.now(local_tz) 