# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import pytz
from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, exceptions, _
from odoo.tools import float_round


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    attendance_manager_id = fields.Many2one(
        'res.users', store=True, readonly=False,
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
        groups="hr_attendance.group_hr_attendance_manager",
        help="The user set in Attendance will access the attendance of the employee through the dedicated app and will be able to edit them.")
    attendance_ids = fields.One2many(
        'hr.attendance', 'employee_id', groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user")
    last_attendance_id = fields.Many2one(
        'hr.attendance', compute='_compute_last_attendance_id', store=True,
        groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user")
    last_check_in = fields.Datetime(
        related='last_attendance_id.check_in', store=True,
        groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user", tracking=False)
    last_check_out = fields.Datetime(
        related='last_attendance_id.check_out', store=True,
        groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user", tracking=False)
    attendance_state = fields.Selection(
        string="Attendance Status", compute='_compute_attendance_state',
        selection=[('checked_out', "Checked out"), ('checked_in', "Checked in")],
        groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user")
    hours_last_month = fields.Float(
        compute='_compute_hours_last_month', groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user")
    hours_today = fields.Float(
        compute='_compute_hours_today',
        groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user")
    hours_previously_today = fields.Float(
        compute='_compute_hours_today',
        groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user")
    last_attendance_worked_hours = fields.Float(
        compute='_compute_hours_today',
        groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user")
    hours_last_month_display = fields.Char(
        compute='_compute_hours_last_month', groups="hr.group_hr_user")
    overtime_ids = fields.One2many(
        'hr.attendance.overtime', 'employee_id', groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user")
    total_overtime = fields.Float(
        compute='_compute_total_overtime', compute_sudo=True, groups="hr_attendance.group_hr_attendance_officer,hr.group_hr_user")

    # Add Vietnamese social insurance fields
    social_insurance_number = fields.Char(string='Mã BHXH', help='Mã số Bảo hiểm Xã hội')
    health_insurance_number = fields.Char(string='Mã BHYT', help='Mã số Bảo hiểm Y tế')

    # Add leave types according to Vietnamese law
    annual_leave_days = fields.Float(string='Ngày nghỉ phép năm', default=12.0)
    sick_leave_days = fields.Float(string='Ngày nghỉ ốm', default=30.0)
    maternity_leave_days = fields.Float(string='Ngày nghỉ thai sản', default=180.0)

    # Add shift configuration for Vietnamese working schedules
    shift_type = fields.Selection(string='Loại ca', selection=[('day', 'Ca ngày'), ('night', 'Ca đêm'), ('rotating', 'Ca xoay vòng')], default='day', help='Loại ca làm việc của nhân viên.')
    shift_start_time = fields.Float(string='Giờ bắt đầu ca', default=8.0, help='Giờ bắt đầu ca làm việc (theo định dạng 24h).')
    shift_end_time = fields.Float(string='Giờ kết thúc ca', default=17.0, help='Giờ kết thúc ca làm việc (theo định dạng 24h).')

    @api.model_create_multi
    def create(self, vals_list):
        officer_group = self.env.ref('hr_attendance.group_hr_attendance_officer', raise_if_not_found=False)
        group_updates = []
        for vals in vals_list:
            if officer_group and vals.get('attendance_manager_id'):
                group_updates.append((4, vals['attendance_manager_id']))
        if group_updates:
            officer_group.sudo().write({'users': group_updates})
        return super().create(vals_list)

    def write(self, values):
        old_officers = self.env['res.users']
        if 'attendance_manager_id' in values:
            old_officers = self.attendance_manager_id
            # Officer was added
            if values['attendance_manager_id']:
                officer = self.env['res.users'].browse(values['attendance_manager_id'])
                officers_group = self.env.ref('hr_attendance.group_hr_attendance_officer', raise_if_not_found=False)
                if officers_group and not officer.has_group('hr_attendance.group_hr_attendance_officer'):
                    officer.sudo().write({'groups_id': [(4, officers_group.id)]})

        res = super(HrEmployee, self).write(values)
        old_officers.sudo()._clean_attendance_officers()

        return res

    @api.depends('overtime_ids.duration', 'attendance_ids', 'attendance_ids.overtime_status')
    def _compute_total_overtime(self):
        mapped_validated_overtimes = dict(self.env['hr.attendance']._read_group(
            domain=[('overtime_status', '=', 'approved')],
            groupby=['employee_id'],
            aggregates=['validated_overtime_hours:sum']
        ))

        mapped_overtime_adjustments = dict(self.env['hr.attendance.overtime']._read_group(
            domain=[('adjustment', '=', True)],
            groupby=['employee_id'],
            aggregates=['duration:sum']
        ))

        for employee in self:
            employee.total_overtime = mapped_validated_overtimes.get(employee, 0) + mapped_overtime_adjustments.get(employee, 0)

    def _compute_hours_last_month(self):
        """
        Compute hours in the current month, if we are the 15th of october, will compute hours from 1 oct to 15 oct
        """
        now = fields.Datetime.now()
        now_utc = pytz.utc.localize(now)
        for employee in self:
            tz = pytz.timezone(employee.tz or 'UTC')
            now_tz = now_utc.astimezone(tz)
            start_tz = now_tz.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            start_naive = start_tz.astimezone(pytz.utc).replace(tzinfo=None)
            end_tz = now_tz
            end_naive = end_tz.astimezone(pytz.utc).replace(tzinfo=None)

            hours = sum(
                att.worked_hours or 0
                for att in employee.attendance_ids.filtered(
                    lambda att: att.check_in >= start_naive and att.check_out and att.check_out <= end_naive
                )
            )

            employee.hours_last_month = round(hours, 2)
            employee.hours_last_month_display = "%g" % employee.hours_last_month

    def _compute_hours_today(self):
        now = fields.Datetime.now()
        now_utc = pytz.utc.localize(now)
        for employee in self:
            # start of day in the employee's timezone might be the previous day in utc
            tz = pytz.timezone(employee.tz)
            now_tz = now_utc.astimezone(tz)
            start_tz = now_tz + relativedelta(hour=0, minute=0)  # day start in the employee's timezone
            start_naive = start_tz.astimezone(pytz.utc).replace(tzinfo=None)

            attendances = self.env['hr.attendance'].search([
                ('employee_id', 'in', employee.ids),
                ('check_in', '<=', now),
                '|', ('check_out', '>=', start_naive), ('check_out', '=', False),
            ], order='check_in asc')
            hours_previously_today = 0
            worked_hours = 0
            attendance_worked_hours = 0
            for attendance in attendances:
                delta = (attendance.check_out or now) - max(attendance.check_in, start_naive)
                attendance_worked_hours = delta.total_seconds() / 3600.0
                worked_hours += attendance_worked_hours
                hours_previously_today += attendance_worked_hours
            employee.last_attendance_worked_hours = attendance_worked_hours
            hours_previously_today -= attendance_worked_hours
            employee.hours_previously_today = hours_previously_today
            employee.hours_today = worked_hours

    @api.depends('attendance_ids')
    def _compute_last_attendance_id(self):
        for employee in self:
            employee.last_attendance_id = self.env['hr.attendance'].search([
                ('employee_id', 'in', employee.ids),
            ], order="check_in desc", limit=1)

    @api.depends('last_attendance_id.check_in', 'last_attendance_id.check_out', 'last_attendance_id')
    def _compute_attendance_state(self):
        for employee in self:
            att = employee.last_attendance_id.sudo()
            employee.attendance_state = att and not att.check_out and 'checked_in' or 'checked_out'

    def _attendance_action_change(self, geo_information=None):
        """ Check In/Check Out action
            Check In: create a new attendance record
            Check Out: modify check_out field of appropriate attendance record
        """
        self.ensure_one()
        action_date = fields.Datetime.now()

        if self.attendance_state != 'checked_in':
            if geo_information:
                vals = {
                    'employee_id': self.id,
                    'check_in': action_date,
                    **{'in_%s' % key: geo_information[key] for key in geo_information}
                }
            else:
                vals = {
                    'employee_id': self.id,
                    'check_in': action_date,
                }
            return self.env['hr.attendance'].create(vals)
        attendance = self.env['hr.attendance'].search([('employee_id', '=', self.id), ('check_out', '=', False)], limit=1)
        if attendance:
            if geo_information:
                attendance.write({
                    'check_out': action_date,
                    **{'out_%s' % key: geo_information[key] for key in geo_information}
                })
            else:
                attendance.write({
                    'check_out': action_date
                })
        else:
            raise exceptions.UserError(_(
                'Cannot perform check out on %(empl_name)s, could not find corresponding check in. '
                'Your attendances have probably been modified manually by human resources.',
                empl_name=self.sudo().name))
        return attendance

    def action_open_last_month_attendances(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Attendances This Month"),
            "res_model": "hr.attendance",
            "views": [[self.env.ref('hr_attendance.hr_attendance_employee_simple_tree_view').id, "list"]],
            "context": {
                "create": 0
            },
            "domain": [('employee_id', '=', self.id),
                       ('check_in', ">=", fields.datetime.today().replace(day=1, hour=0, minute=0))]
        }

    def action_open_last_month_overtime(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Attendances This Month"),
            "res_model": "hr.attendance",
            "views": [[self.env.ref('hr_attendance.hr_attendance_validated_hours_employee_simple_tree_view').id, "list"]],
            "context": {
                "create": 0
            },
            "domain": [('employee_id', '=', self.id), ('overtime_status', '=', 'approved')]
        }

    def _get_weekly_hours(self, start_date, end_date):
        """Calculate total working hours for the employee within a week."""
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_in', '>=', start_date),
            ('check_out', '<=', end_date),
            ('check_out', '!=', False)
        ])
        return sum(attendance.worked_hours for attendance in attendances)

    def _get_annual_overtime_hours(self, start_date, end_date):
        """Calculate total overtime hours for the employee within a year."""
        attendances = self.env['hr.attendance'].search([
            ('employee_id', '=', self.id),
            ('check_in', '>=', start_date),
            ('check_out', '<=', end_date),
            ('check_out', '!=', False)
        ])
        return sum(attendance.overtime_hours for attendance in attendances)

    def _check_missed_attendance(self):
        """Check if the employee missed check-in or check-out for the day and send notification."""
        from datetime import datetime, date
        today = date.today()
        for employee in self:
            # Check if employee has an attendance record for today
            attendance = self.env['hr.attendance'].search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', today),
                ('check_in', '<', today + relativedelta(days=1))
            ], limit=1)
            if not attendance and employee.resource_calendar_id:
                # Send notification to employee and manager
                message = _("Reminder: You have not checked in today. Please remember to record your attendance.")
                employee.message_post(body=message, partner_ids=[employee.user_id.partner_id.id])
                if employee.parent_id and employee.parent_id.user_id:
                    employee.message_post(body=message, partner_ids=[employee.parent_id.user_id.partner_id.id])
