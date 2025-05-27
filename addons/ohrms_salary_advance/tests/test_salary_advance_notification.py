from odoo.tests.common import TransactionCase
from datetime import date

class TestSalaryAdvanceNotification(TransactionCase):
    def setUp(self):
        super().setUp()
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

    def test_notification_flow(self):
        adv = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 1000000,
            'approval_level': 2,
        })
        # Khi tạo mới
        self.assertIn('A new salary advance request has been created.', adv.message_ids.mapped('body'))
        adv.approve_request()
        adv.action_submit_to_manager()
        self.assertIn('The salary advance request has been submitted for approval.', adv.message_ids.mapped('body'))
        # Cấp 1 duyệt
        adv.with_user(self.hr_manager).action_approve_level()
        self.assertTrue(any('approved at level' in m for m in adv.message_ids.mapped('body')))
        # Cấp 2 từ chối
        adv.with_user(self.account_manager).action_reject_level(note='Không hợp lệ')
        self.assertTrue(any('rejected at level' in m for m in adv.message_ids.mapped('body')))
        # Đánh dấu đã trừ vào lương
        adv.is_deducted = True
        adv.mark_deducted_notify()
        self.assertIn('has been deducted in payslip', adv.message_ids.mapped('body')) 