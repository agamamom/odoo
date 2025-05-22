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
from odoo import api, fields, models, _


class InsurancePolicy(models.Model):
    """Used this model for insurance policy"""
    _name = 'insurance.policy'
    _description = "Policies of Insurance"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Policy Name', required=True, tracking=True)
    policy_type = fields.Selection([
        ('mandatory', 'Mandatory'),
        ('voluntary', 'Voluntary')
    ], string='Policy Type', required=True, default='mandatory', tracking=True)
    coverage_type = fields.Selection([
        ('bhxh', 'BHXH - Bảo hiểm xã hội'),
        ('bhyt', 'BHYT - Bảo hiểm y tế'),
        ('bhtn', 'BHTN - Bảo hiểm thất nghiệp'),
        ('bhtnlđ-bnn', 'BHTNLĐ-BNN - Bảo hiểm tai nạn lao động, bệnh nghề nghiệp'),
        ('other', 'Khác'),
    ], string='Coverage Type', required=True, default='bhxh', tracking=True)
    employee_rate = fields.Float(string='Employee Rate (%)', required=True, default=0.0, tracking=True)
    company_rate = fields.Float(string='Company Rate (%)', required=True, default=0.0, tracking=True)
    total_rate = fields.Float(string='Total Rate (%)', compute='_compute_total_rate', store=True)
    note = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, help="Company",
                                 default=lambda self: self.env.company)
    is_social_insurance = fields.Boolean(string="Là bảo hiểm xã hội", default=False)

    @api.depends('employee_rate', 'company_rate')
    def _compute_total_rate(self):
        for policy in self:
            policy.total_rate = policy.employee_rate + policy.company_rate
