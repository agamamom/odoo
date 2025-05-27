{
    'name': "HR REST API",
    'summary': "RESTful API for HR module including Payroll and Insurance management",
    'description': """
        This module provides RESTful API endpoints for the HR module,
        allowing external applications to access HR data through standard HTTP requests.
        Includes payslip management, computation, validation, insurance management, and reporting features.
        
        Employee self-service features:
        - View own payslips and download PDFs
        - View payslip details and computation
        - View salary structure
        - GDPR compliance features (data access, correction, portability)
    """,
    'version': '1.0',
    'category': 'Human Resources/API',
    'depends': [
        'hr', 
        'base',
        'hr_insurance',
        'hr_payroll_community',
        'hr_contract'
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/res_users_views.xml',
        'views/hr_gdpr_request_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
} 