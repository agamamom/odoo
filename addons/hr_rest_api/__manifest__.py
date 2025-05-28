# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'HR REST API',
    'version': '18.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'REST API for HR module',
    'description': """
HR REST API
==========

This module provides a RESTful API to access HR data.
Features include:
- User management API
- Employee management API
- Authentication with API keys
- CORS support for cross-origin requests
""",
    'depends': ['hr', 'hr_attendance', 'hr_holidays'],
    'data': [
        'security/ir.model.access.csv',
        'views/menus.xml',
    ],
    'demo': [
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
} 