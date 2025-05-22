# -*- coding: utf-8 -*-
from datetime import date
from odoo.tests import common
from odoo.exceptions import ValidationError


class TestInsurancePayment(common.TransactionCase):
    def setUp(self):
        super().setUp()
        
        # Create test company
        self.company = self.env['res.company'].create({
            'name': 'Test Company',
            'currency_id': self.env.ref('base.VND').id,
        })
        
        # Create test department
        self.department = self.env['hr.department'].create({
            'name': 'Test Department',
            'company_id': self.company.id,
        })
        
        # Create test employee
        self.employee = self.env['hr.employee'].create({
            'name': 'Test Employee',
            'department_id': self.department.id,
            'company_id': self.company.id,
            'social_insurance_code': '1234567890',
            'social_insurance_status': 'active',
        })
        
        # Create test policy
        self.policy_bhxh = self.env['insurance.policy'].create({
            'name': 'Test BHXH',
            'is_social_insurance': True,
            'insurance_type': 'bhxh',
            'employee_rate': 8.0,
            'company_rate': 17.5,
        })
        
        # Create test insurance
        self.insurance = self.env['hr.insurance'].create({
            'employee_id': self.employee.id,
            'policy_id': self.policy_bhxh.id,
            'amount': 240000,
            'sum_insured': 3000000,
            'policy_coverage': 'monthly',
            'date_from': date.today(),
            'wage_base': 3000000,
            'allowances': 0,
            'company_id': self.company.id,
        })
        
        # Create test payment
        self.payment = self.env['insurance.payment'].create({
            'payment_date': date.today(),
            'period_month': str(date.today().month),
            'period_year': date.today().year,
            'insurance_type': 'bhxh',
            'payment_amount': 765000, # 3000000 * (8% + 17.5%)
            'payment_method': 'bank_transfer',
            'payment_ref': 'REF001',
            'company_id': self.company.id,
        })
        
        # Create test payment line
        self.payment_line = self.env['insurance.payment.line'].create({
            'payment_id': self.payment.id,
            'employee_id': self.employee.id,
            'salary_base': 3000000,
            'employee_bhxh_rate': 8.0,
            'employer_bhxh_rate': 17.5,
        })
        
    def test_01_payment_compute_fields(self):
        """Test computation of payment fields"""
        self.payment._compute_employee_count()
        self.assertEqual(self.payment.employee_count, 1, "Payment should have 1 employee")
        
        self.payment._compute_insurance_amounts()
        self.assertEqual(self.payment.bhxh_amount, 765000, "BHXH amount should be 765000")
        
        self.payment._compute_expected_amount()
        self.assertEqual(self.payment.expected_amount, 765000, "Expected amount should be 765000")
        
        self.payment._compute_difference_amount()
        self.assertEqual(self.payment.difference_amount, 0, "Difference should be 0")
        
    def test_02_payment_line_compute(self):
        """Test computation of payment line fields"""
        self.payment_line._compute_insurance_amounts()
        self.assertEqual(self.payment_line.bhxh_amount, 765000, "BHXH amount should be 765000")
        
        self.payment_line._compute_total_amount()
        self.assertEqual(self.payment_line.total_amount, 765000, "Total amount should be 765000")
        
    def test_03_payment_workflow(self):
        """Test payment workflow"""
        # Draft -> Confirmed
        self.payment.action_confirm()
        self.assertEqual(self.payment.state, 'confirmed', "Payment state should be 'confirmed'")
        
        # Confirmed -> Paid
        self.payment.action_set_to_paid()
        self.assertEqual(self.payment.state, 'paid', "Payment state should be 'paid'")
        
        # Paid -> Verified
        with self.assertRaises(ValidationError):
            # Should raise error because receipt attachment is missing
            self.payment.action_verify()
            
        # Add receipt and try again
        self.payment.receipt_attachment = b'test'
        self.payment.receipt_filename = 'test.pdf'
        self.payment.action_verify()
        self.assertEqual(self.payment.state, 'verified', "Payment state should be 'verified'")
        
        # Try to change verified payment to draft (should raise error)
        with self.assertRaises(ValidationError):
            self.payment.action_reset_to_draft()
            
    def test_04_payment_constraints(self):
        """Test payment constraints"""
        # Create a new payment
        payment2 = self.env['insurance.payment'].create({
            'payment_date': date.today(),
            'period_month': str(date.today().month),
            'period_year': date.today().year,
            'insurance_type': 'bhxh',
            'payment_amount': 765000,
            'payment_method': 'bank_transfer',
            'payment_ref': 'REF002',
            'company_id': self.company.id,
        })
        
        # Try to add the same employee twice (should raise error)
        self.env['insurance.payment.line'].create({
            'payment_id': payment2.id,
            'employee_id': self.employee.id,
            'salary_base': 3000000,
        })
        
        with self.assertRaises(ValidationError):
            self.env['insurance.payment.line'].create({
                'payment_id': payment2.id,
                'employee_id': self.employee.id,
                'salary_base': 3000000,
            })
            
    def test_05_payment_unlink(self):
        """Test payment deletion rules"""
        # Draft payment can be deleted
        payment_draft = self.env['insurance.payment'].create({
            'payment_date': date.today(),
            'period_month': str(date.today().month),
            'period_year': date.today().year,
            'insurance_type': 'bhxh',
            'payment_amount': 765000,
            'payment_method': 'bank_transfer',
            'company_id': self.company.id,
        })
        payment_draft.unlink()
        
        # Confirmed payment cannot be deleted
        payment_confirmed = self.env['insurance.payment'].create({
            'payment_date': date.today(),
            'period_month': str(date.today().month),
            'period_year': date.today().year,
            'insurance_type': 'bhxh',
            'payment_amount': 765000,
            'payment_method': 'bank_transfer',
            'company_id': self.company.id,
        })
        self.env['insurance.payment.line'].create({
            'payment_id': payment_confirmed.id,
            'employee_id': self.employee.id,
            'salary_base': 3000000,
        })
        payment_confirmed.action_confirm()
        
        with self.assertRaises(ValidationError):
            payment_confirmed.unlink()
            
        # But it can be cancelled and then deleted
        payment_confirmed.action_cancel()
        self.assertEqual(payment_confirmed.state, 'cancelled', "Payment state should be 'cancelled'")
        payment_confirmed.unlink() 