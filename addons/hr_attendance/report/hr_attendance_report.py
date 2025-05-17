# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class HrAttendanceReport(models.TransientModel):
    _name = "hr.attendance.report"
    _description = "Attendance Report"

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)
    start_date = fields.Date(string='Start Date', required=True)
    end_date = fields.Date(string='End Date', required=True)
    report_type = fields.Selection([('excel', 'Excel'), ('pdf', 'PDF')], string='Report Type', default='pdf', required=True)

    def action_generate_report(self):
        self.ensure_one()
        data = {
            'employee_id': self.employee_id.id,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'report_type': self.report_type,
        }
        if self.report_type == 'pdf':
            return self.env.ref('hr_attendance.action_report_attendance_pdf').report_action(self, data=data)
        else:
            return self.env.ref('hr_attendance.action_report_attendance_excel').report_action(self, data=data)

# Add detailed attendance report for Vietnam
class HrAttendanceReport(models.AbstractModel):
    _name = 'report.hr_attendance.attendance_report'
    _description = 'Báo cáo Chấm công Chi tiết'

    def _get_report_values(self, docids, data=None):
        employees = self.env['hr.employee'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'hr.employee',
            'docs': employees,
            'data': data,
        } 