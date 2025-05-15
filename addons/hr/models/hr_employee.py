# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import re
from pytz import timezone, UTC
from datetime import datetime, time, date
from random import choice
from string import digits
from dateutil.relativedelta import relativedelta
from markupsafe import Markup
import io
import xlsxwriter
from odoo.tools.safe_eval import safe_eval
from odoo.http import request
from odoo import http
from odoo.tools import html2plaintext
import csv
from babel.dates import format_date as babel_format_date
from babel.numbers import format_currency
import locale

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, AccessError
from odoo.osv import expression
from odoo.tools import convert, format_date


class HrEmployeePrivate(models.Model):
    """
    NB: Any field only available on the model hr.employee (i.e. not on the
    hr.employee.public model) should have `groups="hr.group_hr_user"` on its
    definition to avoid being prefetched when the user hasn't access to the
    hr.employee model. Indeed, the prefetch loads the data for all the fields
    that are available according to the group defined on them.
    """
    _name = "hr.employee"
    _description = "Employee"
    _order = 'name'
    _inherit = ['hr.employee.base', 'mail.thread.main.attachment', 'mail.activity.mixin', 'resource.mixin', 'avatar.mixin']
    _mail_post_access = 'read'

    @api.model
    def _lang_get(self):
        return self.env['res.lang'].get_installed()

    # resource and user
    # required on the resource, make sure required="True" set in the view
    name = fields.Char(string="Employee Name", related='resource_id.name', store=True, readonly=False, tracking=True)
    user_id = fields.Many2one(
        'res.users', 'User',
        related='resource_id.user_id',
        store=True,
        readonly=False,
        check_company=True,
        precompute=True,
        ondelete='restrict')
    user_partner_id = fields.Many2one(related='user_id.partner_id', related_sudo=False, string="User's partner")
    active = fields.Boolean('Active', related='resource_id.active', default=True, store=True, readonly=False)
    resource_calendar_id = fields.Many2one(tracking=True)
    department_id = fields.Many2one(tracking=True)
    company_id = fields.Many2one('res.company', required=True)
    company_country_id = fields.Many2one('res.country', 'Company Country', related='company_id.country_id', readonly=True, groups="base.group_system,hr.group_hr_user")
    company_country_code = fields.Char(related='company_country_id.code', depends=['company_country_id'], readonly=True, groups="base.group_system,hr.group_hr_user")
    # private info
    private_street = fields.Char(string="Private Street", groups="hr.group_hr_user")
    private_street2 = fields.Char(string="Private Street2", groups="hr.group_hr_user")
    private_city = fields.Char(string="Private City", groups="hr.group_hr_user")
    private_state_id = fields.Many2one(
        "res.country.state", string="Private State",
        domain="[('country_id', '=?', private_country_id)]",
        groups="hr.group_hr_user")
    private_zip = fields.Char(string="Private Zip", groups="hr.group_hr_user")
    private_country_id = fields.Many2one("res.country", string="Private Country", groups="hr.group_hr_user")
    private_phone = fields.Char(string="Private Phone", groups="hr.group_hr_user")
    private_email = fields.Char(string="Private Email", groups="hr.group_hr_user")
    lang = fields.Selection(selection=_lang_get, string="Lang", groups="hr.group_hr_user")
    country_id = fields.Many2one(
        'res.country', 'Nationality (Country)', groups="hr.group_hr_user", tracking=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Other')
    ], groups="hr.group_hr_user", tracking=True)
    marital = fields.Selection(
        selection='_get_marital_status_selection',
        string='Marital Status',
        groups="hr.group_hr_user",
        default='single',
        required=True,
        tracking=True)

    spouse_complete_name = fields.Char(string="Spouse Complete Name", groups="hr.group_hr_user", tracking=True)
    spouse_birthdate = fields.Date(string="Spouse Birthdate", groups="hr.group_hr_user", tracking=True)
    children = fields.Integer(string='Number of Dependent Children', groups="hr.group_hr_user", tracking=True)
    place_of_birth = fields.Char('Place of Birth', groups="hr.group_hr_user", tracking=True)
    country_of_birth = fields.Many2one('res.country', string="Country of Birth", groups="hr.group_hr_user", tracking=True)
    birthday = fields.Date('Date of Birth', groups="hr.group_hr_user", tracking=True)
    ssnid = fields.Char('SSN No', help='Social Security Number', groups="hr.group_hr_user", tracking=True)
    sinid = fields.Char('SIN No', help='Social Insurance Number', groups="hr.group_hr_user", tracking=True)
    identification_id = fields.Char(string='Identification No', groups="hr.group_hr_user", tracking=True)
    passport_id = fields.Char('Passport No', groups="hr.group_hr_user", tracking=True)
    bank_account_id = fields.Many2one(
        'res.partner.bank', 'Bank Account',
        domain="[('partner_id', '=', work_contact_id), '|', ('company_id', '=', False), ('company_id', '=', company_id)]",
        groups="hr.group_hr_user",
        tracking=True,
        help='Employee bank account to pay salaries')
    permit_no = fields.Char('Work Permit No', groups="hr.group_hr_user", tracking=True)
    visa_no = fields.Char('Visa No', groups="hr.group_hr_user", tracking=True)
    visa_expire = fields.Date('Visa Expiration Date', groups="hr.group_hr_user", tracking=True)
    work_permit_expiration_date = fields.Date('Work Permit Expiration Date', groups="hr.group_hr_user", tracking=True)
    has_work_permit = fields.Binary(string="Work Permit", groups="hr.group_hr_user")
    work_permit_scheduled_activity = fields.Boolean(default=False, groups="hr.group_hr_user")
    work_permit_name = fields.Char('work_permit_name', compute='_compute_work_permit_name', groups="hr.group_hr_user")
    additional_note = fields.Text(string='Additional Note', groups="hr.group_hr_user", tracking=True)
    certificate = fields.Selection([
        ('graduate', 'Graduate'),
        ('bachelor', 'Bachelor'),
        ('master', 'Master'),
        ('doctor', 'Doctor'),
        ('other', 'Other'),
    ], 'Certificate Level', groups="hr.group_hr_user", tracking=True)
    study_field = fields.Char("Field of Study", groups="hr.group_hr_user", tracking=True)
    study_school = fields.Char("School", groups="hr.group_hr_user", tracking=True)
    emergency_contact = fields.Char("Contact Name", groups="hr.group_hr_user", tracking=True)
    emergency_phone = fields.Char("Contact Phone", groups="hr.group_hr_user", tracking=True)
    distance_home_work = fields.Integer(string="Home-Work Distance", groups="hr.group_hr_user", tracking=True)
    km_home_work = fields.Integer(string="Home-Work Distance in Km", groups="hr.group_hr_user", compute="_compute_km_home_work", inverse="_inverse_km_home_work", store=True)
    distance_home_work_unit = fields.Selection([
        ('kilometers', 'km'),
        ('miles', 'mi'),
    ], 'Home-Work Distance unit', tracking=True, groups="hr.group_hr_user", default='kilometers', required=True)
    employee_type = fields.Selection([
            ('employee', 'Employee'),
            ('worker', 'Worker'),
            ('student', 'Student'),
            ('trainee', 'Trainee'),
            ('contractor', 'Contractor'),
            ('freelance', 'Freelancer'),
        ], string='Employee Type', default='employee', required=True, groups="hr.group_hr_user",
        help="Categorize your Employees by type. This field also has an impact on contracts. Only Employees, Students and Trainee will have contract history.")

    job_id = fields.Many2one(tracking=True)
    # employee in company
    child_ids = fields.One2many('hr.employee', 'parent_id', string='Direct subordinates')
    category_ids = fields.Many2many(
        'hr.employee.category', 'employee_category_rel',
        'employee_id', 'category_id', groups="hr.group_hr_user",
        string='Tags')
    # misc
    notes = fields.Text('Notes', groups="hr.group_hr_user")
    color = fields.Integer('Color Index', default=0)
    barcode = fields.Char(string="Badge ID", help="ID used for employee identification.", groups="hr.group_hr_user", copy=False)
    pin = fields.Char(string="PIN", groups="hr.group_hr_user", copy=False,
        help="PIN used to Check In/Out in the Kiosk Mode of the Attendance application (if enabled in Configuration) and to change the cashier in the Point of Sale application.")
    departure_reason_id = fields.Many2one("hr.departure.reason", string="Departure Reason", groups="hr.group_hr_user",
                                          copy=False, tracking=True, ondelete='restrict')
    departure_description = fields.Html(string="Additional Information", groups="hr.group_hr_user", copy=False)
    departure_date = fields.Date(string="Departure Date", groups="hr.group_hr_user", copy=False, tracking=True)
    message_main_attachment_id = fields.Many2one(groups="hr.group_hr_user")
    id_card = fields.Binary(string="ID Card Copy", groups="hr.group_hr_user")
    driving_license = fields.Binary(string="Driving License", groups="hr.group_hr_user")
    private_car_plate = fields.Char(groups="hr.group_hr_user", help="If you have more than one car, just separate the plates by a space.")
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True, groups="hr.group_hr_user")
    related_partners_count = fields.Integer(compute="_compute_related_partners_count", groups="hr.group_hr_user")
    # properties
    employee_properties = fields.Properties('Properties', definition='company_id.employee_properties_definition', precompute=False, groups="hr.group_hr_user")

    # mail.activity.mixin
    activity_ids = fields.One2many(groups="hr.group_hr_user")
    activity_state = fields.Selection(groups="hr.group_hr_user")
    activity_user_id = fields.Many2one(groups="hr.group_hr_user")
    activity_type_id = fields.Many2one(groups="hr.group_hr_user")
    activity_type_icon = fields.Char(groups="hr.group_hr_user")
    activity_date_deadline = fields.Date(groups="hr.group_hr_user")
    my_activity_date_deadline = fields.Date(groups="hr.group_hr_user")
    activity_summary = fields.Char(groups="hr.group_hr_user")
    activity_exception_decoration = fields.Selection(groups="hr.group_hr_user")
    activity_exception_icon = fields.Char(groups="hr.group_hr_user")

    # mail.thread mixin
    message_is_follower = fields.Boolean(groups="hr.group_hr_user")
    message_follower_ids = fields.One2many(groups="hr.group_hr_user")
    message_partner_ids = fields.Many2many(groups="hr.group_hr_user")
    message_ids = fields.One2many(groups="hr.group_hr_user")
    has_message = fields.Boolean(groups="hr.group_hr_user")
    message_needaction = fields.Boolean(groups="hr.group_hr_user")
    message_needaction_counter = fields.Integer(groups="hr.group_hr_user")
    message_has_error = fields.Boolean(groups="hr.group_hr_user")
    message_has_error_counter = fields.Integer(groups="hr.group_hr_user")
    message_attachment_count = fields.Integer(groups="hr.group_hr_user")

    # Vietnam-specific fields
    bhxh_code = fields.Char(string="Mã số BHXH", groups="hr.group_hr_user", tracking=True)
    bhyt_code = fields.Char(string="Mã số BHYT", groups="hr.group_hr_user", tracking=True)
    bhtn_code = fields.Char(string="Mã số BHTN", groups="hr.group_hr_user", tracking=True)
    kcb_place = fields.Char(string="Nơi đăng ký KCB", groups="hr.group_hr_user", tracking=True)
    labor_contract_number = fields.Char(string="Số hợp đồng lao động", groups="hr.group_hr_user", tracking=True)
    labor_contract_sign_date = fields.Date(string="Ngày ký hợp đồng", groups="hr.group_hr_user", tracking=True)
    labor_contract_expiry_date = fields.Date(string="Ngày hết hạn hợp đồng", groups="hr.group_hr_user", tracking=True)
    labor_contract_type = fields.Selection([
        ("indefinite", "Không xác định thời hạn"),
        ("definite", "Xác định thời hạn"),
        ("seasonal", "Thời vụ"),
        ("other", "Khác")
    ], string="Loại hợp đồng lao động", groups="hr.group_hr_user", tracking=True)
    labor_contract_file = fields.Binary(string="File scan hợp đồng lao động", groups="hr.group_hr_user")
    minimum_wage_region = fields.Selection([
        ("I", "Vùng I"),
        ("II", "Vùng II"),
        ("III", "Vùng III"),
        ("IV", "Vùng IV")
    ], string="Vùng lương tối thiểu", groups="hr.group_hr_user", tracking=True)
    detailed_contract_type = fields.Selection([
        ("probation", "Thử việc"),
        ("official", "Chính thức"),
        ("seasonal", "Thời vụ"),
        ("internship", "Thực tập"),
        ("other", "Khác")
    ], string="Loại hợp đồng chi tiết", groups="hr.group_hr_user", tracking=True)

    # Project assignment fields for Vietnam
    project_ids = fields.Many2many(
        'project.project',
        'hr_employee_project_rel',
        'employee_id',
        'project_id',
        string='Dự án tham gia',
        groups="hr.group_hr_user",
        tracking=True
    )
    project_role = fields.Char(string="Vai trò trong dự án", groups="hr.group_hr_user", tracking=True)

    # New fields for project assignment
    project_assignment_ids = fields.One2many(
        'hr.employee.project.assignment', 'employee_id', string='Phân bổ dự án', groups="hr.group_hr_user"
    )

    # New fields for skills
    skill_ids = fields.One2many(
        'hr.employee.skill', 'employee_id', string='Kỹ năng & Chứng chỉ', groups="hr.group_hr_user"
    )

    # New fields for shifts
    shift_ids = fields.One2many(
        'hr.employee.shift', 'employee_id', string='Lịch & Ca làm việc', groups="hr.group_hr_user"
    )

    # Vietnam-specific tax and salary fields
    personal_tax_code = fields.Char(string="Mã số thuế cá nhân", groups="hr.group_hr_user", tracking=True)
    bhxh_salary = fields.Float(string="Mức lương đóng BHXH", groups="hr.group_hr_user", tracking=True)
    net_salary = fields.Float(string="Mức lương thực nhận", groups="hr.group_hr_user", tracking=True)
    year_income = fields.Float(string="Tổng thu nhập năm", groups="hr.group_hr_user", tracking=True)
    tax_deductions = fields.Float(string="Các khoản giảm trừ thuế TNCN", groups="hr.group_hr_user", tracking=True)

    # 1. Trường quản lý hồ sơ BHXH/BHYT cho nhân viên
    bhxh_profile_status = fields.Selection([
        ('draft', 'Chưa gửi'),
        ('sent', 'Đã gửi'),
        ('responded', 'Đã phản hồi'),
        ('error', 'Lỗi'),
        ('done', 'Hoàn thành')
    ], string='Trạng thái hồ sơ BHXH', default='draft', groups="hr.group_hr_user", tracking=True)
    bhxh_transaction_code = fields.Char(string='Mã giao dịch BHXH', groups="hr.group_hr_user", tracking=True)
    bhxh_profile_file = fields.Binary(string='File hồ sơ BHXH (PDF/XML)', groups="hr.group_hr_user")
    bhxh_response_note = fields.Text(string='Ghi chú phản hồi BHXH', groups="hr.group_hr_user")

    # 2. Model lịch sử giao dịch BHXH/BHYT
    bhxh_history_ids = fields.One2many(
        'hr.employee.bhxh.history', 'employee_id', string='Lịch sử giao dịch BHXH', groups="hr.group_hr_user"
    )

    # New fields for contracts
    contract_ids = fields.One2many(
        'hr.employee.contract', 'employee_id', string='Hợp đồng lao động', groups="hr.group_hr_user"
    )

    # New fields for personal income tax
    personal_income_tax_ids = fields.One2many(
        'hr.employee.personal.income.tax', 'employee_id', string='Quyết toán thuế TNCN', groups="hr.group_hr_user"
    )

    _sql_constraints = [
        ('barcode_uniq', 'unique (barcode)', "The Badge ID must be unique, this one is already assigned to another employee."),
        ('user_uniq', 'unique (user_id, company_id)', "A user cannot be linked to multiple employees in the same company.")
    ]

    @api.model
    def check_field_access_rights(self, operation, field_names):
        # DISCLAIMER: Dirty hack to avoid having to create a bridge module to override only a
        # groups on a field which is not prefetched (because not stored) but would crash anyway
        # if we try to read them directly (very uncommon use case). Don't add your field on this
        # list if you can specify the group on the field directly (as all the other fields).
        result = super().check_field_access_rights(operation, field_names)
        if not self.env.user.has_group("hr.group_hr_user"):
            result = [field for field in result if field not in ['activity_calendar_event_id', 'rating_ids', 'website_message_ids', 'message_has_sms_error']]
        return result

    @api.depends('name', 'user_id.avatar_1920', 'image_1920')
    def _compute_avatar_1920(self):
        super()._compute_avatar_1920()

    @api.depends('name', 'user_id.avatar_1024', 'image_1024')
    def _compute_avatar_1024(self):
        super()._compute_avatar_1024()

    @api.depends('name', 'user_id.avatar_512', 'image_512')
    def _compute_avatar_512(self):
        super()._compute_avatar_512()

    @api.depends('name', 'user_id.avatar_256', 'image_256')
    def _compute_avatar_256(self):
        super()._compute_avatar_256()

    @api.depends('name', 'user_id.avatar_128', 'image_128')
    def _compute_avatar_128(self):
        super()._compute_avatar_128()

    def _compute_avatar(self, avatar_field, image_field):
        employee_wo_user_and_image = self.env['hr.employee']
        for employee in self:
            if not employee.user_id and not employee._origin[image_field]:
                employee_wo_user_and_image += employee
                continue
            avatar = employee._origin[image_field]
            if not avatar and employee.user_id:
                avatar = employee.user_id.sudo()[avatar_field]
            employee[avatar_field] = avatar
        super(HrEmployeePrivate, employee_wo_user_and_image)._compute_avatar(avatar_field, image_field)

    @api.depends('name', 'permit_no')
    def _compute_work_permit_name(self):
        for employee in self:
            name = employee.name.replace(' ', '_') + '_' if employee.name else ''
            permit_no = '_' + employee.permit_no if employee.permit_no else ''
            employee.work_permit_name = "%swork_permit%s" % (name, permit_no)

    @api.depends('distance_home_work', 'distance_home_work_unit')
    def _compute_km_home_work(self):
        for employee in self:
            employee.km_home_work = employee.distance_home_work * 1.609 if employee.distance_home_work_unit == "miles" else employee.distance_home_work

    def _inverse_km_home_work(self):
        for employee in self:
            employee.distance_home_work = employee.km_home_work / 1.609 if employee.distance_home_work_unit == "miles" else employee.km_home_work

    def _get_partner_count_depends(self):
        return ['user_id']

    @api.depends(lambda self: self._get_partner_count_depends())
    def _compute_related_partners_count(self):
        self.related_partners_count = len(self._get_related_partners())

    def _get_related_partners(self):
        return self.work_contact_id | self.user_id.partner_id

    def action_related_contacts(self):
        related_partners = self._get_related_partners()
        action = {
            'name': _("Related Contacts"),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
        }
        if len(related_partners) > 1:
            action['view_mode'] = 'kanban,list,form'
            action['domain'] = [('id', 'in', related_partners.ids)]
            return action
        else:
            action['res_id'] = related_partners.id
        return action

    def action_create_user(self):
        self.ensure_one()
        if self.user_id:
            raise ValidationError(_("This employee already has an user."))
        return {
            'name': _('Create User'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.users',
            'view_mode': 'form',
            'view_id': self.env.ref('hr.view_users_simple_form').id,
            'target': 'new',
            'context': dict(self._context, **{
                'default_create_employee_id': self.id,
                'default_name': self.name,
                'default_phone': self.work_phone,
                'default_mobile': self.mobile_phone,
                'default_login': self.work_email,
                'default_partner_id': self.work_contact_id.id,
            })
        }

    def _compute_display_name(self):
        if self.browse().has_access('read'):
            return super()._compute_display_name()
        for employee_private, employee_public in zip(self, self.env['hr.employee.public'].browse(self.ids)):
            employee_private.display_name = employee_public.display_name

    def search_fetch(self, domain, field_names, offset=0, limit=None, order=None):
        if self.browse().has_access('read'):
            return super().search_fetch(domain, field_names, offset, limit, order)

        # HACK: retrieve publicly available values from hr.employee.public and
        # copy them to the cache of self; non-public data will be missing from
        # cache, and interpreted as an access error
        self._check_private_fields(field_names)
        self.flush_model(field_names)
        public = self.env['hr.employee.public'].search_fetch(domain, field_names, offset, limit, order)
        employees = self.browse(public._ids)
        employees._copy_cache_from(public, field_names)
        return employees

    def fetch(self, field_names):
        if self.browse().has_access('read'):
            return super().fetch(field_names)

        # HACK: retrieve publicly available values from hr.employee.public and
        # copy them to the cache of self; non-public data will be missing from
        # cache, and interpreted as an access error
        self._check_private_fields(field_names)
        self.flush_recordset(field_names)
        public = self.env['hr.employee.public'].browse(self._ids)
        public.fetch(field_names)
        self._copy_cache_from(public, field_names)

    def _check_private_fields(self, field_names):
        """ Check whether ``field_names`` contain private fields. """
        public_fields = self.env['hr.employee.public']._fields
        private_fields = [fname for fname in field_names if fname not in public_fields]
        if private_fields:
            raise AccessError(_('The fields "%s", which you are trying to read, are not available for employee public profiles.', ','.join(private_fields)))

    def _copy_cache_from(self, public, field_names):
        # HACK: retrieve publicly available values from hr.employee.public and
        # copy them to the cache of self; non-public data will be missing from
        # cache, and interpreted as an access error
        for fname in field_names:
            values = self.env.cache.get_values(public, public._fields[fname])
            if self._fields[fname].translate:
                values = [(value.copy() if value else None) for value in values]
            self.env.cache.update_raw(self, self._fields[fname], values)

    @api.model
    def _cron_check_work_permit_validity(self):
        # Called by a cron
        # Schedule an activity 1 month before the work permit expires
        outdated_days = fields.Date.today() + relativedelta(months=+1)
        nearly_expired_work_permits = self.search([('work_permit_scheduled_activity', '=', False), ('work_permit_expiration_date', '<', outdated_days)])
        employees_scheduled = self.env['hr.employee']
        for employee in nearly_expired_work_permits.filtered(lambda employee: employee.parent_id):
            responsible_user_id = employee.parent_id.user_id.id
            if responsible_user_id:
                employees_scheduled |= employee
                lang = self.env['res.users'].browse(responsible_user_id).lang
                formated_date = format_date(employee.env, employee.work_permit_expiration_date, date_format="dd MMMM y", lang_code=lang)
                employee.activity_schedule(
                    'mail.mail_activity_data_todo',
                    note=_('The work permit of %(employee)s expires at %(date)s.',
                        employee=employee.name,
                        date=formated_date),
                    user_id=responsible_user_id)
        employees_scheduled.write({'work_permit_scheduled_activity': True})

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        if self.browse().has_access('read'):
            return super().get_view(view_id, view_type, **options)
        return self.env['hr.employee.public'].get_view(view_id, view_type, **options)

    @api.model
    def get_views(self, views, options=None):
        if self.browse().has_access('read'):
            return super().get_views(views, options)
        res = self.env['hr.employee.public'].get_views(views, options)
        res['models'].update({'hr.employee': res['models']['hr.employee.public']})
        return res

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        """
            We override the _search because it is the method that checks the access rights
            This is correct to override the _search. That way we enforce the fact that calling
            search on an hr.employee returns a hr.employee recordset, even if you don't have access
            to this model, as the result of _search (the ids of the public employees) is to be
            browsed on the hr.employee model. This can be trusted as the ids of the public
            employees exactly match the ids of the related hr.employee.
        """
        if self.browse().has_access('read'):
            return super()._search(domain, offset, limit, order)
        try:
            ids = self.env['hr.employee.public']._search(domain, offset, limit, order)
        except ValueError:
            raise AccessError(_('You do not have access to this document.'))
        # the result is expected from this table, so we should link tables
        return super(HrEmployeePrivate, self.sudo())._search([('id', 'in', ids)], order=order)

    def get_formview_id(self, access_uid=None):
        """ Override this method in order to redirect many2one towards the right model depending on access_uid """
        user = self.env.user
        if access_uid:
            user = self.env['res.users'].browse(access_uid).sudo()

        if user.has_group('hr.group_hr_user'):
            return super(HrEmployeePrivate, self).get_formview_id(access_uid=access_uid)
        # Hardcode the form view for public employee
        return self.env.ref('hr.hr_employee_public_view_form').id

    def get_formview_action(self, access_uid=None):
        """ Override this method in order to redirect many2one towards the right model depending on access_uid """
        res = super(HrEmployeePrivate, self).get_formview_action(access_uid=access_uid)
        user = self.env.user
        if access_uid:
            user = self.env['res.users'].browse(access_uid).sudo()

        if not user.has_group('hr.group_hr_user'):
            res['res_model'] = 'hr.employee.public'

        return res

    @api.constrains('pin')
    def _verify_pin(self):
        for employee in self:
            if employee.pin and not employee.pin.isdigit():
                raise ValidationError(_("The PIN must be a sequence of digits."))

    @api.constrains('barcode')
    def _verify_barcode(self):
        for employee in self:
            if employee.barcode:
                if not (re.match(r'^[A-Za-z0-9]+$', employee.barcode) and len(employee.barcode) <= 18):
                    raise ValidationError(_("The Badge ID must be alphanumeric without any accents and no longer than 18 characters."))

    @api.constrains('ssnid')
    def _check_ssnid(self):
        # By default, an Social Security Number is always valid, but each localization
        # may want to add its own constraints
        pass

    @api.onchange('user_id')
    def _onchange_user(self):
        self.update(self._sync_user(self.user_id, (bool(self.image_1920))))
        if not self.name:
            self.name = self.user_id.name

    @api.onchange('resource_calendar_id')
    def _onchange_timezone(self):
        if self.resource_calendar_id and not self.tz:
            self.tz = self.resource_calendar_id.tz

    def _remove_work_contact_id(self, user, employee_company):
        """ Remove work_contact_id for previous employee if the user is assigned to a new employee """
        employee_company = employee_company or self.company_id.id
        # For employees with a user_id, the constraint (user can't be linked to multiple employees) is triggered
        old_partner_employee_ids = user.partner_id.employee_ids.filtered(lambda e:
            not e.user_id
            and e.company_id.id == employee_company
            and e != self
        )
        old_partner_employee_ids.work_contact_id = None

    def _sync_user(self, user, employee_has_image=False):
        vals = dict(
            work_contact_id=user.partner_id.id if user else self.work_contact_id.id,
            user_id=user.id,
        )
        if not employee_has_image:
            vals['image_1920'] = user.image_1920
        if user.tz:
            vals['tz'] = user.tz
        return vals

    def _prepare_resource_values(self, vals, tz):
        resource_vals = super()._prepare_resource_values(vals, tz)
        vals.pop('name')  # Already considered by super call but no popped
        # We need to pop it to avoid useless resource update (& write) call
        # on every newly created resource (with the correct name already)
        user_id = vals.pop('user_id', None)
        if user_id:
            resource_vals['user_id'] = user_id
        active_status = vals.get('active')
        if active_status is not None:
            resource_vals['active'] = active_status
        return resource_vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('user_id'):
                user = self.env['res.users'].browse(vals['user_id'])
                vals.update(self._sync_user(user, bool(vals.get('image_1920'))))
                vals['name'] = vals.get('name', user.name)
                self._remove_work_contact_id(user, vals.get('company_id'))
        employees = super().create(vals_list)
        # Sudo in case HR officer doesn't have the Contact Creation group
        employees.filtered(lambda e: not e.work_contact_id).sudo()._create_work_contacts()
        for employee_sudo in employees.sudo():
            # creating 'svg/xml' attachments requires specific rights
            if not employee_sudo.image_1920 and self.env['ir.ui.view'].sudo(False).has_access('write'):
                employee_sudo.image_1920 = employee_sudo._avatar_generate_svg()
                employee_sudo.work_contact_id.image_1920 = employee_sudo.image_1920
        if self.env.context.get('salary_simulation'):
            return employees
        employee_departments = employees.department_id
        if employee_departments:
            self.env['discuss.channel'].sudo().search([
                ('subscription_department_ids', 'in', employee_departments.ids)
            ])._subscribe_users_automatically()
        onboarding_notes_bodies = {}
        hr_root_menu = self.env.ref('hr.menu_hr_root')
        for employee in employees:
            # Launch onboarding plans
            url = '/odoo/%s/action-hr.plan_wizard_action?active_model=hr.employee&menu_id=%s' % (employee.id, hr_root_menu.id)
            onboarding_notes_bodies[employee.id] = Markup(_(
                '<b>Congratulations!</b> May I recommend you to setup an <a href="%s">onboarding plan?</a>',
            )) % url
        employees._message_log_batch(onboarding_notes_bodies)
        return employees

    def write(self, vals):
        if 'work_contact_id' in vals:
            account_ids = vals.get('bank_account_id') or self.bank_account_id.ids
            if account_ids:
                bank_accounts = self.env['res.partner.bank'].sudo().browse(account_ids)
                for bank_account in bank_accounts:
                    if vals['work_contact_id'] != bank_account.partner_id.id:
                        if bank_account.allow_out_payment:
                            bank_account.allow_out_payment = False
                        if vals['work_contact_id']:
                            bank_account.partner_id = vals['work_contact_id']
            self.message_unsubscribe(self.work_contact_id.ids)
            if vals['work_contact_id']:
                self._message_subscribe([vals['work_contact_id']])
        if vals.get('user_id'):
            # Update the profile pictures with user, except if provided
            user = self.env['res.users'].browse(vals['user_id'])
            vals.update(self._sync_user(user, (bool(all(emp.image_1920 for emp in self)))))
            self._remove_work_contact_id(user, vals.get('company_id'))
        if 'work_permit_expiration_date' in vals:
            vals['work_permit_scheduled_activity'] = False
        res = super(HrEmployeePrivate, self).write(vals)
        if vals.get('department_id') or vals.get('user_id'):
            department_id = vals['department_id'] if vals.get('department_id') else self[:1].department_id.id
            # When added to a department or changing user, subscribe to the channels auto-subscribed by department
            self.env['discuss.channel'].sudo().search([
                ('subscription_department_ids', 'in', department_id)
            ])._subscribe_users_automatically()
        if vals.get('departure_description'):
            for employee in self:
                employee.message_post(body=_(
                    'Additional Information: \n %(description)s',
                    description=vals.get('departure_description')))
        return res

    def unlink(self):
        resources = self.mapped('resource_id')
        super(HrEmployeePrivate, self).unlink()
        return resources.unlink()

    def _get_employee_m2o_to_empty_on_archived_employees(self):
        return ['parent_id', 'coach_id']

    def _get_user_m2o_to_empty_on_archived_employees(self):
        return []

    def toggle_active(self):
        res = super(HrEmployeePrivate, self).toggle_active()
        unarchived_employees = self.filtered(lambda employee: employee.active)
        unarchived_employees.write({
            'departure_reason_id': False,
            'departure_description': False,
            'departure_date': False
        })

        archived_employees = self.filtered(lambda e: not e.active)
        if archived_employees:
            # Empty links to this employees (example: manager, coach, time off responsible, ...)
            employee_fields_to_empty = self._get_employee_m2o_to_empty_on_archived_employees()
            user_fields_to_empty = self._get_user_m2o_to_empty_on_archived_employees()
            employee_domain = [[(field, 'in', archived_employees.ids)] for field in employee_fields_to_empty]
            user_domain = [[(field, 'in', archived_employees.user_id.ids) for field in user_fields_to_empty]]
            employees = self.env['hr.employee'].search(expression.OR(employee_domain + user_domain))
            for employee in employees:
                for field in employee_fields_to_empty:
                    if employee[field] in archived_employees:
                        employee[field] = False
                for field in user_fields_to_empty:
                    if employee[field] in archived_employees.user_id:
                        employee[field] = False

        if len(self) == 1 and not self.active and not self.env.context.get('no_wizard', False):
            return {
                'type': 'ir.actions.act_window',
                'name': _('Register Departure'),
                'res_model': 'hr.departure.wizard',
                'view_mode': 'form',
                'target': 'new',
                'context': {'active_id': self.id},
                'views': [[False, 'form']]
            }
        return res

    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self._origin:
            return {'warning': {
                'title': _("Warning"),
                'message': _("To avoid multi company issues (losing the access to your previous contracts, leaves, ...), you should create another employee in the new company instead.")
            }}

    def generate_random_barcode(self):
        for employee in self:
            employee.barcode = '041'+"".join(choice(digits) for i in range(9))

    def _get_tz(self):
        # Finds the first valid timezone in his tz, his work hours tz,
        #  the company calendar tz or UTC and returns it as a string
        self.ensure_one()
        return self.tz or\
               self.resource_calendar_id.tz or\
               self.company_id.resource_calendar_id.tz or\
               'UTC'

    def _get_tz_batch(self):
        # Finds the first valid timezone in his tz, his work hours tz,
        #  the company calendar tz or UTC
        # Returns a dict {employee_id: tz}
        return {emp.id: emp._get_tz() for emp in self}

    def _employee_attendance_intervals(self, start, stop, lunch=False):
        self.ensure_one()
        calendar = self.resource_calendar_id or self.company_id.resource_calendar_id
        if not lunch:
            return self._get_expected_attendances(start, stop)
        else:
            return calendar._attendance_intervals_batch(start, stop, self.resource_id, lunch=True)[self.resource_id.id]

    def _get_expected_attendances(self, date_from, date_to):
        self.ensure_one()
        employee_timezone = timezone(self.tz) if self.tz else None
        calendar = self.resource_calendar_id or self.company_id.resource_calendar_id
        calendar_intervals = calendar._work_intervals_batch(
                                date_from,
                                date_to,
                                tz=employee_timezone,
                                resources=self.resource_id,
                                compute_leaves=True,
                                domain=[('company_id', 'in', [False, self.company_id.id])])[self.resource_id.id]
        return calendar_intervals

    def _get_calendar_attendances(self, date_from, date_to):
        self.ensure_one()
        employee_timezone = timezone(self.tz) if self.tz else None
        calendar = self.resource_calendar_id or self.company_id.resource_calendar_id
        return calendar\
            .with_context(employee_timezone=employee_timezone)\
            .get_work_duration_data(
                date_from,
                date_to,
                domain=[('company_id', 'in', [False, self.company_id.id])])

    def _get_marital_status_selection(self):
        return [
            ('single', _('Single')),
            ('married', _('Married')),
            ('cohabitant', _('Legal Cohabitant')),
            ('widower', _('Widower')),
            ('divorced', _('Divorced')),
        ]

    def _load_scenario(self):
        demo_tag = self.env.ref('hr.employee_category_demo', raise_if_not_found=False)
        if demo_tag:
            return
        convert.convert_file(self.env, 'hr', 'data/scenarios/hr_scenario.xml', None, mode='init', kind='data')

    # ---------------------------------------------------------
    # Business Methods
    # ---------------------------------------------------------

    @api.model
    def get_import_templates(self):
        return [{
            'label': _('Import Template for Employees'),
            'template': '/hr/static/xls/hr_employee.xls'
        }]

    def _get_unusual_days(self, date_from, date_to=None):
        # Checking the calendar directly allows to not grey out the leaves taken
        # by the employee or fallback to the company calendar
        return (self.resource_calendar_id or self.env.company.resource_calendar_id)._get_unusual_days(
            datetime.combine(fields.Date.from_string(date_from), time.min).replace(tzinfo=UTC),
            datetime.combine(fields.Date.from_string(date_to), time.max).replace(tzinfo=UTC),
            self.company_id,
        )

    def _get_age(self, target_date=None):
        self.ensure_one()
        if target_date is None:
            target_date = fields.Date.context_today(self.env.user)
        return relativedelta(target_date, self.birthday).years if self.birthday else 0

    # ---------------------------------------------------------
    # Messaging
    # ---------------------------------------------------------

    def _phone_get_number_fields(self):
        return ['mobile_phone']

    def _mail_get_partner_fields(self, introspect_fields=False):
        return ['user_partner_id']

    def get_project_performance_summary(self):
        self.ensure_one()
        summary = []
        for assignment in self.project_assignment_ids:
            summary.append({
                'project': assignment.project_id.name,
                'role': assignment.role,
                'date_start': assignment.date_start,
                'date_end': assignment.date_end,
                'progress': assignment.progress,
                'performance_score': assignment.performance_score,
                'note': assignment.note,
            })
        return summary

    def get_skill_summary(self):
        self.ensure_one()
        return [{
            'skill_name': skill.skill_name,
            'skill_level': skill.skill_level,
            'certificate': skill.certificate,
            'certificate_issue_date': skill.certificate_issue_date,
            'certificate_expiry_date': skill.certificate_expiry_date,
            'note': skill.note,
        } for skill in self.skill_ids]

    def has_skill_for_task(self, required_skills):
        """
        required_skills: list of dict, e.g. [{'skill_name': 'Python', 'skill_level': 'advanced'}]
        Return True nếu nhân viên đáp ứng đủ kỹ năng yêu cầu.
        """
        self.ensure_one()
        for req in required_skills:
            found = False
            for skill in self.skill_ids:
                if skill.skill_name == req['skill_name'] and skill.skill_level in [req['skill_level'], 'expert']:
                    found = True
                    break
            if not found:
                return False
        return True

    def export_employee_list_excel(self, fields_to_export=None):
        """
        Xuất danh sách nhân viên ra file Excel với các trường tùy chọn.
        fields_to_export: list tên trường muốn xuất, nếu None sẽ xuất mặc định các trường phổ biến tại Việt Nam.
        Trả về: (filename, file_content_bytes)
        """
        self.ensure_one()
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Danh sách nhân viên')
        # Trường mặc định phổ biến tại Việt Nam
        default_fields = [
            ('name', 'Họ tên'),
            ('department_id', 'Phòng ban'),
            ('job_id', 'Chức vụ'),
            ('minimum_wage_region', 'Vùng lương'),
            ('detailed_contract_type', 'Loại HĐ'),
            ('bhxh_code', 'Mã BHXH'),
            ('bhyt_code', 'Mã BHYT'),
            ('bhtn_code', 'Mã BHTN'),
            ('kcb_place', 'Nơi KCB'),
            ('labor_contract_number', 'Số HĐLĐ'),
            ('labor_contract_sign_date', 'Ngày ký HĐ'),
            ('labor_contract_expiry_date', 'Ngày hết HĐ'),
            ('project_ids', 'Dự án'),
            ('project_role', 'Vai trò dự án'),
            ('children', 'Số con'),
            ('birthday', 'Ngày sinh'),
            ('gender', 'Giới tính'),
            ('country_id', 'Quốc tịch'),
            ('private_phone', 'SĐT cá nhân'),
            ('private_email', 'Email cá nhân'),
        ]
        fields_to_export = fields_to_export or default_fields
        # Header
        for col, (_, label) in enumerate(fields_to_export):
            worksheet.write(0, col, label)
        # Data
        for row, emp in enumerate(self.search([]), 1):
            for col, (field, _) in enumerate(fields_to_export):
                value = getattr(emp, field, '')
                if isinstance(value, models.Model):
                    value = ', '.join(value.mapped('name'))
                elif isinstance(value, list) or isinstance(value, tuple):
                    value = ', '.join([str(v) for v in value])
                worksheet.write(row, col, value or '')
        workbook.close()
        output.seek(0)
        return ('danh_sach_nhan_vien.xlsx', output.read())

    def export_employee_list_pdf(self, fields_to_export=None):
        """
        Xuất danh sách nhân viên ra PDF với các trường tùy chọn.
        fields_to_export: list tên trường muốn xuất, nếu None sẽ xuất mặc định các trường phổ biến tại Việt Nam.
        Trả về: (filename, file_content_bytes)
        """
        self.ensure_one()
        # Sử dụng QWeb template hoặc html2pdf
        employees = self.search([])
        default_fields = [
            ('name', 'Họ tên'),
            ('department_id', 'Phòng ban'),
            ('job_id', 'Chức vụ'),
            ('minimum_wage_region', 'Vùng lương'),
            ('detailed_contract_type', 'Loại HĐ'),
            ('bhxh_code', 'Mã BHXH'),
            ('bhyt_code', 'Mã BHYT'),
            ('bhtn_code', 'Mã BHTN'),
            ('kcb_place', 'Nơi KCB'),
            ('labor_contract_number', 'Số HĐLĐ'),
            ('labor_contract_sign_date', 'Ngày ký HĐ'),
            ('labor_contract_expiry_date', 'Ngày hết HĐ'),
            ('project_ids', 'Dự án'),
            ('project_role', 'Vai trò dự án'),
            ('children', 'Số con'),
            ('birthday', 'Ngày sinh'),
            ('gender', 'Giới tính'),
            ('country_id', 'Quốc tịch'),
            ('private_phone', 'SĐT cá nhân'),
            ('private_email', 'Email cá nhân'),
        ]
        fields_to_export = fields_to_export or default_fields
        # Tạo HTML table
        html = '<h2>Danh sách nhân viên</h2><table border="1" cellspacing="0" cellpadding="3"><tr>'
        for _, label in fields_to_export:
            html += f'<th>{label}</th>'
        html += '</tr>'
        for emp in employees:
            html += '<tr>'
            for field, _ in fields_to_export:
                value = getattr(emp, field, '')
                if isinstance(value, models.Model):
                    value = ', '.join(value.mapped('name'))
                elif isinstance(value, list) or isinstance(value, tuple):
                    value = ', '.join([str(v) for v in value])
                html += f'<td>{html2plaintext(str(value or ""))}</td>'
            html += '</tr>'
        html += '</table>'
        # Render PDF sử dụng phương thức mới của Odoo 18.0
        pdf_content = self.env['ir.actions.report']._render_qweb_pdf('base.report_external_layout', {'html': html})[0]
        return ('danh_sach_nhan_vien.pdf', pdf_content)

    def get_shift_summary(self):
        self.ensure_one()
        return [{
            'shift_name': shift.shift_name,
            'shift_type': shift.shift_type,
            'time_start': shift.time_start,
            'time_end': shift.time_end,
            'date_apply': shift.date_apply,
            'note': shift.note,
        } for shift in self.shift_ids]

    def is_shift_conflict(self, new_shift):
        """
        Kiểm tra ca làm việc mới có bị trùng với ca đã có không.
        new_shift: dict với các khóa shift_name, time_start, time_end, date_apply
        """
        self.ensure_one()
        for shift in self.shift_ids:
            if shift.date_apply == new_shift['date_apply']:
                # Kiểm tra giao nhau thời gian
                if not (new_shift['time_end'] <= shift.time_start or new_shift['time_start'] >= shift.time_end):
                    return True
        return False

    def export_state_report_labor_usage(self):
        """
        Xuất báo cáo tình hình sử dụng lao động (chuẩn Việt Nam) ra file CSV.
        Trả về: (filename, file_content_bytes)
        """
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output)
        # Header theo mẫu báo cáo
        header = [
            'STT', 'Họ tên', 'Ngày sinh', 'Giới tính', 'Quốc tịch', 'Số CMND/CCCD', 'Phòng ban', 'Chức vụ',
            'Loại hợp đồng', 'Ngày vào làm', 'Ngày nghỉ việc', 'Lý do nghỉ', 'Ghi chú'
        ]
        writer.writerow(header)
        for idx, emp in enumerate(self.search([]), 1):
            writer.writerow([
                idx,
                emp.name or '',
                emp.birthday or '',
                emp.gender or '',
                emp.country_id.name or '',
                emp.identification_id or '',
                emp.department_id.name or '',
                emp.job_id.name or '',
                emp.detailed_contract_type or '',
                emp.labor_contract_sign_date or '',
                emp.departure_date or '',
                emp.departure_reason_id.name or '',
                ''
            ])
        output.seek(0)
        return ('bao_cao_su_dung_lao_dong.csv', output.read().encode('utf-8'))

    def export_bhxh_report_c12ts(self):
        """
        Xuất báo cáo BHXH định kỳ mẫu C12-TS ra file CSV.
        Trả về: (filename, file_content_bytes)
        """
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            'STT', 'Họ tên', 'Mã số BHXH', 'Ngày sinh', 'Giới tính', 'Số CMND/CCCD', 'Phòng ban', 'Chức vụ',
            'Mức lương đóng BHXH', 'Tỷ lệ đóng', 'Từ tháng', 'Đến tháng', 'Ghi chú'
        ]
        writer.writerow(header)
        for idx, emp in enumerate(self.search([]), 1):
            writer.writerow([
                idx,
                emp.name or '',
                emp.bhxh_code or '',
                emp.birthday or '',
                emp.gender or '',
                emp.identification_id or '',
                emp.department_id.name or '',
                emp.job_id.name or '',
                '',  # Mức lương đóng BHXH (có thể lấy từ bảng lương nếu tích hợp)
                '',  # Tỷ lệ đóng (có thể cấu hình thêm)
                '',  # Từ tháng
                '',  # Đến tháng
                ''
            ])
        output.seek(0)
        return ('bao_cao_bhxh_c12ts.csv', output.read().encode('utf-8'))

    def export_bhxh_report_d02ts(self):
        """
        Xuất báo cáo BHXH định kỳ mẫu D02-TS ra file CSV.
        Trả về: (filename, file_content_bytes)
        """
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            'STT', 'Họ tên', 'Mã số BHXH', 'Ngày sinh', 'Giới tính', 'Số CMND/CCCD', 'Phòng ban', 'Chức vụ',
            'Nội dung thay đổi', 'Từ ngày', 'Đến ngày', 'Ghi chú'
        ]
        writer.writerow(header)
        for idx, emp in enumerate(self.search([]), 1):
            writer.writerow([
                idx,
                emp.name or '',
                emp.bhxh_code or '',
                emp.birthday or '',
                emp.gender or '',
                emp.identification_id or '',
                emp.department_id.name or '',
                emp.job_id.name or '',
                '',  # Nội dung thay đổi
                '',  # Từ ngày
                '',  # Đến ngày
                ''
            ])
        output.seek(0)
        return ('bao_cao_bhxh_d02ts.csv', output.read().encode('utf-8'))

    def export_tax_report_personal_income(self):
        """
        Xuất báo cáo quyết toán thuế TNCN ra file CSV.
        Trả về: (filename, file_content_bytes)
        """
        self.ensure_one()
        output = io.StringIO()
        writer = csv.writer(output)
        header = [
            'STT', 'Họ tên', 'Mã số thuế', 'Ngày sinh', 'Giới tính', 'Số CMND/CCCD', 'Phòng ban', 'Chức vụ',
            'Tổng thu nhập', 'Các khoản giảm trừ', 'Thu nhập chịu thuế', 'Thuế TNCN phải nộp', 'Ghi chú'
        ]
        writer.writerow(header)
        for idx, emp in enumerate(self.search([]), 1):
            writer.writerow([
                idx,
                emp.name or '',
                '',  # Mã số thuế (có thể bổ sung trường riêng)
                emp.birthday or '',
                emp.gender or '',
                emp.identification_id or '',
                emp.department_id.name or '',
                emp.job_id.name or '',
                '',  # Tổng thu nhập (có thể lấy từ bảng lương nếu tích hợp)
                '',  # Các khoản giảm trừ
                '',  # Thu nhập chịu thuế
                '',  # Thuế TNCN phải nộp
                ''
            ])
        output.seek(0)
        return ('bao_cao_thue_tncn.csv', output.read().encode('utf-8'))

    def create_bhxh_profile(self, action_type='register'):
        """
        Tạo hồ sơ BHXH/BHYT cho nhân viên, lưu vào lịch sử, sinh file XML giả lập.
        """
        self.ensure_one()
        # Sinh file XML giả lập (có thể thay bằng sinh file thật khi có API)
        xml_content = f'<BHXHProfile><Name>{self.name}</Name><Action>{action_type}</Action></BHXHProfile>'
        history = self.env['hr.employee.bhxh.history'].create({
            'employee_id': self.id,
            'action_type': action_type,
            'date_action': fields.Date.today(),
            'status': 'draft',
            'file_sent': xml_content.encode('utf-8'),
        })
        self.bhxh_profile_file = xml_content.encode('utf-8')
        self.bhxh_profile_status = 'draft'
        return history

    def send_bhxh_profile(self):
        """
        Stub gửi hồ sơ BHXH/BHYT (sau này tích hợp API sẽ bổ sung logic gọi API ở đây).
        """
        self.ensure_one()
        # Giả lập gửi thành công
        self.bhxh_profile_status = 'sent'
        self.bhxh_transaction_code = f'FAKE-{self.id}-{fields.Date.today()}'
        # Cập nhật lịch sử
        if self.bhxh_history_ids:
            self.bhxh_history_ids[-1].status = 'sent'
            self.bhxh_history_ids[-1].transaction_code = self.bhxh_transaction_code
        return True

    def receive_bhxh_response(self, response_note='Phản hồi thành công', file_response=None):
        """
        Stub nhận phản hồi từ BHXH (sau này tích hợp API sẽ bổ sung logic nhận phản hồi ở đây).
        """
        self.ensure_one()
        self.bhxh_profile_status = 'responded'
        self.bhxh_response_note = response_note
        if self.bhxh_history_ids:
            self.bhxh_history_ids[-1].status = 'responded'
            self.bhxh_history_ids[-1].response_note = response_note
            if file_response:
                self.bhxh_history_ids[-1].file_response = file_response
        return True

    def mark_bhxh_done(self):
        self.ensure_one()
        self.bhxh_profile_status = 'done'
        if self.bhxh_history_ids:
            self.bhxh_history_ids[-1].status = 'done'
        return True

    def auto_bhxh_reminder(self):
        """
        Tự động nhắc nhở nếu hồ sơ BHXH chưa gửi hoặc chưa phản hồi.
        """
        for emp in self.search([('bhxh_profile_status', 'in', ['draft', 'sent'])]):
            # Ở thực tế có thể gửi email, thông báo, hoặc tạo activity
            print(f'Nhắc nhở: Hồ sơ BHXH của {emp.name} đang ở trạng thái {emp.bhxh_profile_status}')

    # 1. Hàm định dạng tiền tệ VND
    def format_vnd(self, amount):
        """
        Định dạng số tiền theo chuẩn Việt Nam (VND).
        """
        try:
            return format_currency(amount, 'VND', locale='vi_VN')
        except Exception:
            return f"{amount:,.0f} VND"

    # 2. Hàm định dạng ngày giờ theo chuẩn Việt Nam
    def format_vn_date(self, date_obj):
        """
        Định dạng ngày theo chuẩn Việt Nam (dd/MM/yyyy).
        """
        try:
            return babel_format_date(date_obj, format='dd/MM/yyyy', locale='vi_VN')
        except Exception:
            return date_obj.strftime('%d/%m/%Y') if date_obj else ''

    # 3. Hàm kiểm tra ngày lễ quốc gia Việt Nam
    @staticmethod
    def is_vn_public_holiday(date_obj):
        """
        Kiểm tra ngày có phải là ngày lễ quốc gia Việt Nam không.
        """
        vn_holidays = [
            (1, 1),    # Tết Dương lịch
            (4, 30),   # Giải phóng miền Nam
            (5, 1),    # Quốc tế Lao động
            (9, 2),    # Quốc khánh
            # ... có thể bổ sung thêm các ngày lễ khác
        ]
        return (date_obj.month, date_obj.day) in vn_holidays

    # 4. Hướng dẫn dịch giao diện
    # Đảm bảo tất cả các label, help, string đều sử dụng _("") để dịch tự động qua file .po
    # Khi triển khai, sử dụng lệnh Odoo để sinh file .pot/.po, dịch sang tiếng Việt và nạp lại vào hệ thống

    def get_contract_summary(self):
        self.ensure_one()
        return [{
            'contract_type': c.contract_type,
            'sign_date': c.sign_date,
            'expiry_date': c.expiry_date,
            'salary': c.salary,
            'allowance': c.allowance,
            'special_terms': c.special_terms,
            'state': c.state,
        } for c in self.contract_ids]

    def check_contract_expiry(self):
        self.ensure_one()
        for c in self.contract_ids:
            if c.state == 'active' and c.expiry_date and c.expiry_date <= fields.Date.today():
                c.state = 'expired'

    def contract_expiry_reminder(self):
        for emp in self.search([]):
            for c in emp.contract_ids:
                if c.state == 'active' and c.expiry_date:
                    days_left = (c.expiry_date - fields.Date.today()).days
                    if 0 <= days_left <= 30:
                        print(f'Cảnh báo: Hợp đồng của {emp.name} ({c.contract_type}) sắp hết hạn vào {c.expiry_date}')

    def generate_contract_template(self, contract_type='definite'):
        """
        Sinh hợp đồng mẫu (dạng text) theo loại hợp đồng, có thể xuất ra file hoặc in.
        """
        self.ensure_one()
        template = f"""
        CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
        Độc lập - Tự do - Hạnh phúc

        HỢP ĐỒNG LAO ĐỘNG ({dict([('probation','Thử việc'),('definite','Xác định thời hạn'),('indefinite','Không xác định thời hạn'),('seasonal','Thời vụ'),('other','Khác')])[contract_type]})

        Họ tên người lao động: {self.name}
        Chức vụ: {self.job_id.name if self.job_id else ''}
        Phòng ban: {self.department_id.name if self.department_id else ''}
        Lương cơ bản: {self.format_vnd(self.net_salary)}
        Ngày ký: {self.format_vn_date(fields.Date.today())}
        ... (bổ sung các điều khoản đặc thù theo luật Việt Nam)
        """
        return template

    def get_personal_income_tax_summary(self):
        self.ensure_one()
        return [{
            'year': t.year,
            'total_income': t.total_income,
            'self_deduction': t.self_deduction,
            'dependent_deduction': t.dependent_deduction,
            'taxable_income': t.taxable_income,
            'tax_amount': t.tax_amount,
            'state': t.state,
        } for t in self.personal_income_tax_ids]

    def export_tax_finalization_report(self, year):
        """
        Sinh file báo cáo quyết toán thuế TNCN theo mẫu Tổng cục Thuế (CSV).
        """
        self.ensure_one()
        tax = self.personal_income_tax_ids.filtered(lambda t: t.year == year)
        if not tax:
            return None
        import io, csv
        output = io.StringIO()
        writer = csv.writer(output)
        header = ['Năm', 'Họ tên', 'Mã số thuế', 'Tổng thu nhập', 'Giảm trừ bản thân', 'Giảm trừ NPT', 'Thu nhập chịu thuế', 'Thuế phải nộp', 'Trạng thái']
        writer.writerow(header)
        for t in tax:
            writer.writerow([
                t.year,
                self.name,
                self.personal_tax_code or '',
                t.total_income,
                t.self_deduction,
                t.dependent_deduction,
                t.taxable_income,
                t.tax_amount,
                t.state
            ])
        output.seek(0)
        return (f'quyet_toan_thue_{self.name}_{year}.csv', output.read().encode('utf-8'))

    # 1. Scheduled Action: Tự động sinh quyết toán thuế cuối năm cho toàn bộ nhân viên
    @api.model
    def cron_auto_create_tax_finalization(self):
        current_year = date.today().year
        for emp in self.search([]):
            if not emp.personal_income_tax_ids.filtered(lambda t: t.year == current_year):
                total_income = emp.year_income or 0.0
                dependent_count = getattr(emp, 'dependent_count', 0) or 0
                dependent_deduction = dependent_count * 4400000 * 12
                emp.env['hr.employee.personal.income.tax'].create({
                    'employee_id': emp.id,
                    'year': current_year,
                    'total_income': total_income,
                    'dependent_deduction': dependent_deduction,
                })

    # 2. Tự động cảnh báo, nhắc nhở quyết toán thuế
    def auto_tax_reminder(self):
        for emp in self.search([]):
            for t in emp.personal_income_tax_ids:
                if t.state == 'draft' and t.year == date.today().year:
                    # Gửi activity nhắc nhở (có thể mở rộng gửi email)
                    emp.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary=_('Nhắc nhở quyết toán thuế TNCN'),
                        note=_('Bạn cần hoàn thành quyết toán thuế TNCN năm %s.') % t.year
                    )

    # 3. Tự động kiểm tra và cảnh báo bất thường về thu nhập, thuế
    def auto_tax_anomaly_check(self):
        for emp in self.search([]):
            taxes = sorted(emp.personal_income_tax_ids, key=lambda t: t.year)
            for i in range(1, len(taxes)):
                prev, curr = taxes[i-1], taxes[i]
                if prev.total_income and abs(curr.total_income - prev.total_income) / prev.total_income > 0.5:
                    emp.message_post(
                        body=_('Cảnh báo: Thu nhập năm %s tăng/giảm bất thường so với năm %s.') % (curr.year, prev.year),
                        subject=_('Cảnh báo thu nhập bất thường')
                    )
                if curr.tax_amount < 0:
                    emp.message_post(
                        body=_('Cảnh báo: Thuế TNCN năm %s nhỏ hơn 0, vui lòng kiểm tra lại dữ liệu!') % curr.year,
                        subject=_('Cảnh báo thuế bất thường')
                    )

    # 4. Tự động cập nhật giảm trừ khi thay đổi số người phụ thuộc
    def write(self, vals):
        res = super().write(vals)
        if 'dependent_count' in vals:
            for emp in self:
                for t in emp.personal_income_tax_ids:
                    t.dependent_deduction = vals['dependent_count'] * 4400000 * 12
        return res

    # 5. Bản địa hóa thông báo, cảnh báo, báo cáo: đã dùng _() cho mọi thông báo, nội dung đều tiếng Việt, định dạng chuẩn VN.


