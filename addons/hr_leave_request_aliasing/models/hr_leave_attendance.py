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
from pytz import timezone
import logging

_logger = logging.getLogger(__name__)


class HrLeaveAttendance(models.Model):
    """Mở rộng model hr.leave để tích hợp với hr_attendance"""
    _inherit = 'hr.leave'

    update_attendance = fields.Boolean(
        string="Cập nhật chấm công",
        default=True,
        help="Tự động cập nhật trạng thái chấm công của nhân viên khi nghỉ phép")
    attendance_status_updated = fields.Boolean(
        string="Đã cập nhật chấm công",
        default=False,
        help="Đánh dấu đã cập nhật chấm công cho đơn nghỉ phép này")

    @api.model
    def _create_resource_leave(self):
        """Ghi đè phương thức để cập nhật chấm công khi tạo kỳ nghỉ"""
        res = super(HrLeaveAttendance, self)._create_resource_leave()
        self._update_attendance_status()
        return res

    def _remove_resource_leave(self):
        """Ghi đè phương thức để cập nhật chấm công khi xóa kỳ nghỉ"""
        res = super(HrLeaveAttendance, self)._remove_resource_leave()
        self._reset_attendance_status()
        return res

    def _update_attendance_status(self):
        """Cập nhật trạng thái chấm công khi nghỉ phép được phê duyệt"""
        for leave in self.filtered(lambda l: l.state == 'validate' and l.update_attendance and not l.attendance_status_updated):
            # Kiểm tra xem module hr_attendance đã được cài đặt
            if not self.env.get('hr.attendance'):
                continue

            try:
                # Tạo mục nhập chấm công "Leave" cho khoảng thời gian nghỉ phép
                start_date = fields.Datetime.from_string(leave.date_from)
                end_date = fields.Datetime.from_string(leave.date_to)
                
                # Chỉ xử lý ngày làm việc (loại trừ các ngày cuối tuần, ngày lễ)
                current_date = start_date
                while current_date <= end_date:
                    # Kiểm tra nếu là ngày làm việc
                    if self._is_work_day(leave.employee_id, current_date):
                        # Tạo check-in ảo đầu ngày
                        check_in_time = self._get_work_time_start(leave.employee_id, current_date)
                        if check_in_time:
                            # Tạo check-out ảo cuối ngày
                            check_out_time = self._get_work_time_end(leave.employee_id, current_date)
                            if check_out_time:
                                self.env['hr.attendance'].create({
                                    'employee_id': leave.employee_id.id,
                                    'check_in': check_in_time,
                                    'check_out': check_out_time,
                                    'leave_id': leave.id,
                                    'is_leave': True,
                                })
                    
                    # Chuyển sang ngày tiếp theo
                    current_date = current_date + timedelta(days=1)
                
                # Đánh dấu đã cập nhật
                leave.attendance_status_updated = True
                
            except Exception as e:
                _logger.error("Lỗi khi cập nhật chấm công cho nghỉ phép: %s", e)

    def _reset_attendance_status(self):
        """Xóa các mục chấm công đã tạo cho đơn nghỉ phép khi hủy phê duyệt"""
        for leave in self.filtered(lambda l: l.attendance_status_updated):
            try:
                # Xóa các bản ghi chấm công liên quan đến đơn nghỉ phép này
                if self.env.get('hr.attendance'):
                    attendances = self.env['hr.attendance'].search([('leave_id', '=', leave.id), ('is_leave', '=', True)])
                    if attendances:
                        attendances.unlink()
                
                # Đánh dấu chưa cập nhật
                leave.attendance_status_updated = False
                
            except Exception as e:
                _logger.error("Lỗi khi xóa chấm công cho nghỉ phép: %s", e)

    def _is_work_day(self, employee, date):
        """Kiểm tra xem ngày có phải là ngày làm việc không"""
        # Kiểm tra theo lịch làm việc của nhân viên nếu có
        if employee.resource_calendar_id:
            # Chuyển đổi múi giờ
            user_tz = timezone(employee.resource_calendar_id.tz or self.env.user.tz or 'UTC')
            date_in_tz = date.astimezone(user_tz).replace(hour=0, minute=0, second=0)
            return employee.resource_calendar_id.is_work_day(date_in_tz)
        
        # Mặc định nếu không có lịch làm việc: thứ 2-6 là ngày làm việc
        return date.weekday() < 5

    def _get_work_time_start(self, employee, date):
        """Lấy thời gian bắt đầu làm việc trong ngày"""
        try:
            if employee.resource_calendar_id:
                # Ngày làm việc
                user_tz = timezone(employee.resource_calendar_id.tz or self.env.user.tz or 'UTC')
                date_in_tz = date.astimezone(user_tz).replace(hour=0, minute=0, second=0)
                
                # Lấy giờ làm việc từ lịch làm việc
                work_intervals = employee.resource_calendar_id._work_intervals(
                    date_in_tz, date_in_tz.replace(hour=23, minute=59, second=59),
                    employee.resource_id)
                
                for interval in work_intervals:
                    return interval[0]
                
            # Mặc định 8:00 sáng nếu không có lịch làm việc
            return date.replace(hour=8, minute=0, second=0)
        except Exception as e:
            _logger.error("Lỗi khi lấy thời gian bắt đầu làm việc: %s", e)
            return date.replace(hour=8, minute=0, second=0)

    def _get_work_time_end(self, employee, date):
        """Lấy thời gian kết thúc làm việc trong ngày"""
        try:
            if employee.resource_calendar_id:
                # Ngày làm việc
                user_tz = timezone(employee.resource_calendar_id.tz or self.env.user.tz or 'UTC')
                date_in_tz = date.astimezone(user_tz).replace(hour=0, minute=0, second=0)
                
                # Lấy giờ làm việc từ lịch làm việc
                work_intervals = employee.resource_calendar_id._work_intervals(
                    date_in_tz, date_in_tz.replace(hour=23, minute=59, second=59),
                    employee.resource_id)
                
                # Lấy thời gian kết thúc của khoảng thời gian làm việc cuối cùng
                last_interval_end = date.replace(hour=17, minute=0, second=0)  # Mặc định 17:00
                
                for interval in work_intervals:
                    last_interval_end = interval[1]  # Cập nhật thời gian kết thúc
                
                return last_interval_end
                
            # Mặc định 17:00 chiều nếu không có lịch làm việc
            return date.replace(hour=17, minute=0, second=0)
        except Exception as e:
            _logger.error("Lỗi khi lấy thời gian kết thúc làm việc: %s", e)
            return date.replace(hour=17, minute=0, second=0)

    def write(self, vals):
        """Ghi đè phương thức write để xử lý thay đổi trạng thái"""
        res = super(HrLeaveAttendance, self).write(vals)
        
        # Nếu trạng thái thay đổi thành 'validate' (được phê duyệt)
        if vals.get('state') == 'validate':
            self._update_attendance_status()
        
        # Nếu trạng thái thay đổi từ 'validate' sang trạng thái khác (bị hủy)
        if 'state' in vals and vals.get('state') != 'validate':
            for leave in self.filtered(lambda l: l.attendance_status_updated):
                leave._reset_attendance_status()
        
        return res


class HrAttendance(models.Model):
    """Mở rộng model hr.attendance để thêm trường liên kết đến leave"""
    _inherit = 'hr.attendance'

    leave_id = fields.Many2one('hr.leave', string='Đơn nghỉ phép', help='Đơn nghỉ phép liên quan')
    is_leave = fields.Boolean(string='Là nghỉ phép', default=False, 
                            help='Đánh dấu chấm công được tạo tự động từ đơn nghỉ phép') 