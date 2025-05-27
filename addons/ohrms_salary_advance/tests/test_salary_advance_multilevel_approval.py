from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from datetime import date

class TestSalaryAdvanceMultiLevelApproval(TransactionCase):
    def setUp(self):
        super().setUp()
        self.env = self.env(context=dict(self.env.context, test_queue_job_no_delay=True))
        self.employee = self.env['hr.employee'].create({'name': 'Test Employee'})
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
        self.hr_manager = self.env.ref('hr.group_hr_manager').users[:1] or self.env.user
        self.account_manager = self.env.ref('account.group_account_manager').users[:1] or self.env.user
        self.admin = self.env.ref('base.group_system').users[:1] or self.env.user

    def test_multilevel_approval_happy_path(self):
        adv = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 1000000,
            'approval_level': 3,
        })
        adv.approve_request()
        adv.action_submit_to_manager()
        # Cấp 1 duyệt
        adv.with_user(self.hr_manager).action_approve_level()
        self.assertEqual(adv.current_approval_level, 2)
        self.assertEqual(adv.approval_line_ids[0].state, 'approved')
        # Cấp 2 duyệt
        adv.with_user(self.account_manager).action_approve_level()
        self.assertEqual(adv.current_approval_level, 3)
        self.assertEqual(adv.approval_line_ids[1].state, 'approved')
        # Cấp 3 duyệt
        adv.with_user(self.admin).action_approve_level()
        self.assertEqual(adv.state, 'approve')
        self.assertEqual(adv.approval_line_ids[2].state, 'approved')

    def test_reject_at_level(self):
        adv = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 1000000,
            'approval_level': 3,
        })
        adv.approve_request()
        adv.action_submit_to_manager()
        # Cấp 1 duyệt
        adv.with_user(self.hr_manager).action_approve_level()
        # Cấp 2 từ chối
        adv.with_user(self.account_manager).action_reject_level(note='Không hợp lệ')
        self.assertEqual(adv.state, 'reject')
        self.assertEqual(adv.approval_line_ids[1].state, 'rejected')
        # Không thể duyệt tiếp
        with self.assertRaises(UserError):
            adv.with_user(self.admin).action_approve_level()

    def test_wrong_user_cannot_approve(self):
        adv = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 1000000,
            'approval_level': 2,
        })
        adv.approve_request()
        adv.action_submit_to_manager()
        # Người không đúng cấp không thể duyệt
        with self.assertRaises(UserError):
            adv.with_user(self.admin).action_approve_level()

    def test_salary_advance_deducted_in_payslip(self):
        adv = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 2000000,
            'approval_level': 2,
        })
        adv.approve_request()
        adv.action_submit_to_manager()
        adv.action_approve_level()  # cấp 1
        adv.action_approve_level()  # cấp 2 (state='approve')
        self.assertEqual(adv.state, 'approve')
        # Tạo payslip tháng 6/2024
        payslip = self.env['hr.payslip'].create({
            'employee_id': self.employee.id,
            'contract_id': self.contract.id,
            'date_from': date(2024, 6, 1),
            'date_to': date(2024, 6, 30),
        })
        payslip.action_payslip_done()
        # Kiểm tra input SAR đã trừ đúng số tiền
        sar_input = payslip.input_line_ids.filtered(lambda l: l.code == 'SAR')
        self.assertTrue(sar_input, 'Không có input SAR trên payslip')
        self.assertEqual(sar_input.amount, -2000000)
        # Kiểm tra is_deducted đã được cập nhật
        adv.refresh()
        self.assertTrue(adv.is_deducted) 