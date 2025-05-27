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
import time
from datetime import datetime
from odoo import exceptions
from odoo.exceptions import UserError
from odoo import api, fields, models, _


class SalaryAdvanceApprovalLine(models.Model):
    _name = 'salary.advance.approval.line'
    _description = 'Lịch sử phê duyệt tạm ứng'

    salary_advance_id = fields.Many2one('salary.advance', string=_('Yêu cầu tạm ứng'), ondelete='cascade')
    level = fields.Integer(string=_('Cấp phê duyệt'))
    approver_id = fields.Many2one('res.users', string=_('Người phê duyệt'))
    state = fields.Selection([
        ('pending', _('Chờ duyệt')),
        ('approved', _('Đã duyệt')),
        ('rejected', _('Từ chối'))
    ], string=_('Trạng thái'), default='pending')
    note = fields.Text(string=_('Ghi chú'))
    date = fields.Datetime(string=_('Ngày phê duyệt'))


class SalaryAdvance(models.Model):
    """Class for the model salary_advance. Contains methods and fields of the
       model."""
    _name = "salary.advance"
    _description = "Tạm ứng lương"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string=_('Mã tạm ứng'), readonly=True, default=lambda self: 'TU/', help=_('Mã tạm ứng'))
    employee_id = fields.Many2one('hr.employee', string=_('Nhân viên'), required=True, help=_('Nhân viên'))
    date = fields.Date(string=_('Ngày tạm ứng'), required=True, default=lambda self: fields.Date.today(), help=_('Ngày tạo yêu cầu tạm ứng'))
    reason = fields.Text(string=_('Lý do tạm ứng'), help=_('Lý do tạm ứng'))
    currency_id = fields.Many2one('res.currency', string=_('Tiền tệ'), required=True, help=_('Tiền tệ công ty'), default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', string=_('Công ty'), required=True, help=_('Công ty'), default=lambda self: self.env.company)
    advance = fields.Float(string=_('Số tiền tạm ứng'), required=True, help=_('Số tiền tạm ứng'))
    payment_method_id = fields.Many2one('account.journal', string=_('Phương thức thanh toán'), help=_('Phương thức thanh toán tạm ứng'))
    exceed_condition = fields.Boolean(string=_('Vượt quá mức cho phép'), help=_('Tạm ứng vượt quá mức cho phép'))
    department_id = fields.Many2one('hr.department', string=_('Phòng ban'), related='employee_id.department_id', help=_('Phòng ban'))
    state = fields.Selection([
        ('draft', _('Nháp')),
        ('submit', _('Đã gửi phê duyệt')),
        ('waiting_approval', _('Chờ phê duyệt')),
        ('approve', _('Đã duyệt')),
        ('cancel', _('Đã hủy')),
        ('reject', _('Từ chối'))
    ], string=_('Trạng thái'), default='draft', tracking=True, help=_('Trạng thái tạm ứng'))
    debit_id = fields.Many2one('account.account', string=_('Tài khoản nợ'), help=_('Tài khoản nợ'))
    credit_id = fields.Many2one('account.account', string=_('Tài khoản có'), help=_('Tài khoản có'))
    journal_id = fields.Many2one('account.journal', string=_('Nhật ký kế toán'), help=_('Nhật ký kế toán'))
    employee_contract_id = fields.Many2one('hr.contract', string=_('Hợp đồng lao động'), related='employee_id.contract_id', help=_('Hợp đồng lao động'))
    approval_level = fields.Integer(string=_('Số cấp phê duyệt'), default=1, help=_('Số cấp phê duyệt'))
    current_approval_level = fields.Integer(string=_('Cấp phê duyệt hiện tại'), default=1)
    approval_line_ids = fields.One2many('salary.advance.approval.line', 'salary_advance_id', string=_('Lịch sử phê duyệt'))
    reject_reason = fields.Text(string=_('Lý do từ chối'))
    is_deducted = fields.Boolean(string=_('Đã trừ vào lương'), default=False)
    attachments = fields.Many2many(
        'ir.attachment',
        'salary_advance_attachment_rel',
        'salary_advance_id',
        'attachment_id',
        string=_('Tệp đính kèm')
    )
    advance_type = fields.Selection([
        ('salary', _('Tạm ứng lương')),
        ('travel', _('Tạm ứng công tác phí')),
        ('other', _('Tạm ứng khác'))
    ], string=_('Loại tạm ứng'), default='salary', required=True)

    @api.onchange('company_id')
    def _onchange_company_id(self):
        """This method will trigger when there is a change in company_id."""
        company = self.company_id
        domain = [('company_id.id', '=', company.id)]
        result = {
            'domain': {
                'journal_id': domain,
            },
        }
        return result

    def _get_advance_limit(self):
        """Tính hạn mức tạm ứng theo nhân viên, phòng ban, công ty, hợp đồng."""
        # Ưu tiên: nhân viên > phòng ban > công ty > hợp đồng
        limit = 0
        # Có thể mở rộng lấy từ model salary.advance.limit nếu có
        if self.employee_contract_id and self.employee_contract_id.struct_id and self.employee_contract_id.struct_id.max_percent:
            limit = self.employee_contract_id.wage * self.employee_contract_id.struct_id.max_percent / 100.0
        return limit

    def _check_advance_limit(self):
        """Kiểm tra tổng tạm ứng trong tháng không vượt hạn mức."""
        limit = self._get_advance_limit()
        month = self.date.month
        year = self.date.year
        advances = self.search([
            ('employee_id', '=', self.employee_id.id),
            ('state', 'in', ['approve', 'waiting_approval', 'submit']),
            ('date', '>=', f'{year}-{month:02d}-01'),
            ('date', '<=', f'{year}-{month:02d}-31'),
            ('id', '!=', self.id)
        ])
        total = sum(a.advance for a in advances) + self.advance
        if limit and total > limit:
            raise UserError(_('Tổng số tiền tạm ứng trong tháng vượt quá hạn mức cho phép: %s') % limit)

    def action_submit_to_manager(self):
        self._check_advance_limit()
        # Kiểm tra số tiền tạm ứng không vượt quá lương cơ bản
        if not self.employee_contract_id or not self.employee_contract_id.wage:
            raise UserError(_('Không tìm thấy hợp đồng hoặc lương cơ bản của nhân viên.'))
        if self.advance > (self.employee_contract_id.wage * 0.4):
            raise UserError(_('Số tiền tạm ứng không được vượt quá 40%% lương cơ bản của nhân viên (%s).') % self.employee_contract_id.wage)
        self.state = 'submit'
        self.message_post(body=_('Yêu cầu tạm ứng đã được gửi phê duyệt.'))
        # Tạo dòng phê duyệt nếu chưa có
        if not self.approval_line_ids:
            for i in range(1, self.approval_level + 1):
                self.env['salary.advance.approval.line'].create({
                    'salary_advance_id': self.id,
                    'level': i,
                    'state': 'pending',
                })
        self.current_approval_level = 1

    def action_approve_level(self):
        """Duyệt ở cấp hiện tại, chỉ đúng người mới được duyệt."""
        line = self.approval_line_ids.filtered(lambda l: l.level == self.current_approval_level and l.state == 'pending')
        if not line:
            raise UserError(_('Không có dòng phê duyệt hợp lệ ở cấp này.'))
        # Có thể kiểm tra quyền user ở đây nếu cần
        line.write({'state': 'approved', 'approver_id': self.env.user.id, 'date': fields.Datetime.now()})
        self.message_post(body=_('Đã duyệt cấp %s bởi %s.') % (self.current_approval_level, self.env.user.name))
        if self.current_approval_level < self.approval_level:
            self.current_approval_level += 1
        else:
            self.state = 'waiting_approval'
            self.message_post(body=_('Yêu cầu đã được duyệt qua tất cả các cấp.'))

    def action_reject_level(self, note=None):
        """Từ chối ở cấp hiện tại."""
        line = self.approval_line_ids.filtered(lambda l: l.level == self.current_approval_level and l.state == 'pending')
        if not line:
            raise UserError(_('Không có dòng phê duyệt hợp lệ ở cấp này.'))
        line.write({'state': 'rejected', 'approver_id': self.env.user.id, 'date': fields.Datetime.now(), 'note': note or ''})
        self.state = 'reject'
        self.reject_reason = note or ''
        self.message_post(body=_('Yêu cầu bị từ chối ở cấp %s bởi %s. Lý do: %s') % (self.current_approval_level, self.env.user.name, note or ''))

    def approve_request(self):
        """Duyệt cấp 1: chỉ cho phép khi trạng thái là 'submit'."""
        if self.state != 'submit':
            raise UserError(_('Chỉ có thể duyệt cấp 1 khi trạng thái là "Đã gửi phê duyệt".'))
        self.state = 'waiting_approval'
        # Lưu lịch sử phê duyệt cấp 1
        line = self.approval_line_ids.filtered(lambda l: l.level == 1 and l.state == 'pending')
        if line:
            line.write({'state': 'approved', 'approver_id': self.env.user.id, 'date': fields.Datetime.now()})
        self.current_approval_level = 2
        self.message_post(body=_('Yêu cầu tạm ứng đã được duyệt cấp 1 bởi %s.') % self.env.user.name)

    def approve_request_acc_dept(self):
        """Duyệt cấp 2: chỉ cho phép khi trạng thái là 'waiting_approval'.
        Sau khi duyệt, tự động cập nhật input SAR trên các phiếu lương draft và done của nhân viên trong tháng ứng lương."""
        if self.state != 'waiting_approval':
            raise UserError(_('Chỉ có thể duyệt cấp 2 khi trạng thái là "Chờ phê duyệt".'))
        self.state = 'approve'
        # Lưu lịch sử phê duyệt cấp 2
        line = self.approval_line_ids.filtered(lambda l: l.level == 2 and l.state == 'pending')
        if line:
            line.write({'state': 'approved', 'approver_id': self.env.user.id, 'date': fields.Datetime.now()})
        self.current_approval_level = 3
        self.message_post(body=_('Yêu cầu tạm ứng đã được duyệt cấp 2 bởi %s.') % self.env.user.name)

        # --- Bổ sung: Tự động cập nhật input SAR trên các phiếu lương liên quan ---
        payslip_obj = self.env['hr.payslip']
        # Tìm các phiếu lương của nhân viên trong tháng ứng lương (draft và done)
        payslips = payslip_obj.search([
            ('employee_id', '=', self.employee_id.id),
            ('date_from', '<=', self.date),
            ('date_to', '>=', self.date),
            ('state', 'in', ['draft', 'done'])
        ])
        for payslip in payslips:
            # Lấy lại input mới (luôn là recordset)
            if payslip.contract_id:
                contracts = payslip.contract_id
            else:
                contract_ids = payslip.get_contract(payslip.employee_id, payslip.date_from, payslip.date_to)
                contracts = payslip.env['hr.contract'].browse(contract_ids)
            input_lines = payslip.get_inputs(contracts, payslip.date_from, payslip.date_to)
            # Cập nhật hoặc tạo mới input SAR
            for input_data in input_lines:
                if input_data.get('code') == 'SAR':
                    sar_input = payslip.input_line_ids.filtered(lambda l: l.code == 'SAR')
                    vals_update = {
                        'amount': input_data['amount'],
                    }
                    # Nếu là input SAR, truyền thêm ngày tạo và ngày duyệt ứng lương
                    if self.date:
                        vals_update['advance_create_date'] = self.date
                    # Lấy ngày duyệt cấp 2 (ưu tiên lấy dòng vừa duyệt, nếu không có thì lấy ngày hiện tại)
                    approve_line = self.approval_line_ids.filtered(lambda l: l.level == 2 and l.state == 'approved')
                    approve_date = False
                    if approve_line:
                        approve_date = approve_line[-1].date
                    else:
                        # Nếu vừa duyệt thì lấy luôn ngày hiện tại
                        approve_date = fields.Datetime.now()
                    if approve_date:
                        vals_update['advance_approve_date'] = approve_date
                    if sar_input:
                        sar_input.write(vals_update)
                    else:
                        vals_create = {
                            'name': input_data['name'],
                            'code': input_data['code'],
                            'amount': input_data['amount'],
                            'contract_id': input_data['contract_id'],
                            'date_from': input_data['date_from'],
                            'date_to': input_data['date_to'],
                            'payslip_id': payslip.id,
                        }
                        if self.date:
                            vals_create['advance_create_date'] = self.date
                        if approve_date:
                            vals_create['advance_approve_date'] = approve_date
                        payslip.input_line_ids.create(vals_create)
                    payslip.message_post(body=_('Đã tự động cập nhật số tiền ứng lương (SAR) sau khi duyệt tạm ứng.'))
            payslip.action_compute_sheet()

    def mark_deducted_notify(self):
        self.is_deducted = True
        self.message_post(body=_('Khoản tạm ứng đã được khấu trừ vào lương.'))

    @api.model
    def create(self, vals):
        """Supering the create method to generate sequence for the salary
         advance."""
        vals['name'] = self.env['ir.sequence'].get('salary.advance.seq') or ' '
        res_id = super(SalaryAdvance, self).create(vals)
        return res_id

    def action_cancel(self):
        """Method of a button. Changing the state of the salary advance."""
        self.state = 'cancel'

    def action_reject(self):
        """Method of a button. Changing the state of the salary advance."""
        self.state = 'reject'


class SalaryAdvanceReport(models.Model):
    _name = 'salary.advance.report'
    _description = 'Báo cáo tổng hợp tạm ứng lương'
    _auto = False

    employee_id = fields.Many2one('hr.employee', string='Nhân viên')
    department_id = fields.Many2one('hr.department', string='Phòng ban')
    month = fields.Char(string='Tháng')
    total_advance = fields.Float(string='Tổng tạm ứng')
    total_deducted = fields.Float(string='Đã khấu trừ')
    total_remaining = fields.Float(string='Còn lại')

    def init(self):
        self.env.cr.execute('''
            CREATE OR REPLACE VIEW salary_advance_report AS (
                SELECT
                    min(sa.id) as id,
                    sa.employee_id,
                    emp.department_id,
                    to_char(sa.date, 'YYYY-MM') as month,
                    sum(sa.advance) as total_advance,
                    sum(CASE WHEN sa.is_deducted THEN sa.advance ELSE 0 END) as total_deducted,
                    sum(CASE WHEN NOT sa.is_deducted THEN sa.advance ELSE 0 END) as total_remaining
                FROM salary_advance sa
                LEFT JOIN hr_employee emp ON sa.employee_id = emp.id
                WHERE sa.state = 'approve'
                GROUP BY sa.employee_id, emp.department_id, to_char(sa.date, 'YYYY-MM')
            )
        ''')
