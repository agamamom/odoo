# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields


class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    # Add Vietnamese labor law fields
    social_insurance_number = fields.Char(string='Mã BHXH', help='Mã số Bảo hiểm Xã hội')
    health_insurance_number = fields.Char(string='Mã BHYT', help='Mã số Bảo hiểm Y tế')
    annual_leave_days = fields.Float(string='Ngày nghỉ phép năm', default=12.0, help='Số ngày nghỉ phép năm theo luật Việt Nam')
    sick_leave_days = fields.Float(string='Ngày nghỉ ốm', default=30.0, help='Số ngày nghỉ ốm theo luật Việt Nam')
    maternity_leave_days = fields.Float(string='Ngày nghỉ thai sản', default=180.0, help='Số ngày nghỉ thai sản theo luật Việt Nam')

    @api.depends("user_id.im_status", "attendance_state")
    def _compute_presence_state(self):
        """
        Override to include checkin/checkout in the presence state
        Attendance has the second highest priority after login
        """
        super()._compute_presence_state()
        employees = self.filtered(lambda e: e.hr_presence_state != "present")
        employee_to_check_working = self.filtered(lambda e: e.attendance_state == "checked_out"
                                                            and e.hr_presence_state == "out_of_working_hour")
        working_now_list = employee_to_check_working._get_employee_working_now()
        for employee in employees:
            if employee.attendance_state == "checked_out" and employee.hr_presence_state == "out_of_working_hour" and \
                    employee.id in working_now_list:
                employee.hr_presence_state = "absent"
            elif employee.attendance_state == "checked_in":
                employee.hr_presence_state = "present"

    def _compute_presence_icon(self):
        res = super()._compute_presence_icon()
        # All employee must chek in or check out. Everybody must have an icon
        for employee in self:
            employee.show_hr_icon_display = employee.company_id.hr_presence_control_attendance or bool(employee.user_id)
        return res
