# -*- coding: utf-8 -*-
from odoo.tests import common
from datetime import date, timedelta

class TestSocialInsurance(common.TransactionCase):
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
        
    def test_social_insurance_calculation(self):
        """Test BHXH insurance amount calculations"""
        # Create insurance for employee
        insurance = self.env['hr.insurance'].create({
            'employee_id': self.employee.id,
            'policy_id': self.bhxh_policy.id,
            'insurance_type': 'bhxh',
            'salary_base': 10000000,  # 10 million VND
            'date_from': date.today(),
        })
        
        # Confirm insurance
        insurance.action_confirm()
        
        # Check calculated contributions
        self.assertEqual(insurance.state, 'active')
        self.assertEqual(insurance.employee_contribution, 800000)  # 8% of 10 million
        self.assertEqual(insurance.company_contribution, 1750000)  # 17.5% of 10 million
        self.assertEqual(insurance.total_contribution, 2550000)  # Sum of both contributions

    def test_bhyt_card_expiration(self):
        """Test BHYT card expiration detection"""
        # Create a BHYT document
        bhyt_doc = self.env['social.insurance.document'].create({
            'employee_id': self.employee.id,
            'document_type': 'bhyt_card',
            'date': date.today(),
            'bhyt_number': 'BH12345678',
            'bhyt_issue_date': date.today() - timedelta(days=180),
            'bhyt_expiry_date': date.today() + timedelta(days=15),  # Expires soon
            'bhyt_hospital': 'Test Hospital',
        })
        
        # Force compute fields
        bhyt_doc._compute_bhyt_expired()
        
        # Verify expiry calculation
        self.assertFalse(bhyt_doc.is_bhyt_expired)
        self.assertEqual(bhyt_doc.days_to_expire, 15)
        
        # Change to expired date
        bhyt_doc.bhyt_expiry_date = date.today() - timedelta(days=1)
        bhyt_doc._compute_bhyt_expired()
        
        # Verify it's now expired
        self.assertTrue(bhyt_doc.is_bhyt_expired)
        self.assertEqual(bhyt_doc.days_to_expire, 0) 