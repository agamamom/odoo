# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo import fields

class TestHrDynamicAllowance(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, no_reset_password=True))
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
        })
        self.contract = self.env['hr.contract'].create({
            'name': 'Test Contract',
            'employee_id': self.employee.id,
            'wage': 10000000,
            'date_start': fields.Date.today(),
        })

    def test_create_dynamic_allowance(self):
        allowance = self.env['hr.dynamic.allowance'].create({
            'name': 'Lunch',
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'allowance_type': 'lunch',
            'amount': 500000,
            'start_date': fields.Date.today(),
        })
        self.assertEqual(allowance.state, 'active')

    def test_duplicate_dynamic_allowance(self):
        vals = {
            'name': 'Lunch',
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'allowance_type': 'lunch',
            'amount': 500000,
            'start_date': fields.Date.today(),
        }
        self.env['hr.dynamic.allowance'].create(vals)
        with self.assertRaises(Exception):
            self.env['hr.dynamic.allowance'].create(vals) 