# -*- coding: utf-8 -*-
{
    'name': 'Company Geolocation',
    'version': '18.0.1.0.0',
    'category': 'Tools',
    'summary': 'Add geolocation map to company form',
    'description': """
        This module adds a geolocation map to the company form view
        allowing users to select the company location on a map.
        It stores both the address and coordinates (latitude/longitude).
    """,
    'author': 'Your Company',
    'depends': ['base', 'geolocation_map_widget'],
    'data': [
        'views/res_company_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            ('after', 'geolocation_map_widget/static/src/js/geolocation_map.js', 'company_geolocation/static/src/js/company_geolocation.js'),
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
} 