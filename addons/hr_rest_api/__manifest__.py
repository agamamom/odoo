{
    'name': "HR REST API",
    'summary': "RESTful API for HR module including Payroll management",
    'description': """
        This module provides RESTful API endpoints for the HR module,
        allowing external applications to access HR data through standard HTTP requests.
        Includes payslip management, computation, validation, and reporting features.
    """,
    'version': '1.0',
    'category': 'Human Resources/API',
    'depends': [
        'hr', 
        'base',
        'hr_payroll_community',
        'hr_payroll_account_community',
        'hr_work_entry_holidays',
        'ohrms_loan',
        'ohrms_salary_advance',
        'ohrms_loan_accounting'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
} 