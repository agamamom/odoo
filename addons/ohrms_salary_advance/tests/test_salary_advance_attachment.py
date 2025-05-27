from odoo.tests.common import TransactionCase
from datetime import date

class TestSalaryAdvanceAttachment(TransactionCase):
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

    def test_attachment_upload_and_retrieve(self):
        adv = self.env['salary.advance'].create({
            'employee_id': self.employee.id,
            'date': date(2024, 6, 1),
            'advance': 1000000,
        })
        # Tạo attachment giả lập
        attachment = self.env['ir.attachment'].create({
            'name': 'test_doc.pdf',
            'datas': 'VGhpcyBpcyBhIHRlc3QgZG9jdW1lbnQu',  # base64 for 'This is a test document.'
            'res_model': 'salary.advance',
            'res_id': adv.id,
            'type': 'binary',
        })
        adv.attachments = [(6, 0, [attachment.id])]
        self.assertEqual(len(adv.attachments), 1)
        self.assertEqual(adv.attachments[0].name, 'test_doc.pdf') 