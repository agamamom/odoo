from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from datetime import date

class TestSalaryAdvanceMultiPerMonth(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, test_queue_job_no_delay=True))
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
        })
        self.contract = self.env['hr.contract'].create({
            'name': 'Test Contract',
            'employee_id': self.employee.id,
            'wage': 10000000,
            'struct_id': self.env['hr.payroll.structure'].create({
                'name': 'Test Structure',
                'max_percent': 20,
            }).id,
        })
        self.employee.contract_id = self.contract.id

    def test_multi_advance_per_month_and_limit(self):
        # 1. Tạo ứng lương lần 1
        adv1 = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 1000000,
        })
        adv1.approve_request()
        adv1.state = 'approve'
        # 2. Tạo ứng lương lần 2 trong cùng tháng, không vượt hạn mức
        adv2 = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 10),
            'advance': 500000,
        })
        adv2.approve_request()
        adv2.state = 'approve'
        # 3. Tạo ứng lương lần 3 vượt hạn mức (20% lương = 2tr)
        with self.assertRaises(UserError):
            adv3 = self.env['salary.advance'].create({
                'employee_id': self.employee.id,
                'date': date(2024, 6, 15),
                'advance': 700000,
            })
            adv3.approve_request()

    def test_auto_deduct_in_payslip(self):
        adv1 = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 1000000,
        })
        adv1.approve_request()
        adv1.state = 'approve'
        adv2 = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 10),
            'advance': 500000,
        })
        adv2.approve_request()
        adv2.state = 'approve'
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'date_from': date(2024, 6, 1),
            'date_to': date(2024, 6, 30),
        })
        inputs = payslip.get_inputs([self.contract], date(2024, 6, 1), date(2024, 6, 30))
        sar_input = next((i for i in inputs if i.get('code') == 'SAR'), None)
        self.assertIsNotNone(sar_input)
        self.assertEqual(sar_input['amount'], 1500000)
        adv1.refresh()
        adv2.refresh()
        self.assertTrue(adv1.is_deducted)
        self.assertTrue(adv2.is_deducted) 