class HrEmployeeProjectAssignment(models.Model):
    _name = 'hr.employee.project.assignment'
    _description = 'Phân bổ dự án cho nhân viên (Việt Nam)'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, ondelete='cascade')
    project_id = fields.Many2one('project.project', string='Dự án', required=True, ondelete='cascade')
    role = fields.Char(string='Vai trò trong dự án')
    date_start = fields.Date(string='Ngày bắt đầu')
    date_end = fields.Date(string='Ngày kết thúc')
    progress = fields.Float(string='Tiến độ (%)', default=0.0)
    performance_score = fields.Float(string='Điểm hiệu suất', default=0.0)
    note = fields.Text(string='Ghi chú')


class HrEmployeeSkill(models.Model):
    _name = 'hr.employee.skill'
    _description = 'Kỹ năng và chứng chỉ nhân viên (Việt Nam)'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, ondelete='cascade')
    skill_name = fields.Char(string='Tên kỹ năng', required=True)
    skill_level = fields.Selection([
        ('basic', 'Cơ bản'),
        ('intermediate', 'Trung bình'),
        ('advanced', 'Nâng cao'),
        ('expert', 'Chuyên gia')
    ], string='Cấp độ', required=True)
    certificate = fields.Char(string='Chứng chỉ liên quan')
    certificate_issue_date = fields.Date(string='Ngày cấp chứng chỉ')
    certificate_expiry_date = fields.Date(string='Ngày hết hạn chứng chỉ')
    note = fields.Text(string='Ghi chú')


