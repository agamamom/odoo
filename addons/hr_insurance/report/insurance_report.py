# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import date, timedelta

# Import the wizard model from wizards directory is causing circular dependency
# from ..wizards.insurance_report_wizard import InsuranceReportWizard

class InsuranceReport(models.AbstractModel):
    _name = 'report.hr_insurance.report_insurance'
    _description = 'Báo cáo bảo hiểm xã hội'
    
    @api.model
    def _get_report_values(self, docids, data=None):
        if not docids and not data:
            raise UserError(_("Không tìm thấy dữ liệu cho báo cáo"))
            
        # Nếu chạy từ báo cáo xuất PDF trực tiếp
        if docids and not data:
            insurances = self.env['hr.insurance'].browse(docids)
            
            insurance_data = []
            for insurance in insurances:
                insurance_data.append({
                    'employee_id': insurance.employee_id.id,
                    'employee_name': insurance.employee_id.name,
                    'department': insurance.employee_id.department_id.name,
                    'policy': insurance.policy_id.name,
                    'insurance_type': dict(insurance._fields['insurance_type'].selection).get(insurance.insurance_type),
                    'date_from': insurance.date_from,
                    'date_to': insurance.date_to,
                    'state': dict(insurance._fields['state'].selection).get(insurance.state),
                    'amount': insurance.amount,
                    'employee_contribution': insurance.employee_contribution,
                    'company_contribution': insurance.company_contribution,
                    'total_contribution': insurance.total_contribution,
                    'salary_base': insurance.salary_base,
                    'employee_rate': insurance.policy_id.employee_rate if insurance.policy_id else 0,
                    'company_rate': insurance.policy_id.company_rate if insurance.policy_id else 0
                })
                
            data = {
                'form': {
                    'date_from': min(insurances.mapped('date_from')) if insurances.mapped('date_from') else fields.Date.today(),
                    'date_to': max(insurances.mapped('date_to')) if insurances.mapped('date_to') else fields.Date.today(),
                    'department_name': 'Nhiều phòng ban' if len(set(insurances.mapped('department_id.id'))) > 1 else insurances[0].department_id.name if insurances.mapped('department_id') else 'Tất cả phòng ban',
                    'company_name': insurances[0].company_id.name if insurances else self.env.company.name,
                    'insurance_type': 'All',
                    'include_expired': True,
                    'insurance_records': insurance_data,
                }
            }
            
            # Thêm thông tin lịch sử thanh toán (nếu docids đủ nhỏ để là lựa chọn có chủ ý)
            if len(docids) <= 20:  # Giới hạn số lượng hợp lý cho việc xem lịch sử
                # Mặc định lấy 3 tháng gần nhất
                today = fields.Date.today()
                payment_from_date = today - timedelta(days=90)
                payment_to_date = today
                
                # Lấy danh sách nhân viên để tìm các khoản thanh toán liên quan
                employee_ids = list(set(insurance.employee_id.id for insurance in insurances if insurance.employee_id))
                
                # Tìm các thanh toán có chứa nhân viên được chọn
                if employee_ids:
                    payment_lines = self.env['insurance.payment.line'].search([
                        ('employee_id', 'in', employee_ids)
                    ])
                    payment_ids = payment_lines.mapped('payment_id.id')
                    
                    if payment_ids:
                        payments = self.env['insurance.payment'].search([
                            ('id', 'in', payment_ids),
                            ('payment_date', '>=', payment_from_date),
                            ('payment_date', '<=', payment_to_date),
                            ('state', 'in', ['paid', 'verified'])
                        ])
                        
                        if payments:
                            # Thêm thông tin thanh toán vào dữ liệu báo cáo
                            data['form']['payment_history'] = [{
                                'name': payment.name,
                                'payment_date': payment.payment_date,
                                'period': f"{payment.period_month}/{payment.period_year}",
                                'payment_amount': payment.payment_amount,
                                'payment_ref': payment.payment_ref,
                                'state': dict(payment._fields['state'].selection).get(payment.state),
                                'bhxh_amount': payment.bhxh_amount,
                                'bhyt_amount': payment.bhyt_amount,
                                'bhtn_amount': payment.bhtn_amount,
                                'employee_count': payment.employee_count
                            } for payment in payments]
                            
                            data['form']['include_payment_history'] = True
                            data['form']['payment_from_date'] = payment_from_date
                            data['form']['payment_to_date'] = payment_to_date
                            data['form']['total_payment_amount'] = sum(payments.mapped('payment_amount'))
            
        result = {
            'doc_ids': docids,
            'doc_model': 'hr.insurance',
            'data': data['form'] if data and 'form' in data else data,
            'date_from': data['form']['date_from'] if data and 'form' in data else None,
            'date_to': data['form']['date_to'] if data and 'form' in data else None,
            'insurance_type': data['form']['insurance_type'] if data and 'form' in data else None,
            'company_name': data['form']['company_name'] if data and 'form' in data else self.env.company.name,
            'department_name': data['form']['department_name'] if data and 'form' in data else 'Tất cả phòng ban',
            'insurance_records': data['form']['insurance_records'] if data and 'form' in data and 'insurance_records' in data['form'] else [],
            'total_employee': sum([r['employee_contribution'] for r in data['form']['insurance_records']]) if data and 'form' in data and 'insurance_records' in data['form'] else 0,
            'total_company': sum([r['company_contribution'] for r in data['form']['insurance_records']]) if data and 'form' in data and 'insurance_records' in data['form'] else 0,
            'total_all': sum([r['total_contribution'] for r in data['form']['insurance_records']]) if data and 'form' in data and 'insurance_records' in data['form'] else 0,
            'res_company': self.env.company,
        }
        
        # Thêm thông tin lịch sử thanh toán
        if data and 'form' in data and 'payment_history' in data['form']:
            result['include_payment_history'] = True
            result['payment_history'] = data['form']['payment_history']
            result['payment_from_date'] = data['form']['payment_from_date']
            result['payment_to_date'] = data['form']['payment_to_date']
            result['total_payment_amount'] = data['form']['total_payment_amount']
        
        return result 