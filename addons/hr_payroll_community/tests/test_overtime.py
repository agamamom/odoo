# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
from odoo import fields

class TestHrOvertime(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, no_reset_password=True))
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
        })

    def test_create_overtime(self):
        overtime = self.env['hr.overtime'].create({
            'employee_id': self.employee.id,
            'date': fields.Date.today(),
            'hours': 2.0,
            'overtime_type': 'normal',
        })
        self.assertEqual(overtime.state, 'draft')
        self.assertEqual(overtime.wage_coefficient, 1.5)

    def test_submit_and_approve(self):
        overtime = self.env['hr.overtime'].create({
            'employee_id': self.employee.id,
            'date': fields.Date.today(),
            'hours': 3.0,
            'overtime_type': 'weekend',
        })
        overtime.action_submit()
        self.assertEqual(overtime.state, 'to_approve')
        overtime.action_approve()
        self.assertEqual(overtime.state, 'approved')
        self.assertTrue(overtime.approver_id)

    def test_refuse(self):
        overtime = self.env['hr.overtime'].create({
            'employee_id': self.employee.id,
            'date': fields.Date.today(),
            'hours': 1.0,
            'overtime_type': 'holiday',
        })
        overtime.action_submit()
        overtime.action_refuse()
        self.assertEqual(overtime.state, 'refused')

    def test_reset_draft(self):
        overtime = self.env['hr.overtime'].create({
            'employee_id': self.employee.id,
            'date': fields.Date.today(),
            'hours': 1.0,
            'overtime_type': 'night',
        })
        overtime.action_submit()
        overtime.action_reset_draft()
        self.assertEqual(overtime.state, 'draft')

    def test_invalid_submit(self):
        overtime = self.env['hr.overtime'].create({
            'employee_id': self.employee.id,
            'date': fields.Date.today(),
            'hours': 1.0,
            'overtime_type': 'normal',
        })
        overtime.action_submit()
        with self.assertRaises(Exception):
            overtime.action_submit() 