from odoo import http
from odoo.http import request, Response
from odoo.addons.hr_rest_api.controllers.main import HrRestApiController
import json
import logging
from werkzeug.exceptions import BadRequest, Forbidden
from datetime import datetime, date
import base64

_logger = logging.getLogger(__name__)

# Check if required modules are installed
PAYROLL_INSTALLED = False
try:
    from odoo.addons.hr_payroll_community.models.hr_payslip import HrPayslip
    PAYROLL_INSTALLED = True
except ImportError:
    _logger.info("hr_payroll_community module not installed, payslip features will be disabled")

class EmployeePayrollApi(HrRestApiController):
    
    def _validate_employee_access(self, employee_id=None):
        """
        Validate that the authenticated user has access to the employee's payroll data
        Returns (is_valid, employee, user) or (is_valid, error_message, None)
        """
        # Validate API key first
        is_valid, result = self._validate_api_key()
        if not is_valid:
            return False, result, None
            
        user = result
        
        # Find the employee linked to this user
        if employee_id:
            employee = request.env['hr.employee'].sudo().browse(employee_id)
            if not employee.exists():
                return False, {"error": "Employee not found"}, None
            
            # Check if the user is accessing their own data
            if employee.user_id.id != user.id:
                return False, {"error": "You can only access your own payroll data"}, None
        else:
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            if not employee:
                return False, {"error": "No employee record found for your user account"}, None
                
        return True, employee, user
    
    # --- CORS preflight handlers ---
    @http.route([
        '/api/employee/payslips',
        '/api/employee/payslips/<int:payslip_id>',
        '/api/employee/payslips/<int:payslip_id>/lines',
        '/api/employee/payslips/<int:payslip_id>/pdf',
        '/api/employee/payroll/structure',
        '/api/employee/gdpr/data_request',
        '/api/employee/gdpr/data_correction',
        '/api/employee/gdpr/data_portability'
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_employee_payroll_endpoints(self, **kw):
        """Handle OPTIONS request for employee payroll endpoints"""
        return self._handle_options_request()
    
    # --- 1. Payslip Access - View Own Payslips Only ---
    @http.route('/api/employee/payslips', type='http', auth='public', methods=['GET'], csrf=False)
    def get_own_payslips(self, **kw):
        """Get all payslips for the authenticated employee"""
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
        
        # Validate employee access
        is_valid, result, user = self._validate_employee_access()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        employee = result
        
        # Apply filters
        domain = [('employee_id', '=', employee.id)]
        
        date_from = kw.get('date_from')
        if date_from:
            domain.append(('date_from', '>=', date_from))
            
        date_to = kw.get('date_to')
        if date_to:
            domain.append(('date_to', '<=', date_to))
            
        state = kw.get('state')
        if state:
            domain.append(('state', '=', state))
            
        # Pagination
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        
        # Get payslips
        payslips = request.env['hr.payslip'].sudo().search(domain, limit=limit, offset=offset, 
                                                         order='date_from desc, id desc')
        
        # Format response
        result = {
            'success': True,
            'count': len(payslips),
            'total': request.env['hr.payslip'].sudo().search_count(domain),
            'payslips': [{
                'id': payslip.id,
                'name': payslip.name,
                'date_from': payslip.date_from.strftime('%Y-%m-%d') if payslip.date_from else False,
                'date_to': payslip.date_to.strftime('%Y-%m-%d') if payslip.date_to else False,
                'state': payslip.state,
                'number': payslip.number,
                'company_id': payslip.company_id.id,
                'company_name': payslip.company_id.name,
            } for payslip in payslips]
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/employee/payslips/<int:payslip_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_own_payslip_detail(self, payslip_id, **kw):
        """Get detailed information about a specific payslip for the authenticated employee"""
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        # Get the payslip
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Validate employee access to this specific payslip's employee
        is_valid, result, user = self._validate_employee_access(payslip.employee_id.id)
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Format response
        result = {
            'success': True,
            'payslip': {
                'id': payslip.id,
                'name': payslip.name,
                'employee_id': payslip.employee_id.id,
                'employee_name': payslip.employee_id.name,
                'date_from': payslip.date_from.strftime('%Y-%m-%d') if payslip.date_from else False,
                'date_to': payslip.date_to.strftime('%Y-%m-%d') if payslip.date_to else False,
                'state': payslip.state,
                'number': payslip.number,
                'company_id': payslip.company_id.id,
                'company_name': payslip.company_id.name,
                'contract_id': payslip.contract_id.id if payslip.contract_id else False,
                'contract_name': payslip.contract_id.name if payslip.contract_id else False,
                'struct_id': payslip.struct_id.id if payslip.struct_id else False,
                'struct_name': payslip.struct_id.name if payslip.struct_id else False,
            }
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/employee/payslips/<int:payslip_id>/lines', type='http', auth='public', methods=['GET'], csrf=False)
    def get_own_payslip_lines(self, payslip_id, **kw):
        """Get the salary lines for a specific payslip for the authenticated employee"""
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        # Get the payslip
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Validate employee access to this specific payslip's employee
        is_valid, result, user = self._validate_employee_access(payslip.employee_id.id)
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Format response
        result = {
            'success': True,
            'payslip_id': payslip.id,
            'lines': [{
                'id': line.id,
                'name': line.name,
                'code': line.code,
                'category_id': line.category_id.id if line.category_id else False,
                'category_name': line.category_id.name if line.category_id else False,
                'amount': line.amount,
                'quantity': line.quantity,
                'rate': line.rate,
                'total': line.total,
                'sequence': line.sequence,
            } for line in payslip.line_ids]
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/employee/payslips/<int:payslip_id>/pdf', type='http', auth='public', methods=['GET'], csrf=False)
    def get_own_payslip_pdf(self, payslip_id, **kw):
        """Get the PDF report for a specific payslip for the authenticated employee"""
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        # Get the payslip
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Validate employee access to this specific payslip's employee
        is_valid, result, user = self._validate_employee_access(payslip.employee_id.id)
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Generate PDF report
        try:
            report_name = 'hr_payroll_community.report_payslip'
            pdf_content, content_type = request.env.ref(report_name)._render_qweb_pdf([payslip.id])
            
            # Prepare response
            filename = f"Payslip-{payslip.employee_id.name}-{payslip.date_from}.pdf"
            response = request.make_response(
                pdf_content,
                headers=[
                    ('Content-Type', 'application/pdf'),
                    ('Content-Disposition', f'attachment; filename="{filename}"'),
                    ('Content-Length', len(pdf_content)),
                ]
            )
            return self._add_cors_headers(response)
        except Exception as e:
            _logger.error("Error generating payslip PDF: %s", str(e))
            result = {'success': False, 'error': 'Failed to generate PDF'}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
    
    # --- 5. Payslip Structure View-Only Access ---
    @http.route('/api/employee/payroll/structure', type='http', auth='public', methods=['GET'], csrf=False)
    def get_own_payroll_structure(self, **kw):
        """Get the payroll structure applied to the authenticated employee's contract"""
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
        
        # Validate employee access
        is_valid, result, user = self._validate_employee_access()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        employee = result
        
        # Get the active contract
        contract = request.env['hr.contract'].sudo().search([
            ('employee_id', '=', employee.id),
            ('state', '=', 'open')
        ], limit=1)
        
        if not contract:
            result = {'success': False, 'error': 'No active contract found'}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the structure
        structure = contract.struct_id
        if not structure:
            result = {'success': False, 'error': 'No salary structure found on contract'}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Format response
        result = {
            'success': True,
            'structure': {
                'id': structure.id,
                'name': structure.name,
                'code': structure.code,
                'parent_id': structure.parent_id.id if structure.parent_id else False,
                'parent_name': structure.parent_id.name if structure.parent_id else False,
                'rule_categories': [],
            }
        }
        
        # Group rules by category
        categories = {}
        for rule in structure.rule_ids:
            category_id = rule.category_id.id
            if category_id not in categories:
                categories[category_id] = {
                    'id': category_id,
                    'name': rule.category_id.name,
                    'code': rule.category_id.code,
                    'rules': []
                }
            
            categories[category_id]['rules'].append({
                'id': rule.id,
                'name': rule.name,
                'code': rule.code,
                'sequence': rule.sequence,
            })
        
        result['structure']['rule_categories'] = list(categories.values())
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    # --- 4 & 6. GDPR-Related Functions ---
    @http.route('/api/employee/gdpr/data_request', type='json', auth='public', methods=['POST'], csrf=False)
    def request_personal_data(self, **kw):
        """Submit a request to access personal data (GDPR compliance)"""
        # Validate employee access
        is_valid, result, user = self._validate_employee_access()
        if not is_valid:
            return result
            
        employee = result
        
        # Check if data protection is enabled
        protection = request.env['hr.payroll.data.protection'].sudo().search([
            ('company_id', '=', employee.company_id.id),
            ('active', '=', True)
        ], limit=1)
        
        if not protection or not protection.enable_data_subject_requests:
            return {
                'success': False,
                'error': 'Data subject requests are not enabled for your company'
            }
        
        # Create data request
        try:
            request_data = {
                'employee_id': employee.id,
                'request_type': 'access',
                'request_date': fields.Date.today(),
                'state': 'pending',
                'note': kw.get('note', 'Self-service portal request'),
            }
            
            data_request = request.env['hr.gdpr.request'].sudo().create(request_data)
            
            # Notify data protection officer
            if protection.data_officer_id:
                data_request.message_subscribe(partner_ids=[protection.data_officer_id.partner_id.id])
                data_request.message_post(
                    body=f"Data subject access request submitted by employee {employee.name}",
                    partner_ids=[protection.data_officer_id.partner_id.id]
                )
            
            return {
                'success': True,
                'request_id': data_request.id,
                'message': 'Your request has been submitted successfully'
            }
        except Exception as e:
            _logger.error("Error creating GDPR data request: %s", str(e))
            return {
                'success': False,
                'error': 'Failed to submit request'
            }
    
    @http.route('/api/employee/gdpr/data_correction', type='json', auth='public', methods=['POST'], csrf=False)
    def request_data_correction(self, **kw):
        """Submit a request to correct personal data (GDPR compliance)"""
        # Validate employee access
        is_valid, result, user = self._validate_employee_access()
        if not is_valid:
            return result
            
        employee = result
        
        # Check if data protection is enabled
        protection = request.env['hr.payroll.data.protection'].sudo().search([
            ('company_id', '=', employee.company_id.id),
            ('active', '=', True)
        ], limit=1)
        
        if not protection or not protection.enable_data_subject_requests:
            return {
                'success': False,
                'error': 'Data subject requests are not enabled for your company'
            }
        
        # Required fields
        field_to_correct = kw.get('field')
        current_value = kw.get('current_value')
        requested_value = kw.get('requested_value')
        
        if not field_to_correct or not requested_value:
            return {
                'success': False,
                'error': 'Field name and requested value are required'
            }
        
        # Create correction request
        try:
            request_data = {
                'employee_id': employee.id,
                'request_type': 'correction',
                'request_date': fields.Date.today(),
                'state': 'pending',
                'field_to_correct': field_to_correct,
                'current_value': current_value,
                'requested_value': requested_value,
                'note': kw.get('note', ''),
            }
            
            data_request = request.env['hr.gdpr.request'].sudo().create(request_data)
            
            # Notify data protection officer
            if protection.data_officer_id:
                data_request.message_subscribe(partner_ids=[protection.data_officer_id.partner_id.id])
                data_request.message_post(
                    body=f"Data correction request submitted by employee {employee.name}",
                    partner_ids=[protection.data_officer_id.partner_id.id]
                )
            
            return {
                'success': True,
                'request_id': data_request.id,
                'message': 'Your correction request has been submitted successfully'
            }
        except Exception as e:
            _logger.error("Error creating GDPR correction request: %s", str(e))
            return {
                'success': False,
                'error': 'Failed to submit request'
            }
    
    @http.route('/api/employee/gdpr/data_portability', type='http', auth='public', methods=['GET'], csrf=False)
    def request_data_portability(self, **kw):
        """Export personal data in a machine-readable format (GDPR compliance)"""
        # Validate employee access
        is_valid, result, user = self._validate_employee_access()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        employee = result
        
        # Check if data protection is enabled
        protection = request.env['hr.payroll.data.protection'].sudo().search([
            ('company_id', '=', employee.company_id.id),
            ('active', '=', True)
        ], limit=1)
        
        if not protection or not protection.enable_data_subject_requests:
            result = {
                'success': False,
                'error': 'Data subject requests are not enabled for your company'
            }
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Collect employee data
        try:
            # Basic employee info
            employee_data = {
                'id': employee.id,
                'name': employee.name,
                'work_email': employee.work_email,
                'work_phone': employee.work_phone,
                'department': employee.department_id.name if employee.department_id else '',
                'job_title': employee.job_id.name if employee.job_id else '',
                'address': {
                    'street': employee.address_id.street if employee.address_id else '',
                    'street2': employee.address_id.street2 if employee.address_id else '',
                    'city': employee.address_id.city if employee.address_id else '',
                    'zip': employee.address_id.zip if employee.address_id else '',
                    'country': employee.address_id.country_id.name if employee.address_id and employee.address_id.country_id else '',
                },
                'contracts': [],
                'payslips': []
            }
            
            # Contracts
            contracts = request.env['hr.contract'].sudo().search([('employee_id', '=', employee.id)])
            for contract in contracts:
                employee_data['contracts'].append({
                    'id': contract.id,
                    'name': contract.name,
                    'start_date': contract.date_start.strftime('%Y-%m-%d') if contract.date_start else '',
                    'end_date': contract.date_end.strftime('%Y-%m-%d') if contract.date_end else '',
                    'wage': contract.wage,
                    'state': contract.state,
                    'structure': contract.struct_id.name if contract.struct_id else '',
                })
            
            # Payslips (last 12 months)
            one_year_ago = (datetime.now().date().replace(day=1))
            one_year_ago = one_year_ago.replace(year=one_year_ago.year-1)
            
            payslips = request.env['hr.payslip'].sudo().search([
                ('employee_id', '=', employee.id),
                ('date_from', '>=', one_year_ago.strftime('%Y-%m-%d'))
            ])
            
            for payslip in payslips:
                payslip_data = {
                    'id': payslip.id,
                    'name': payslip.name,
                    'date_from': payslip.date_from.strftime('%Y-%m-%d') if payslip.date_from else '',
                    'date_to': payslip.date_to.strftime('%Y-%m-%d') if payslip.date_to else '',
                    'state': payslip.state,
                    'lines': []
                }
                
                for line in payslip.line_ids:
                    payslip_data['lines'].append({
                        'name': line.name,
                        'code': line.code,
                        'category': line.category_id.name if line.category_id else '',
                        'amount': line.amount,
                        'total': line.total,
                    })
                
                employee_data['payslips'].append(payslip_data)
            
            # Return as JSON file
            filename = f"employee_data_{employee.name}_{datetime.now().strftime('%Y%m%d')}.json"
            response = request.make_response(
                json.dumps(employee_data, indent=2),
                headers=[
                    ('Content-Type', 'application/json'),
                    ('Content-Disposition', f'attachment; filename="{filename}"'),
                ]
            )
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error generating data portability export: %s", str(e))
            result = {
                'success': False,
                'error': 'Failed to generate data export'
            }
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response) 