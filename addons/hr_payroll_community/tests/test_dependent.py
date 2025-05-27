# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo import fields

class TestHrDependent(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, no_reset_password=True))
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
        })

    def test_create_dependent(self):
        dependent = self.env['hr.dependent'].create({
            'name': 'Child 1',
            'employee_id': self.employee.id,
            'relation': 'child',
            'birthday': fields.Date.today(),
            'id_number': '123456789',
            'start_date': fields.Date.today(),
        })
        self.assertEqual(dependent.state, 'active')

    def test_duplicate_dependent(self):
        vals = {
            'name': 'Child 1',
            'employee_id': self.employee.id,
            'relation': 'child',
            'birthday': fields.Date.today(),
            'id_number': '123456789',
            'start_date': fields.Date.today(),
        }
        self.env['hr.dependent'].create(vals)
        with self.assertRaises(Exception):
            self.env['hr.dependent'].create(vals) 