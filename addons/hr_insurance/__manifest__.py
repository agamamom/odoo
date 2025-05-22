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
{
    'name': 'Employee Insurance Management',
    'version': '18.0.1.0.0',
    'summary': 'Employee Insurance Management',
    'author': 'OHRMS',
    'company': 'OHRMS',
    'category': 'Generic Modules/Human Resources',
    'maintainer': 'OHRMS',
    'website': "",
    'depends': ['hr', 'mail', 'hr_payroll_community'],
    'data': [
        'security/ir.model.access.csv',
        'security/hr_insurance_security.xml',
        'data/insurance_policy_data.xml',
        'data/ir_cron_data.xml',
        'data/ir_sequence_data.xml',
        'views/hr_insurance_menus.xml',
        'views/social_insurance_document_views.xml',
        'views/hr_employee_views.xml',
        'views/employee_insurance_views.xml',
        'views/insurance_allowance_views.xml',
        'views/insurance_policy_views.xml',
        'views/insurance_report_views.xml',
        'views/social_insurance_history_views.xml',
        'views/social_insurance_benefit_views.xml',
        'views/social_insurance_late_fee_views.xml',
        'views/insurance_cost_report_views.xml',
        'views/insurance_document_template_views.xml',
        'views/clean_document_view.xml',
        'report/insurance_report_template.xml',
        'report/d02_ts_report_template.xml',
        'report/d03_ts_report_template.xml',
        'wizards/insurance_payment_wizards_views.xml',
        'wizards/social_insurance_code_wizard_views.xml',
        'wizards/social_insurance_print_wizard_views.xml',
        'wizards/insurance_document_create_wizard_views.xml',
    ],
    'demo': [],
    'images': ['static/description/banner.png'],
    'license': 'AGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