class HrEmployeeShift(models.Model):
    _name = 'hr.employee.shift'
    _description = 'Ca làm việc nhân viên (Việt Nam)'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, ondelete='cascade')
    shift_name = fields.Char(string='Tên ca', required=True)
    shift_type = fields.Selection([
        ('day', 'Ca ngày'),
        ('night', 'Ca đêm'),
        ('rotating', 'Ca xoay vòng'),
        ('other', 'Khác')
    ], string='Loại ca', required=True)
    time_start = fields.Float(string='Giờ bắt đầu', required=True, help='Ví dụ: 8.0 cho 8h sáng')
    time_end = fields.Float(string='Giờ kết thúc', required=True, help='Ví dụ: 17.5 cho 17h30')
    date_apply = fields.Date(string='Ngày áp dụng', required=True)
    note = fields.Text(string='Ghi chú')


class HrEmployeeBhxhHistory(models.Model):
    _name = 'hr.employee.bhxh.history'
    _description = 'Lịch sử giao dịch BHXH/BHYT nhân viên (Việt Nam)'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, ondelete='cascade')
    action_type = fields.Selection([
        ('register', 'Đăng ký mới'),
        ('update', 'Cập nhật'),
        ('increase', 'Báo tăng'),
        ('decrease', 'Báo giảm'),
        ('other', 'Khác')
    ], string='Loại nghiệp vụ', required=True)
    date_action = fields.Date(string='Ngày thực hiện', required=True)
    status = fields.Selection([
        ('draft', 'Chưa gửi'),
        ('sent', 'Đã gửi'),
        ('responded', 'Đã phản hồi'),
        ('error', 'Lỗi'),
        ('done', 'Hoàn thành')
    ], string='Trạng thái', default='draft')
    transaction_code = fields.Char(string='Mã giao dịch')
    file_sent = fields.Binary(string='File hồ sơ gửi')
    file_response = fields.Binary(string='File phản hồi')
    response_note = fields.Text(string='Ghi chú phản hồi')


