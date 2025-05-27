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
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo import fields, models, api, _
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    """Create new model for getting Payslip Batches"""
    _name = 'hr.payslip.run'
    _description = 'Payslip Batches'

    name = fields.Char(required=True, help="Name for Payslip Batches",
                       string="Name")
    slip_ids = fields.One2many('hr.payslip',
                               'payslip_run_id',
                               string='Payslips',
                               help="Choose Payslips for Batches")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('close', 'Close'),
    ], string='Status', index=True, readonly=True, copy=False, default='draft',
                               help="Status for Payslip Batches")
    date_start = fields.Date(string='Date From', required=True,
                             help="start date for batch",
                             default=lambda self: fields.Date.to_string(
                                 date.today().replace(day=1)))
    date_end = fields.Date(string='Date To', required=True,
                           help="End date for batch",
                           default=lambda self: fields.Date.to_string(
                               (datetime.now() + relativedelta(months=+1, day=1,
                                                               days=-1)).date())
                           )
    credit_note = fields.Boolean(string='Credit Note',
                                 help="If its checked, indicates that all"
                                      "payslips generated from here are refund"
                                      "payslips.")

    def action_payslip_run(self):
        """Function for state change"""
        return self.write({'state': 'draft'})

    def close_payslip_run(self):
        """Function for state change"""
        return self.write({'state': 'close'})

    def action_generate_all_payslips(self):
        """Tự động tạo phiếu lương cho tất cả nhân viên có hợp đồng active trong kỳ lương."""
        employees = self.env['hr.employee'].search([
            ('contract_id.state', '=', 'open'),
            ('company_id', '=', self.env.company.id)
        ])
        if not employees:
            raise UserError(_('Không có nhân viên nào có hợp đồng active trong công ty hiện tại!'))
        payslips = self.env['hr.payslip']
        for employee in employees:
            slip_data = self.env['hr.payslip'].onchange_employee_id(
                self.date_start, self.date_end, employee.id, contract_id=False)
            res = {
                'employee_id': employee.id,
                'name': slip_data['value'].get('name'),
                'struct_id': slip_data['value'].get('struct_id'),
                'contract_id': slip_data['value'].get('contract_id'),
                'payslip_run_id': self.id,
                'input_line_ids': [(0, 0, x) for x in slip_data['value'].get('input_line_ids')],
                'worked_days_line_ids': [(0, 0, x) for x in slip_data['value'].get('worked_days_line_ids')],
                'date_from': self.date_start,
                'date_to': self.date_end,
                'credit_note': self.credit_note,
                'company_id': employee.company_id.id,
            }
            payslips += self.env['hr.payslip'].create(res)
        payslips.action_compute_sheet()
        return True

    @api.model
    def _cron_auto_generate_payslip_run(self):
        today = fields.Date.today()
        # Chỉ chạy vào ngày 25 hàng tháng
        if today.day != 25:
            return
        # Tìm kỳ lương tháng này
        date_start = today.replace(day=1)
        date_end = (date_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        run = self.create({
            'name': _('Payslip Run %s/%s') % (today.month, today.year),
            'date_start': date_start,
            'date_end': date_end,
        })
        run.action_generate_all_payslips()
