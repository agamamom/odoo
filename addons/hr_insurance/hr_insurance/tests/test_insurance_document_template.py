# -*- coding: utf-8 -*-
from odoo.tests import common
from odoo.exceptions import UserError, ValidationError
from datetime import date, timedelta


class TestInsuranceDocumentTemplate(common.TransactionCase):
    def setUp(self):
        super().setUp()
        # Create test employee
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'gender': 'male',
            'birthday': '1990-01-01',
        })
        
        # Get BHXH policy
        self.bhxh_policy = self.env.ref('hr_insurance.insurance_policy_bhxh')
        
        # Create insurance for employee
        self.insurance = self.env['hr.insurance'].create({
            'employee_id': self.employee.id,
            'policy_id': self.bhxh_policy.id,
            'insurance_type': 'bhxh',
            'salary_base': 10000000,  # 10 million VND
            'date_from': date.today(),
        })
        
        # Create document template
        self.template = self.env['insurance.document.template'].create({
            'name': 'Test BHXH Document Template',
            'document_type': 'bhxh_book',
            'default_bhxh_book_issue_place': 'Test City',
            'auto_set_deadline': True,
            'days_deadline': 15,
            'default_notes': 'Test notes for the document'
        })
    
    def test_document_template_creation(self):
        """Test document template creation and code generation"""
        self.assertTrue(self.template.code, "Template code should be generated")
        self.assertEqual(self.template.document_type, 'bhxh_book', "Document type should be set correctly")
        
    def test_document_creation_from_template(self):
        """Test creating documents from template"""
        # Create a wizard to generate document from template
        wizard = self.env['insurance.document.create.wizard'].create({
            'template_id': self.template.id,
            'employee_ids': [(4, self.employee.id)],
            'date': date.today(),
        })
        
        # Check that values are properly set from the template
        wizard._onchange_template_id()
        self.assertEqual(wizard.bhxh_book_issue_place, 'Test City',
                         "Template values should be copied to the wizard")
        self.assertEqual(wizard.notes, 'Test notes for the document',
                         "Notes should be copied from template")
        
        # Execute the wizard and check document creation
        result = wizard.action_create_documents()
        
        # Check if a document was created
        document_id = result.get('res_id') if result.get('res_mode') == 'form' else False
        if not document_id:
            domain = result.get('domain')
            document_ids = self.env['social.insurance.document'].search(domain)
            self.assertEqual(len(document_ids), 1, "One document should be created")
            document = document_ids[0]
        else:
            document = self.env['social.insurance.document'].browse(document_id)
        
        # Verify document values
        self.assertEqual(document.employee_id.id, self.employee.id, 
                         "Document should be linked to the correct employee")
        self.assertEqual(document.document_type, 'bhxh_book',
                         "Document should have the correct type")
        self.assertEqual(document.bhxh_book_issue_place, 'Test City',
                         "Document should have values from template")
        self.assertEqual(document.notes, 'Test notes for the document',
                         "Document should have notes from template")
        
    def test_multiple_document_creation(self):
        """Test creating documents for multiple employees at once"""
        # Create a second employee
        employee2 = self.env['hr.employee'].create({
            'name': 'Test Employee 2',
            'gender': 'female',
            'birthday': '1992-05-15',
        })
        
        # Create a wizard to generate documents for both employees
        wizard = self.env['insurance.document.create.wizard'].create({
            'template_id': self.template.id,
            'employee_ids': [(6, 0, [self.employee.id, employee2.id])],
            'date': date.today(),
        })
        
        # Execute the wizard
        wizard._onchange_template_id()
        result = wizard.action_create_documents()
        
        # Check that documents were created for both employees
        domain = result.get('domain')
        document_ids = self.env['social.insurance.document'].search(domain)
        self.assertEqual(len(document_ids), 2, "Two documents should be created")
        
        # Verify that each employee has a document
        employee_ids = document_ids.mapped('employee_id.id')
        self.assertIn(self.employee.id, employee_ids, 
                      "First employee should have a document")
        self.assertIn(employee2.id, employee_ids,
                      "Second employee should have a document") 