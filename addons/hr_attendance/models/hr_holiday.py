# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields, api


class HrHoliday(models.Model):
    _name = "hr.holiday"
    _description = "Holiday"

    name = fields.Char(string='Holiday Name', required=True, help='Name of the holiday (e.g., Tet Nguyen Dan, National Day).')
    date = fields.Date(string='Date', required=True, help='Date of the holiday.')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company, help='Company to which this holiday applies.') 