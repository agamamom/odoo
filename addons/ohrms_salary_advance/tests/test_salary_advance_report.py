from odoo.tests.common import TransactionCase
from datetime import date

class TestSalaryAdvanceReport(TransactionCase):
    def setUp(self):
        super().setUp()
        self.employee = self.env['hr.employee'].create({'name': 'Test Employee'})
        self.department = self.env['hr.department'].create({'name': 'IT'})
        self.employee.department_id = self.department.id
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

    def test_report_aggregation(self):
        adv1 = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 1000000,
            'state': 'approve',
            'is_deducted': False,
        })
        adv2 = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 10),
            'advance': 500000,
            'state': 'approve',
            'is_deducted': True,
        })
        self.env.cr.commit()  # Đảm bảo view được cập nhật
        report = self.env['salary.advance.report'].search([('employee_id', '=', self.employee.id), ('month', '=', '2024-06')])
        self.assertEqual(len(report), 1)
        self.assertEqual(report.total_advance, 1500000)
        self.assertEqual(report.total_deducted, 500000)
        self.assertEqual(report.total_remaining, 1000000)

    def test_print_salary_advance_report(self):
        adv = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 1000000,
            'state': 'approve',
        })
        # Test render QWeb report (không lỗi)
        report_action = self.env.ref('ohrms_salary_advance.report_salary_advance_document')
        html = report_action._render_qweb_html([adv.id], data={})
        self.assertIn('ĐƠN XIN TẠM ỨNG LƯƠNG', html[0].decode('utf-8')) 