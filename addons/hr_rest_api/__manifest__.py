{
    'name': "HR REST API",
    'summary': "RESTful API for HR module including Payroll and Insurance management",
    'description': """
        This module provides RESTful API endpoints for the HR module,
        allowing external applications to access HR data through standard HTTP requests.
        Includes payslip management, computation, validation, insurance management, and reporting features.
    """,
    'version': '1.0',
    'category': 'Human Resources/API',
    'depends': [
        'hr', 
        'base',
        'hr_insurance'
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_users_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
} 