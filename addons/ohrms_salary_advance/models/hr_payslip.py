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
from odoo import models, _


class HrPayslip(models.Model):
    """Class for the inherited model hr_payslip. Supering get_inputs() method
        inorder to add details of advance salary in the payslip."""
    _inherit = 'hr.payslip'

    def get_inputs(self, contract_ids, date_from, date_to):
        """Supering get_inputs() method inorder to add details of advance
           salary in the payslip."""
        res = super(HrPayslip, self).get_inputs(contract_ids, date_from,
                                                date_to)
        employee_id = self.env['hr.contract'].browse(
            contract_ids[0].id).employee_id if contract_ids \
            else self.employee_id
        # Lấy các khoản tạm ứng đã duyệt, chưa trừ, trong tháng này
        advances = self.env['salary.advance'].search([
            ('employee_id', '=', employee_id.id),
            ('state', '=', 'approve'),
            ('is_deducted', '=', False),
            ('date', '>=', date_from),
            ('date', '<=', date_to),
        ])
        total_advance = sum(a.advance for a in advances)
        for result in res:
            if result.get('code') == 'SAR':
                result['amount'] = -total_advance  # Trừ vào lương
        return res

    def action_payslip_done(self):
        res = super().action_payslip_done()
        for slip in self:
            advances = self.env['salary.advance'].search([
                ('employee_id', '=', slip.employee_id.id),
                ('state', '=', 'approve'),
                ('is_deducted', '=', False),
                ('date', '>=', slip.date_from),
                ('date', '<=', slip.date_to),
            ])
            advances.write({'is_deducted': True})
        return res
