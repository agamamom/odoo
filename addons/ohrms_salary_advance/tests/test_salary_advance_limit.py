from odoo.tests.common import TransactionCase
from datetime import date

class TestSalaryAdvanceLimit(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env.user.company_id
        self.department = self.env['hr.department'].create({'name': 'IT'})
        self.employee = self.env['hr.employee'].create({'name': 'Test Employee', 'department_id': self.department.id})
        self.contract = self.env['hr.contract'].create({
            'name': 'Test Contract',
            'employee_id': self.employee.id,
            'wage': 10000000,
            'struct_id': self.env['hr.payroll.structure'].create({
                'name': 'Test Structure',
                'max_percent': 10,
            }).id,
        })
        self.employee.contract_id = self.contract.id

    def test_limit_priority(self):
        # 1. Chỉ contract/structure
        adv = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 1000000,
        })
        self.assertEqual(adv._get_advance_limit(), 1000000)
        # 2. Theo công ty
        self.env['salary.advance.limit'].create({
            'name': 'Limit Company',
            'company_id': self.company.id,
            'amount': 2000000,
        })
        self.assertEqual(adv._get_advance_limit(), 2000000)
        # 3. Theo phòng ban
        self.env['salary.advance.limit'].create({
            'name': 'Limit Dept',
            'department_id': self.department.id,
            'amount': 3000000,
        })
        self.assertEqual(adv._get_advance_limit(), 3000000)
        # 4. Theo nhân viên
        self.env['salary.advance.limit'].create({
            'name': 'Limit Emp',
            'employee_id': self.employee.id,
            'amount': 4000000,
        })
        self.assertEqual(adv._get_advance_limit(), 4000000) 