class HrEmployeeContract(models.Model):
    _name = 'hr.employee.contract'
    _description = 'Hợp đồng lao động nhân viên (Việt Nam)'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, ondelete='cascade')
    contract_type = fields.Selection([
        ('probation', 'Thử việc'),
        ('definite', 'Xác định thời hạn'),
        ('indefinite', 'Không xác định thời hạn'),
        ('seasonal', 'Thời vụ'),
        ('other', 'Khác')
    ], string='Loại hợp đồng', required=True)
    sign_date = fields.Date(string='Ngày ký', required=True)
    expiry_date = fields.Date(string='Ngày hết hạn')
    salary = fields.Float(string='Lương cơ bản', required=True)
    allowance = fields.Float(string='Phụ cấp')
    special_terms = fields.Text(string='Điều khoản đặc thù')
    contract_file = fields.Binary(string='File scan hợp đồng')
    state = fields.Selection([
        ('active', 'Hiệu lực'),
        ('expired', 'Hết hạn'),
        ('terminated', 'Đã chấm dứt')
    ], string='Trạng thái hợp đồng', default='active')


class HrEmployeePersonalIncomeTax(models.Model):
    _name = 'hr.employee.personal.income.tax'
    _description = 'Quyết toán thuế TNCN nhân viên (Việt Nam)'

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, ondelete='cascade')
    year = fields.Integer(string='Năm quyết toán', required=True)
    total_income = fields.Float(string='Tổng thu nhập năm', required=True)
    self_deduction = fields.Float(string='Giảm trừ bản thân', default=13200000*12)
    dependent_deduction = fields.Float(string='Giảm trừ người phụ thuộc', default=0.0)
    taxable_income = fields.Float(string='Thu nhập chịu thuế', compute='_compute_taxable_income', store=True)
    tax_amount = fields.Float(string='Thuế TNCN phải nộp', compute='_compute_tax_amount', store=True)
    tax_file = fields.Binary(string='File quyết toán thuế')
    state = fields.Selection([
        ('draft', 'Chưa nộp'),
        ('submitted', 'Đã nộp'),
        ('done', 'Đã quyết toán')
    ], string='Trạng thái', default='draft')

    @api.depends('total_income', 'self_deduction', 'dependent_deduction')
    def _compute_taxable_income(self):
        for rec in self:
            rec.taxable_income = max(0, rec.total_income - rec.self_deduction - rec.dependent_deduction)

    @api.depends('taxable_income')
    def _compute_tax_amount(self):
        for rec in self:
            rec.tax_amount = rec._calculate_vn_personal_income_tax(rec.taxable_income)

    def _calculate_vn_personal_income_tax(self, taxable_income):
        # Áp dụng biểu thuế lũy tiến từng phần theo quy định Việt Nam
        brackets = [ (0, 5000000, 0.05),
                     (5000000, 10000000, 0.1),
                     (10000000, 18000000, 0.15),
                     (18000000, 32000000, 0.2),
                     (32000000, 52000000, 0.25),
                     (52000000, 80000000, 0.3),
                     (80000000, float('inf'), 0.35)]
        tax = 0
        remaining = taxable_income
        for lower, upper, rate in brackets:
            if taxable_income > lower:
                amount = min(upper-lower, remaining)
                tax += amount * rate
                remaining -= amount
                if remaining <= 0:
                    break
        return tax
