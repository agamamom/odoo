from odoo import http
from odoo.http import request, Response
import json
from werkzeug.exceptions import BadRequest, NotFound
from odoo import fields
import datetime
import base64


class HrInsuranceController(http.Controller):
    
    def _validate_api_key(self):
        """Validate the API key from the request headers"""
        api_key = request.httprequest.headers.get('API-Key')
        if not api_key:
            return False, {"error": "API Key is required in the header"}
        
        # Check if the API key is valid (in a real implementation, this should be stored securely)
        user = request.env['res.users'].sudo().search([('api_key', '=', api_key)], limit=1)
        if not user:
            return False, {"error": "Invalid API Key"}
        
        return True, user
    
    def _add_cors_headers(self, response):
        """Add CORS headers to the response"""
        # For development, use '*' to allow all origins; for production, specify exact origins
        allowed_origins = ['http://localhost:5000']  # Replace with your Flutter app's origin
        origin = request.httprequest.headers.get('Origin', '*')
        response.headers.set('Access-Control-Allow-Origin', origin if origin in allowed_origins else '*')
        response.headers.set('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        response.headers.set('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, API-Key')
        response.headers.set('Access-Control-Max-Age', '86400')  # 24 hours cache for preflight requests
        return response
    
    def _handle_options_request(self):
        """Handle OPTIONS preflight requests"""
        response = Response(status=200)
        return self._add_cors_headers(response)
    
    # CORS preflight OPTIONS handling for all insurance routes
    @http.route([
        '/api/hr/insurance',
        '/api/hr/insurance/<int:insurance_id>',
        '/api/hr/insurance/employee/<int:employee_id>',
        '/api/hr/insurance/policies',
        '/api/hr/insurance/policies/<int:policy_id>',
        '/api/hr/insurance/documents',
        '/api/hr/insurance/documents/<int:document_id>',
        '/api/hr/insurance/documents/employee/<int:employee_id>',
        '/api/hr/insurance/allowances',
        '/api/hr/insurance/allowances/<int:allowance_id>',
        '/api/hr/insurance/allowances/employee/<int:employee_id>',
        '/api/hr/insurance/histories',
        '/api/hr/insurance/histories/<int:history_id>',
        '/api/hr/insurance/histories/employee/<int:employee_id>',
        '/api/hr/insurance/benefits',
        '/api/hr/insurance/benefits/<int:benefit_id>',
        '/api/hr/insurance/late_fees',
        '/api/hr/insurance/late_fees/<int:late_fee_id>',
        '/api/hr/insurance/document_templates',
        '/api/hr/insurance/document_templates/<int:template_id>'
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_insurance_routes(self, **kw):
        """Handle OPTIONS request for insurance endpoints"""
        return self._handle_options_request()
    
    # Insurance Policies API
    @http.route('/api/hr/insurance/policies', type='http', auth='public', methods=['GET'], csrf=False)
    def get_insurance_policies(self, **kw):
        """Get all insurance policies"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Get query parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'id desc')
            
            # Create domain filters
            domain = []
            if kw.get('active') is not None:
                domain.append(('active', '=', kw.get('active') == 'true'))
            if kw.get('policy_type'):
                domain.append(('policy_type', '=', kw.get('policy_type')))
            if kw.get('coverage_type'):
                domain.append(('coverage_type', '=', kw.get('coverage_type')))
            
            # Get data from model
            fields_to_get = ['id', 'name', 'policy_type', 'coverage_type', 'employee_rate', 
                            'company_rate', 'total_rate', 'note', 'active', 
                            'company_id', 'is_social_insurance']
            
            policies = request.env['insurance.policy'].sudo().search_read(
                domain=domain,
                fields=fields_to_get,
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(policies),
                'data': policies
            }
            
            response = Response(json.dumps(result, default=str), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)

    @http.route('/api/hr/insurance/policies/<int:policy_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_insurance_policy(self, policy_id, **kw):
        """Get a specific insurance policy by ID"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Get policy
            fields_to_get = ['id', 'name', 'policy_type', 'coverage_type', 'employee_rate', 
                            'company_rate', 'total_rate', 'note', 'active', 
                            'company_id', 'is_social_insurance']
            
            policy = request.env['insurance.policy'].sudo().search_read(
                domain=[('id', '=', policy_id)],
                fields=fields_to_get,
                limit=1
            )
            
            if not policy:
                result = {
                    'success': False,
                    'error': f'Insurance policy not found with ID {policy_id}'
                }
                response = Response(json.dumps(result), content_type='application/json', status=404)
                return self._add_cors_headers(response)
            
            result = {
                'success': True,
                'data': policy[0]
            }
            
            response = Response(json.dumps(result, default=str), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)
            
    @http.route('/api/hr/insurance/policies', type='json', auth='public', methods=['POST'], csrf=False)
    def create_insurance_policy(self, **kw):
        """Create a new insurance policy"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Required fields
            required_fields = ['name', 'policy_type', 'coverage_type', 'employee_rate', 'company_rate']
            for field in required_fields:
                if field not in kw:
                    return {
                        'success': False,
                        'error': f"Field '{field}' is required"
                    }
            
            # Create new policy
            values = {
                'name': kw.get('name'),
                'policy_type': kw.get('policy_type'),
                'coverage_type': kw.get('coverage_type'),
                'employee_rate': kw.get('employee_rate'),
                'company_rate': kw.get('company_rate')
            }
            
            # Optional fields
            if 'note' in kw:
                values['note'] = kw.get('note')
            if 'active' in kw:
                values['active'] = kw.get('active')
            if 'company_id' in kw:
                values['company_id'] = kw.get('company_id')
            if 'is_social_insurance' in kw:
                values['is_social_insurance'] = kw.get('is_social_insurance')
            
            new_policy = request.env['insurance.policy'].sudo().create(values)
            
            return {
                'success': True,
                'id': new_policy.id,
                'message': 'Insurance policy created successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/hr/insurance/policies/<int:policy_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_insurance_policy(self, policy_id, **kw):
        """Update an existing insurance policy"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Find policy
            policy = request.env['insurance.policy'].sudo().browse(policy_id)
            if not policy.exists():
                return {
                    'success': False,
                    'error': f'Insurance policy not found with ID {policy_id}'
                }
            
            # Update fields
            values = {}
            for field in ['name', 'policy_type', 'coverage_type', 'employee_rate', 
                         'company_rate', 'note', 'active', 'company_id', 'is_social_insurance']:
                if field in kw:
                    values[field] = kw.get(field)
            
            policy.write(values)
            
            return {
                'success': True,
                'id': policy.id,
                'message': 'Insurance policy updated successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/hr/insurance/policies/<int:policy_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_insurance_policy(self, policy_id, **kw):
        """Delete an insurance policy"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Find policy
            policy = request.env['insurance.policy'].sudo().browse(policy_id)
            if not policy.exists():
                result = {
                    'success': False,
                    'error': f'Insurance policy not found with ID {policy_id}'
                }
                response = Response(json.dumps(result), content_type='application/json', status=404)
                return self._add_cors_headers(response)
            
            # Check if policy is used in any insurance
            insurance_count = request.env['hr.insurance'].sudo().search_count([('policy_id', '=', policy_id)])
            if insurance_count > 0:
                result = {
                    'success': False,
                    'error': f'Cannot delete policy that is used in {insurance_count} insurance records'
                }
                response = Response(json.dumps(result), content_type='application/json', status=400)
                return self._add_cors_headers(response)
            
            # Delete policy
            policy.unlink()
            
            result = {
                'success': True,
                'message': 'Insurance policy deleted successfully'
            }
            
            response = Response(json.dumps(result), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)
    
    # HR Insurance Records API
    @http.route('/api/hr/insurance', type='http', auth='public', methods=['GET'], csrf=False)
    def get_insurances(self, **kw):
        """Get all insurance records"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Get query parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'date_from desc, id desc')
            
            # Create domain filters
            domain = []
            if kw.get('state'):
                domain.append(('state', '=', kw.get('state')))
            if kw.get('insurance_type'):
                domain.append(('insurance_type', '=', kw.get('insurance_type')))
            if kw.get('policy_id'):
                domain.append(('policy_id', '=', int(kw.get('policy_id'))))
            if kw.get('company_id'):
                domain.append(('company_id', '=', int(kw.get('company_id'))))
            if kw.get('is_social_insurance') is not None:
                domain.append(('is_social_insurance', '=', kw.get('is_social_insurance') == 'true'))
            
            # Get data from model
            fields_to_get = [
                'id', 'name', 'employee_id', 'policy_id', 'insurance_type', 
                'insurance_coverage_type', 'is_voluntary', 'policy_number', 
                'social_insurance_code', 'date_from', 'date_to', 'amount', 
                'sum_insured', 'is_social_insurance', 'wage_base', 'allowances', 
                'salary_base', 'employee_contribution', 'company_contribution', 
                'total_contribution', 'policy_coverage', 'state', 'notes', 
                'company_id'
            ]
            
            insurances = request.env['hr.insurance'].sudo().search_read(
                domain=domain,
                fields=fields_to_get,
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(insurances),
                'data': insurances
            }
            
            response = Response(json.dumps(result, default=str), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)
    
    @http.route('/api/hr/insurance/<int:insurance_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_insurance(self, insurance_id, **kw):
        """Get a specific insurance record by ID"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Get insurance record
            fields_to_get = [
                'id', 'name', 'employee_id', 'policy_id', 'insurance_type', 
                'insurance_coverage_type', 'is_voluntary', 'policy_number', 
                'social_insurance_code', 'date_from', 'date_to', 'amount', 
                'sum_insured', 'is_social_insurance', 'wage_base', 'allowances', 
                'salary_base', 'employee_contribution', 'company_contribution', 
                'total_contribution', 'policy_coverage', 'state', 'notes', 
                'company_id', 'allowance_ids'
            ]
            
            insurance = request.env['hr.insurance'].sudo().search_read(
                domain=[('id', '=', insurance_id)],
                fields=fields_to_get,
                limit=1
            )
            
            if not insurance:
                result = {
                    'success': False,
                    'error': f'Insurance record not found with ID {insurance_id}'
                }
                response = Response(json.dumps(result), content_type='application/json', status=404)
                return self._add_cors_headers(response)
            
            # Get policy details
            if insurance[0]['policy_id']:
                policy = request.env['insurance.policy'].sudo().search_read(
                    domain=[('id', '=', insurance[0]['policy_id'][0])],
                    fields=['name', 'policy_type', 'coverage_type', 'employee_rate', 'company_rate'],
                    limit=1
                )
                insurance[0]['policy_details'] = policy[0] if policy else {}
            
            # Get allowances if any
            if insurance[0]['allowance_ids']:
                allowances = request.env['insurance.allowance'].sudo().search_read(
                    domain=[('id', 'in', insurance[0]['allowance_ids'])],
                    fields=['id', 'name', 'allowance_type', 'date', 'amount', 'state'],
                )
                insurance[0]['allowances'] = allowances
            
            result = {
                'success': True,
                'data': insurance[0]
            }
            
            response = Response(json.dumps(result, default=str), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)
    
    @http.route('/api/hr/insurance/employee/<int:employee_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_insurances(self, employee_id, **kw):
        """Get all insurance records for a specific employee"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Check if employee exists
            employee = request.env['hr.employee'].sudo().browse(employee_id)
            if not employee.exists():
                result = {
                    'success': False,
                    'error': f'Employee not found with ID {employee_id}'
                }
                response = Response(json.dumps(result), content_type='application/json', status=404)
                return self._add_cors_headers(response)
            
            # Get query parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'date_from desc, id desc')
            
            # Create domain filters
            domain = [('employee_id', '=', employee_id)]
            if kw.get('state'):
                domain.append(('state', '=', kw.get('state')))
            if kw.get('insurance_type'):
                domain.append(('insurance_type', '=', kw.get('insurance_type')))
            if kw.get('active_only') == 'true':
                domain.append(('state', '=', 'active'))
            
            # Get data from model
            fields_to_get = [
                'id', 'name', 'policy_id', 'insurance_type', 
                'insurance_coverage_type', 'policy_number', 
                'social_insurance_code', 'date_from', 'date_to', 
                'sum_insured', 'salary_base', 'employee_contribution', 
                'company_contribution', 'total_contribution', 'state'
            ]
            
            insurances = request.env['hr.insurance'].sudo().search_read(
                domain=domain,
                fields=fields_to_get,
                limit=limit,
                offset=offset,
                order=order
            )
            
            # Add policy names
            for insurance in insurances:
                if insurance['policy_id']:
                    policy = request.env['insurance.policy'].sudo().browse(insurance['policy_id'][0])
                    insurance['policy_name'] = policy.name
            
            result = {
                'success': True,
                'count': len(insurances),
                'data': insurances
            }
            
            response = Response(json.dumps(result, default=str), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)
    
    @http.route('/api/hr/insurance', type='json', auth='public', methods=['POST'], csrf=False)
    def create_insurance(self, **kw):
        """Create a new insurance record"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Required fields
            required_fields = ['employee_id', 'policy_id', 'insurance_type', 'date_from', 'salary_base', 'sum_insured']
            for field in required_fields:
                if field not in kw:
                    return {
                        'success': False,
                        'error': f"Field '{field}' is required"
                    }
            
            # Create new insurance record
            values = {
                'employee_id': kw.get('employee_id'),
                'policy_id': kw.get('policy_id'),
                'insurance_type': kw.get('insurance_type'),
                'date_from': kw.get('date_from'),
                'salary_base': kw.get('salary_base'),
                'sum_insured': kw.get('sum_insured')
            }
            
            # Optional fields
            optional_fields = [
                'insurance_coverage_type', 'is_voluntary', 'policy_number', 
                'social_insurance_code', 'date_to', 'amount', 'wage_base', 
                'allowances', 'policy_coverage', 'state', 'notes', 'company_id'
            ]
            
            for field in optional_fields:
                if field in kw:
                    values[field] = kw.get(field)
            
            # Create record
            new_insurance = request.env['hr.insurance'].sudo().create(values)
            
            return {
                'success': True,
                'id': new_insurance.id,
                'name': new_insurance.name,
                'message': 'Insurance record created successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/hr/insurance/<int:insurance_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_insurance(self, insurance_id, **kw):
        """Update an existing insurance record"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Find insurance record
            insurance = request.env['hr.insurance'].sudo().browse(insurance_id)
            if not insurance.exists():
                return {
                    'success': False,
                    'error': f'Insurance record not found with ID {insurance_id}'
                }
            
            # Update fields
            values = {}
            updateable_fields = [
                'policy_id', 'insurance_type', 'insurance_coverage_type',
                'is_voluntary', 'policy_number', 'social_insurance_code',
                'date_from', 'date_to', 'amount', 'sum_insured', 'wage_base',
                'allowances', 'salary_base', 'policy_coverage', 'notes'
            ]
            
            for field in updateable_fields:
                if field in kw:
                    values[field] = kw.get(field)
            
            # Update state if provided
            if 'state' in kw:
                state = kw.get('state')
                if state == 'active':
                    insurance.action_confirm()
                elif state == 'expired':
                    insurance.action_expire()
                elif state == 'cancelled':
                    insurance.action_cancel()
                elif state == 'draft':
                    insurance.action_draft()
            else:
                # Direct update of fields
                insurance.write(values)
            
            return {
                'success': True,
                'id': insurance.id,
                'message': 'Insurance record updated successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/hr/insurance/<int:insurance_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_insurance(self, insurance_id, **kw):
        """Delete an insurance record"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Find insurance record
            insurance = request.env['hr.insurance'].sudo().browse(insurance_id)
            if not insurance.exists():
                result = {
                    'success': False,
                    'error': f'Insurance record not found with ID {insurance_id}'
                }
                response = Response(json.dumps(result), content_type='application/json', status=404)
                return self._add_cors_headers(response)
            
            # Check if insurance has allowances
            if insurance.allowance_ids:
                result = {
                    'success': False,
                    'error': f'Cannot delete insurance that has allowances. Delete the allowances first.'
                }
                response = Response(json.dumps(result), content_type='application/json', status=400)
                return self._add_cors_headers(response)
            
            # Delete insurance
            insurance.unlink()
            
            result = {
                'success': True,
                'message': 'Insurance record deleted successfully'
            }
            
            response = Response(json.dumps(result), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)
    
    # Social Insurance Documents API
    @http.route('/api/hr/insurance/documents', type='http', auth='public', methods=['GET'], csrf=False)
    def get_insurance_documents(self, **kw):
        """Get all social insurance documents"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Get query parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'date desc, id desc')
            
            # Create domain filters
            domain = []
            if kw.get('state'):
                domain.append(('state', '=', kw.get('state')))
            if kw.get('document_type'):
                domain.append(('document_type', '=', kw.get('document_type')))
            if kw.get('adjustment_type'):
                domain.append(('adjustment_type', '=', kw.get('adjustment_type')))
            if kw.get('insurance_id'):
                domain.append(('insurance_id', '=', int(kw.get('insurance_id'))))
            if kw.get('company_id'):
                domain.append(('company_id', '=', int(kw.get('company_id'))))
            
            # Get data from model
            fields_to_get = [
                'id', 'name', 'employee_id', 'insurance_id', 'document_type', 
                'adjustment_type', 'reference', 'date', 'deadline', 'submit_date', 
                'approval_date', 'bhyt_number', 'bhyt_issue_date', 'bhyt_expiry_date', 
                'bhyt_hospital', 'is_bhyt_expired', 'days_to_expire', 
                'bhxh_book_number', 'bhxh_book_issue_date', 'bhxh_book_issue_place', 
                'notes', 'state', 'officer_id', 'old_value', 'new_value', 
                'agency_response', 'agency_officer', 'company_id'
            ]
            
            documents = request.env['social.insurance.document'].sudo().search_read(
                domain=domain,
                fields=fields_to_get,
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(documents),
                'data': documents
            }
            
            response = Response(json.dumps(result, default=str), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)
    
    @http.route('/api/hr/insurance/documents/<int:document_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_insurance_document(self, document_id, **kw):
        """Get a specific social insurance document by ID"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Get document
            fields_to_get = [
                'id', 'name', 'employee_id', 'insurance_id', 'document_type', 
                'adjustment_type', 'reference', 'date', 'deadline', 'submit_date', 
                'approval_date', 'bhyt_number', 'bhyt_issue_date', 'bhyt_expiry_date', 
                'bhyt_hospital', 'is_bhyt_expired', 'days_to_expire', 
                'bhxh_book_number', 'bhxh_book_issue_date', 'bhxh_book_issue_place', 
                'notes', 'state', 'officer_id', 'old_value', 'new_value', 
                'agency_response', 'agency_officer', 'company_id', 'attachment_ids'
            ]
            
            document = request.env['social.insurance.document'].sudo().search_read(
                domain=[('id', '=', document_id)],
                fields=fields_to_get,
                limit=1
            )
            
            if not document:
                result = {
                    'success': False,
                    'error': f'Social insurance document not found with ID {document_id}'
                }
                response = Response(json.dumps(result), content_type='application/json', status=404)
                return self._add_cors_headers(response)
            
            # Get attachment details if any
            if document[0]['attachment_ids']:
                attachments = request.env['ir.attachment'].sudo().search_read(
                    domain=[('id', 'in', document[0]['attachment_ids'])],
                    fields=['id', 'name', 'mimetype', 'create_date'],
                )
                document[0]['attachments'] = attachments
            
            result = {
                'success': True,
                'data': document[0]
            }
            
            response = Response(json.dumps(result, default=str), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)
    
    @http.route('/api/hr/insurance/documents/employee/<int:employee_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_insurance_documents(self, employee_id, **kw):
        """Get all social insurance documents for a specific employee"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Check if employee exists
            employee = request.env['hr.employee'].sudo().browse(employee_id)
            if not employee.exists():
                result = {
                    'success': False,
                    'error': f'Employee not found with ID {employee_id}'
                }
                response = Response(json.dumps(result), content_type='application/json', status=404)
                return self._add_cors_headers(response)
            
            # Get query parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'date desc, id desc')
            
            # Create domain filters
            domain = [('employee_id', '=', employee_id)]
            if kw.get('state'):
                domain.append(('state', '=', kw.get('state')))
            if kw.get('document_type'):
                domain.append(('document_type', '=', kw.get('document_type')))
            
            # Get data from model
            fields_to_get = [
                'id', 'name', 'document_type', 'reference', 'date', 
                'deadline', 'submit_date', 'approval_date', 'state'
            ]
            
            documents = request.env['social.insurance.document'].sudo().search_read(
                domain=domain,
                fields=fields_to_get,
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(documents),
                'data': documents
            }
            
            response = Response(json.dumps(result, default=str), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)
    
    @http.route('/api/hr/insurance/documents', type='json', auth='public', methods=['POST'], csrf=False)
    def create_insurance_document(self, **kw):
        """Create a new social insurance document"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Required fields
            required_fields = ['employee_id', 'document_type', 'date']
            for field in required_fields:
                if field not in kw:
                    return {
                        'success': False,
                        'error': f"Field '{field}' is required"
                    }
            
            # Create new document
            values = {
                'employee_id': kw.get('employee_id'),
                'document_type': kw.get('document_type'),
                'date': kw.get('date')
            }
            
            # Optional fields
            optional_fields = [
                'insurance_id', 'adjustment_type', 'reference', 'deadline', 
                'submit_date', 'approval_date', 'bhyt_number', 'bhyt_issue_date', 
                'bhyt_expiry_date', 'bhyt_hospital', 'bhxh_book_number', 
                'bhxh_book_issue_date', 'bhxh_book_issue_place', 'notes', 
                'state', 'officer_id', 'old_value', 'new_value', 
                'agency_response', 'agency_officer', 'company_id'
            ]
            
            for field in optional_fields:
                if field in kw:
                    values[field] = kw.get(field)
            
            # Handle attachments if any
            if 'attachment_ids' in kw and kw.get('attachment_ids'):
                values['attachment_ids'] = [(6, 0, kw.get('attachment_ids'))]
            
            # Create record
            new_document = request.env['social.insurance.document'].sudo().create(values)
            
            return {
                'success': True,
                'id': new_document.id,
                'name': new_document.name,
                'message': 'Social insurance document created successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/hr/insurance/documents/<int:document_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_insurance_document(self, document_id, **kw):
        """Update an existing social insurance document"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Find document
            document = request.env['social.insurance.document'].sudo().browse(document_id)
            if not document.exists():
                return {
                    'success': False,
                    'error': f'Social insurance document not found with ID {document_id}'
                }
            
            # Update fields
            values = {}
            updateable_fields = [
                'insurance_id', 'document_type', 'adjustment_type', 'reference', 
                'date', 'deadline', 'submit_date', 'approval_date', 'bhyt_number', 
                'bhyt_issue_date', 'bhyt_expiry_date', 'bhyt_hospital', 
                'bhxh_book_number', 'bhxh_book_issue_date', 'bhxh_book_issue_place', 
                'notes', 'officer_id', 'old_value', 'new_value', 
                'agency_response', 'agency_officer'
            ]
            
            for field in updateable_fields:
                if field in kw:
                    values[field] = kw.get(field)
            
            # Handle attachments if any
            if 'attachment_ids' in kw and kw.get('attachment_ids'):
                values['attachment_ids'] = [(6, 0, kw.get('attachment_ids'))]
            
            # Update state if provided
            if 'state' in kw:
                state = kw.get('state')
                if state == 'submitted':
                    document.action_submit()
                elif state == 'approved':
                    document.action_approve()
                elif state == 'rejected':
                    document.action_reject()
                elif state == 'cancelled':
                    document.action_cancel()
                elif state == 'draft':
                    document.action_draft()
            else:
                # Direct update of fields
                document.write(values)
            
            return {
                'success': True,
                'id': document.id,
                'message': 'Social insurance document updated successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/hr/insurance/documents/<int:document_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_insurance_document(self, document_id, **kw):
        """Delete a social insurance document"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = Response(json.dumps(result), content_type='application/json', status=401)
                return self._add_cors_headers(response)
            
            # Find document
            document = request.env['social.insurance.document'].sudo().browse(document_id)
            if not document.exists():
                result = {
                    'success': False,
                    'error': f'Social insurance document not found with ID {document_id}'
                }
                response = Response(json.dumps(result), content_type='application/json', status=404)
                return self._add_cors_headers(response)
            
            # Only allow deletion in draft or cancelled state
            if document.state not in ['draft', 'cancelled']:
                result = {
                    'success': False,
                    'error': f'Cannot delete document in {document.state} state. Change to draft or cancelled first.'
                }
                response = Response(json.dumps(result), content_type='application/json', status=400)
                return self._add_cors_headers(response)
            
            # Delete document
            document.unlink()
            
            result = {
                'success': True,
                'message': 'Social insurance document deleted successfully'
            }
            
            response = Response(json.dumps(result), content_type='application/json')
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            response = Response(json.dumps(result), content_type='application/json', status=500)
            return self._add_cors_headers(response)
    
    @http.route('/api/hr/insurance/documents/<int:document_id>/submit', type='http', auth='public', methods=['POST'], csrf=False)
    def submit_insurance_document(self, document_id, **kw):
        """Submit a social insurance document"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Find document
            document = request.env['social.insurance.document'].sudo().browse(document_id)
            if not document.exists():
                return {
                    'success': False,
                    'error': f'Social insurance document not found with ID {document_id}'
                }
            
            # Check if document is in draft state
            if document.state != 'draft':
                return {
                    'success': False,
                    'error': f'Document cannot be submitted in {document.state} state'
                }
            
            # Submit document
            document.action_submit()
            
            return {
                'success': True,
                'id': document.id,
                'state': document.state,
                'submit_date': document.submit_date,
                'message': 'Social insurance document submitted successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/hr/insurance/documents/<int:document_id>/approve', type='http', auth='public', methods=['POST'], csrf=False)
    def approve_insurance_document(self, document_id, **kw):
        """Approve a social insurance document"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Find document
            document = request.env['social.insurance.document'].sudo().browse(document_id)
            if not document.exists():
                return {
                    'success': False,
                    'error': f'Social insurance document not found with ID {document_id}'
                }
            
            # Check if document is in submitted state
            if document.state != 'submitted':
                return {
                    'success': False,
                    'error': f'Document cannot be approved in {document.state} state'
                }
            
            # Approve document
            document.action_approve()
            
            return {
                'success': True,
                'id': document.id,
                'state': document.state,
                'approval_date': document.approval_date,
                'message': 'Social insurance document approved successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/hr/insurance/documents/<int:document_id>/reject', type='http', auth='public', methods=['POST'], csrf=False)
    def reject_insurance_document(self, document_id, **kw):
        """Reject a social insurance document"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Find document
            document = request.env['social.insurance.document'].sudo().browse(document_id)
            if not document.exists():
                return {
                    'success': False,
                    'error': f'Social insurance document not found with ID {document_id}'
                }
            
            # Check if document is in submitted state
            if document.state != 'submitted':
                return {
                    'success': False,
                    'error': f'Document cannot be rejected in {document.state} state'
                }
            
            # Add agency response if provided
            if 'agency_response' in kw:
                document.write({'agency_response': kw.get('agency_response')})
            
            # Reject document
            document.action_reject()
            
            return {
                'success': True,
                'id': document.id,
                'state': document.state,
                'message': 'Social insurance document rejected successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/hr/insurance/documents/<int:document_id>/generate_form', type='http', auth='public', methods=['POST'], csrf=False)
    def generate_document_form(self, document_id, **kw):
        """Generate form for a social insurance document"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Find document
            document = request.env['social.insurance.document'].sudo().browse(document_id)
            if not document.exists():
                return {
                    'success': False,
                    'error': f'Social insurance document not found with ID {document_id}'
                }
            
            # Generate form
            result = document.action_generate_form()
            
            if result:
                return {
                    'success': True,
                    'report_action': result,
                    'message': 'Social insurance document form generated successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to generate form'
                }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            } 