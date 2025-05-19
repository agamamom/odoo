from odoo import http
from odoo.http import request, Response
import json
from werkzeug.exceptions import BadRequest, NotFound
from odoo import fields
import datetime
import io
from PIL import Image
import base64
import numpy as np
import face_recognition


class HrRestApiController(http.Controller):
    
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
    
    def _handle_request(self, model, fields, domain=None, limit=100, offset=0, order=None):
        """Common method to handle API requests"""
        try:
            if domain is None:
                domain = []
                
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
                
            # Get data from the model
            records = request.env[model].sudo().search_read(
                domain=domain,
                fields=fields,
                limit=limit,
                offset=offset,
                order=order
            )
            
            return {
                'success': True,
                'count': len(records),
                'data': records
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _handle_create(self, model, data):
        """Common method to handle create requests"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
                
            # Create record
            record = request.env[model].sudo().create(data)
            
            return {
                'success': True,
                'id': record.id,
                'message': f'Record created successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _handle_update(self, model, record_id, data):
        """Common method to handle update requests"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
                
            # Update record
            record = request.env[model].sudo().browse(record_id)
            if not record.exists():
                return {
                    'success': False,
                    'error': f'Record not found with ID {record_id}'
                }
                
            record.write(data)
            
            return {
                'success': True,
                'id': record.id,
                'message': f'Record updated successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _handle_delete(self, model, record_id):
        """Common method to handle delete requests"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
                
            # Delete record
            record = request.env[model].sudo().browse(record_id)
            if not record.exists():
                return {
                    'success': False,
                    'error': f'Record not found with ID {record_id}'
                }
                
            record.unlink()
            
            return {
                'success': True,
                'message': f'Record deleted successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _json_serializable(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: self._json_serializable(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._json_serializable(v) for v in obj]
        return obj
    
    # CORS preflight OPTIONS handling for each route pattern
    @http.route(['/api/hr/employees', '/api/hr/employees/<int:employee_id>'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_employees(self, **kw):
        """Handle OPTIONS request for employees endpoints"""
        return self._handle_options_request()
    
    @http.route(['/api/hr/employees', '/api/hr/employees/<int:department_id>'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_department_employees(self, **kw):
        """Handle OPTIONS request for employees endpoints"""
        return self._handle_options_request()

    @http.route(['/api/hr/departments', '/api/hr/departments/<int:department_id>'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_departments(self, **kw):
        """Handle OPTIONS request for departments endpoints"""
        return self._handle_options_request()
    
    @http.route(['/api/hr/jobs', '/api/hr/jobs/<int:job_id>'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_jobs(self, **kw):
        """Handle OPTIONS request for jobs endpoints"""
        return self._handle_options_request()
    
    @http.route(['/api/hr/employee_categories'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_employee_categories(self, **kw):
        """Handle OPTIONS request for employee categories endpoints"""
        return self._handle_options_request()
    
    @http.route(['/api/hr/work_locations'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_work_locations(self, **kw):
        """Handle OPTIONS request for work locations endpoints"""
        return self._handle_options_request()
    
    @http.route(['/api/hr/departure_reasons'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_departure_reasons(self, **kw):
        """Handle OPTIONS request for departure reasons endpoints"""
        return self._handle_options_request()
    
    @http.route(['/api/hr/resource_calendars'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_resource_calendars(self, **kw):
        """Handle OPTIONS request for resource calendars endpoints"""
        return self._handle_options_request()
    
    @http.route(['/api/hr/employees/department/<int:department_id>'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_employees_by_department(self, **kw):
        """Handle OPTIONS request for employees by department endpoint"""
        return self._handle_options_request()
    
    @http.route(['/api/hr/companies', '/api/hr/companies/<int:company_id>'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_companies(self, **kw):
        """Handle OPTIONS request for companies endpoints"""
        return self._handle_options_request()
    
    @http.route(['/api/hr/companies/<int:company_id>/statistics'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_company_statistics(self, **kw):
        """Handle OPTIONS request for company statistics endpoint"""
        return self._handle_options_request()
    
    @http.route(['/api/hr/attendances', '/api/hr/attendances/<int:attendance_id>', '/api/hr/attendances/kiosk_url', '/api/hr/attendances/has_demo_data'], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_attendances(self, **kw):
        """Handle OPTIONS request for attendances endpoints"""
        return self._handle_options_request()
    
    # Employee endpoints
    @http.route('/api/hr/employees', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employees(self, **kw):
        """Get list of employees"""
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'id')
        
        fields = [
            'id', 'name', 'job_title', 'department_id', 'work_phone', 
            'mobile_phone', 'work_email', 'job_id', 'address_id',
            'work_location_id', 'parent_id', 'coach_id', 'category_ids',
            'resource_calendar_id', 'company_id', 'active'
        ]
        
        result = self._handle_request(
            model='hr.employee',
            fields=fields,
            limit=limit,
            offset=offset,
            order=order
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/employees/<int:employee_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee(self, employee_id, **kw):
        """Get employee by ID"""
        fields = [
            'id', 'name', 'job_title', 'department_id', 'work_phone', 
            'mobile_phone', 'work_email', 'job_id', 'address_id',
            'work_location_id', 'parent_id', 'coach_id', 'category_ids',
            'resource_calendar_id', 'company_id', 'active'
        ]
        
        result = self._handle_request(
            model='hr.employee',
            fields=fields,
            domain=[('id', '=', employee_id)]
        )
        
        if result.get('success') and result.get('count') > 0:
            result['data'] = result['data'][0]
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/employees', type='json', auth='public', methods=['POST'], csrf=False)
    def create_employee(self, **kw):
        """Create a new employee"""
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        
        required_fields = ['name']
        for field in required_fields:
            if field not in data:
                response = request.make_response(
                    json.dumps({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }),
                    headers=[('Content-Type', 'application/json')]
                )
                return self._add_cors_headers(response)
        
        result = self._handle_create(
            model='hr.employee',
            data=data
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/employees/<int:employee_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_employee(self, employee_id, **kw):
        """Update an employee"""
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        
        result = self._handle_update(
            model='hr.employee',
            record_id=employee_id,
            data=data
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/employees/<int:employee_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_employee(self, employee_id, **kw):
        """Delete an employee"""
        result = self._handle_delete(
            model='hr.employee',
            record_id=employee_id
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    # Department endpoints
    @http.route('/api/hr/departments', type='http', auth='public', methods=['GET'], csrf=False)
    def get_departments(self, **kw):
        """Get list of departments"""
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'id')
        
        fields = [
            'id', 'name', 'complete_name', 'active', 'company_id', 
            'parent_id', 'manager_id', 'note', 'color', 'total_employee'
        ]
        
        result = self._handle_request(
            model='hr.department',
            fields=fields,
            limit=limit,
            offset=offset,
            order=order
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/departments/<int:department_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_department(self, department_id, **kw):
        """Get department by ID"""
        fields = [
            'id', 'name', 'complete_name', 'active', 'company_id', 
            'parent_id', 'manager_id', 'note', 'color', 'total_employee'
        ]
        
        result = self._handle_request(
            model='hr.department',
            fields=fields,
            domain=[('id', '=', department_id)]
        )
        
        if result.get('success') and result.get('count') > 0:
            result['data'] = result['data'][0]
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/departments', type='json', auth='public', methods=['POST'], csrf=False)
    def create_department(self, **kw):
        """Create a new department"""
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        
        required_fields = ['name']
        for field in required_fields:
            if field not in data:
                response = request.make_response(
                    json.dumps({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }),
                    headers=[('Content-Type', 'application/json')]
                )
                return self._add_cors_headers(response)
        
        result = self._handle_create(
            model='hr.department',
            data=data
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/departments/<int:department_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_department(self, department_id, **kw):
        """Update a department"""
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        
        result = self._handle_update(
            model='hr.department',
            record_id=department_id,
            data=data
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/departments/<int:department_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_department(self, department_id, **kw):
        """Delete a department"""
        result = self._handle_delete(
            model='hr.department',
            record_id=department_id
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    # Job position endpoints
    @http.route('/api/hr/jobs', type='http', auth='public', methods=['GET'], csrf=False)
    def get_jobs(self, **kw):
        """Get list of job positions"""
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'id')
        
        fields = [
            'id', 'name', 'expected_employees', 'no_of_employee',
            'no_of_recruitment', 'no_of_hired_employee', 'department_id', 
            'description', 'requirements', 'company_id', 'active'
        ]
        
        result = self._handle_request(
            model='hr.job',
            fields=fields,
            limit=limit,
            offset=offset,
            order=order
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/jobs/<int:job_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_job(self, job_id, **kw):
        """Get job position by ID"""
        fields = [
            'id', 'name', 'expected_employees', 'no_of_employee',
            'no_of_recruitment', 'no_of_hired_employee', 'department_id', 
            'description', 'requirements', 'company_id', 'active'
        ]
        
        result = self._handle_request(
            model='hr.job',
            fields=fields,
            domain=[('id', '=', job_id)]
        )
        
        if result.get('success') and result.get('count') > 0:
            result['data'] = result['data'][0]
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/jobs', type='json', auth='public', methods=['POST'], csrf=False)
    def create_job(self, **kw):
        """Create a new job position"""
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        
        required_fields = ['name']
        for field in required_fields:
            if field not in data:
                response = request.make_response(
                    json.dumps({
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }),
                    headers=[('Content-Type', 'application/json')]
                )
                return self._add_cors_headers(response)
        
        result = self._handle_create(
            model='hr.job',
            data=data
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/jobs/<int:job_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_job(self, job_id, **kw):
        """Update a job position"""
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        
        result = self._handle_update(
            model='hr.job',
            record_id=job_id,
            data=data
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/jobs/<int:job_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_job(self, job_id, **kw):
        """Delete a job position"""
        result = self._handle_delete(
            model='hr.job',
            record_id=job_id
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    # Employee categories/tags endpoints
    @http.route('/api/hr/employee_categories', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_categories(self, **kw):
        """Get list of employee categories/tags"""
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'id')
        
        fields = ['id', 'name', 'color']
        
        result = self._handle_request(
            model='hr.employee.category',
            fields=fields,
            limit=limit,
            offset=offset,
            order=order
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    # Work location endpoints
    @http.route('/api/hr/work_locations', type='http', auth='public', methods=['GET'], csrf=False)
    def get_work_locations(self, **kw):
        """Get list of work locations"""
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'id')
        
        fields = ['id', 'name', 'address_id', 'company_id', 'active']
        
        result = self._handle_request(
            model='hr.work.location',
            fields=fields,
            limit=limit,
            offset=offset,
            order=order
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    # Departure reason endpoints
    @http.route('/api/hr/departure_reasons', type='http', auth='public', methods=['GET'], csrf=False)
    def get_departure_reasons(self, **kw):
        """Get list of departure reasons"""
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'id')
        
        fields = ['id', 'name', 'sequence']
        
        result = self._handle_request(
            model='hr.departure.reason',
            fields=fields,
            limit=limit,
            offset=offset,
            order=order
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    # Resource calendar endpoints
    @http.route('/api/hr/resource_calendars', type='http', auth='public', methods=['GET'], csrf=False)
    def get_resource_calendars(self, **kw):
        """Get list of resource calendars (work schedules)"""
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'id')
        
        fields = [
            'id', 'name', 'company_id', 'hours_per_day', 'tz',
            'two_weeks_calendar', 'hours_week'
        ]
        
        result = self._handle_request(
            model='resource.calendar',
            fields=fields,
            limit=limit,
            offset=offset,
            order=order
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)

    # --- BHXH History Endpoints ---
    @http.route('/api/hr/employees/<int:employee_id>/bhxh_histories', type='http', auth='public', methods=['GET'], csrf=False)
    def get_bhxh_histories(self, employee_id, **kw):
        """Get BHXH history for an employee"""
        result = self._handle_request(
            model='hr.employee.bhxh.history',
            fields=['id', 'employee_id', 'action_type', 'date_action', 'status', 'transaction_code', 'file_sent', 'file_response', 'response_note'],
            domain=[('employee_id', '=', employee_id)]
        )
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/employees/<int:employee_id>/bhxh_histories', type='json', auth='public', methods=['POST'], csrf=False)
    def create_bhxh_history(self, employee_id, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        data['employee_id'] = employee_id
        result = self._handle_create('hr.employee.bhxh.history', data)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/bhxh_histories/<int:bhxh_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_bhxh_history(self, bhxh_id, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        result = self._handle_update('hr.employee.bhxh.history', bhxh_id, data)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/bhxh_histories/<int:bhxh_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_bhxh_history(self, bhxh_id, **kw):
        result = self._handle_delete('hr.employee.bhxh.history', bhxh_id)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    # --- Personal Income Tax Endpoints ---
    @http.route('/api/hr/employees/<int:employee_id>/personal_income_taxes', type='http', auth='public', methods=['GET'], csrf=False)
    def get_personal_income_taxes(self, employee_id, **kw):
        result = self._handle_request(
            model='hr.employee.personal.income.tax',
            fields=['id', 'employee_id', 'year', 'total_income', 'self_deduction', 'dependent_deduction', 'taxable_income', 'tax_amount', 'tax_file', 'state'],
            domain=[('employee_id', '=', employee_id)]
        )
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/employees/<int:employee_id>/personal_income_taxes', type='json', auth='public', methods=['POST'], csrf=False)
    def create_personal_income_tax(self, employee_id, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        data['employee_id'] = employee_id
        result = self._handle_create('hr.employee.personal.income.tax', data)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/personal_income_taxes/<int:tax_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_personal_income_tax(self, tax_id, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        result = self._handle_update('hr.employee.personal.income.tax', tax_id, data)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/personal_income_taxes/<int:tax_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_personal_income_tax(self, tax_id, **kw):
        result = self._handle_delete('hr.employee.personal.income.tax', tax_id)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    # --- Project Assignment Endpoints ---
    @http.route('/api/hr/employees/<int:employee_id>/project_assignments', type='http', auth='public', methods=['GET'], csrf=False)
    def get_project_assignments(self, employee_id, **kw):
        result = self._handle_request(
            model='hr.employee.project.assignment',
            fields=['id', 'employee_id', 'project_id', 'role', 'date_start', 'date_end', 'progress', 'performance_score', 'note'],
            domain=[('employee_id', '=', employee_id)]
        )
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/employees/<int:employee_id>/project_assignments', type='json', auth='public', methods=['POST'], csrf=False)
    def create_project_assignment(self, employee_id, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        data['employee_id'] = employee_id
        result = self._handle_create('hr.employee.project.assignment', data)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/project_assignments/<int:assignment_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_project_assignment(self, assignment_id, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        result = self._handle_update('hr.employee.project.assignment', assignment_id, data)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/project_assignments/<int:assignment_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_project_assignment(self, assignment_id, **kw):
        result = self._handle_delete('hr.employee.project.assignment', assignment_id)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    # --- Employee Skill Endpoints ---
    @http.route('/api/hr/employees/<int:employee_id>/skills', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_skills(self, employee_id, **kw):
        result = self._handle_request(
            model='hr.employee.skill',
            fields=['id', 'employee_id', 'skill_name', 'skill_level', 'certificate', 'certificate_issue_date', 'certificate_expiry_date', 'note'],
            domain=[('employee_id', '=', employee_id)]
        )
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/employees/<int:employee_id>/skills', type='json', auth='public', methods=['POST'], csrf=False)
    def create_employee_skill(self, employee_id, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        data['employee_id'] = employee_id
        result = self._handle_create('hr.employee.skill', data)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/skills/<int:skill_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_employee_skill(self, skill_id, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        result = self._handle_update('hr.employee.skill', skill_id, data)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/skills/<int:skill_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_employee_skill(self, skill_id, **kw):
        result = self._handle_delete('hr.employee.skill', skill_id)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    # --- Employee Contract Endpoints ---
    @http.route('/api/hr/employees/<int:employee_id>/contracts', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_contracts(self, employee_id, **kw):
        result = self._handle_request(
            model='hr.employee.contract',
            fields=['id', 'employee_id', 'contract_number', 'sign_date', 'expiry_date', 'contract_type', 'file_scan'],
            domain=[('employee_id', '=', employee_id)]
        )
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/employees/<int:employee_id>/contracts', type='json', auth='public', methods=['POST'], csrf=False)
    def create_employee_contract(self, employee_id, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        data['employee_id'] = employee_id
        result = self._handle_create('hr.employee.contract', data)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/contracts/<int:contract_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_employee_contract(self, contract_id, **kw):
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        result = self._handle_update('hr.employee.contract', contract_id, data)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/contracts/<int:contract_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_employee_contract(self, contract_id, **kw):
        result = self._handle_delete('hr.employee.contract', contract_id)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    # --- Export Employee List Endpoints ---
    @http.route('/api/hr/employees/export/excel', type='http', auth='public', methods=['GET'], csrf=False)
    def export_employee_list_excel(self, **kw):
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        fields_to_export = kw.get('fields')
        if fields_to_export:
            try:
                fields_to_export = json.loads(fields_to_export)
            except Exception:
                fields_to_export = None
        employees = request.env['hr.employee'].sudo().search([])
        filename, file_content = employees.export_employee_list_excel(fields_to_export)
        response = request.make_response(file_content, headers=[('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'), ('Content-Disposition', f'attachment; filename={filename}')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/employees/export/pdf', type='http', auth='public', methods=['GET'], csrf=False)
    def export_employee_list_pdf(self, **kw):
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        fields_to_export = kw.get('fields')
        if fields_to_export:
            try:
                fields_to_export = json.loads(fields_to_export)
            except Exception:
                fields_to_export = None
        employees = request.env['hr.employee'].sudo().search([])
        filename, file_content = employees.export_employee_list_pdf(fields_to_export)
        response = request.make_response(file_content, headers=[('Content-Type', 'application/pdf'), ('Content-Disposition', f'attachment; filename={filename}')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/employees/department/<int:department_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employees_by_department(self, department_id, **kw):
        """Get employees by department"""
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'id')
        fields = [
            'id', 'name', 'job_title', 'department_id', 'work_phone', 
            'mobile_phone', 'work_email', 'job_id', 'address_id',
            'work_location_id', 'parent_id', 'coach_id', 'category_ids',
            'resource_calendar_id', 'company_id', 'active'
        ]
        result = self._handle_request(
            model='hr.employee',
            fields=fields,
            domain=[('department_id', '=', department_id)],
            limit=limit,
            offset=offset,
            order=order
        )
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    # Company endpoints
    @http.route('/api/hr/companies', type='http', auth='public', methods=['GET'], csrf=False)
    def get_companies(self, **kw):
        """Get list of companies with HR-related information"""
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'id')
        
        fields = [
            'id', 'name', 'partner_id', 'currency_id', 'sequence', 'parent_id',
            'child_ids', 'hr_presence_control_email_amount', 'hr_presence_control_ip_list',
            'hr_presence_control_login', 'hr_presence_control_email',
            'hr_presence_control_ip', 'hr_presence_control_attendance',
            'country_id', 'email', 'phone', 'website'
        ]
        
        result = self._handle_request(
            model='res.company',
            fields=fields,
            limit=limit,
            offset=offset,
            order=order
        )
        
        response = request.make_response(
            json.dumps(result),
            headers=[('Content-Type', 'application/json')]
        )
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/companies/<int:company_id>/statistics', type='http', auth='public', methods=['GET'], csrf=False)
    def get_company_statistics(self, company_id, **kw):
        """Get HR statistics for a specific company"""
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        # Check company exists
        company = request.env['res.company'].sudo().browse(company_id)
        if not company.exists():
            result = {
                'success': False,
                'error': f'Company not found with ID {company_id}'
            }
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        # Get statistics
        employees = request.env['hr.employee'].sudo().search([('company_id', '=', company_id)])
        departments = request.env['hr.department'].sudo().search([('company_id', '=', company_id)])
        jobs = request.env['hr.job'].sudo().search([('company_id', '=', company_id)])
        
        # Calculate more statistics
        active_employees = len([e for e in employees if e.active])
        inactive_employees = len(employees) - active_employees
        male_employees = len([e for e in employees if e.gender == 'male'])
        female_employees = len([e for e in employees if e.gender == 'female'])
        other_gender_employees = len([e for e in employees if e.gender == 'other'])
        
        result = {
            'success': True,
            'data': {
                'company_id': company_id,
                'company_name': company.name,
                'total_employees': len(employees),
                'active_employees': active_employees,
                'inactive_employees': inactive_employees,
                'total_departments': len(departments),
                'total_job_positions': len(jobs),
                'gender_distribution': {
                    'male': male_employees,
                    'female': female_employees,
                    'other': other_gender_employees
                }
            }
        }
        
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    # Attendance endpoints
    @http.route('/api/hr/attendances', type='http', auth='public', methods=['GET'], csrf=False)
    def get_attendances(self, **kw):
        """Get list of attendance records"""
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'check_in desc')
        fields = [
            'id', 'employee_id', 'department_id', 'manager_id', 'check_in', 'check_out',
            'worked_hours', 'color', 'overtime_hours', 'overtime_status', 'validated_overtime_hours',
            'no_validated_overtime_hours', 'in_latitude', 'in_longitude', 'in_country_name', 'in_city',
            'in_ip_address', 'in_browser', 'in_mode', 'out_latitude', 'out_longitude', 'out_country_name',
            'out_city', 'out_ip_address', 'out_browser', 'out_mode', 'expected_hours',
            'overtime_wage_coefficient', 'is_within_geofence', 'is_offline', 'face_id_result', 'face_id_timestamp',
            'create_uid', 'create_date', 'write_uid', 'write_date'
        ]
        result = self._handle_request(
            model='hr.attendance',
            fields=fields,
            limit=limit,
            offset=offset,
            order=order
        )
        result = self._json_serializable(result)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/attendances/<int:attendance_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_attendance(self, attendance_id, **kw):
        """Get a specific attendance record by ID"""
        fields = [
            'id', 'employee_id', 'department_id', 'manager_id', 'check_in', 'check_out',
            'worked_hours', 'color', 'overtime_hours', 'overtime_status', 'validated_overtime_hours',
            'no_validated_overtime_hours', 'in_latitude', 'in_longitude', 'in_country_name', 'in_city',
            'in_ip_address', 'in_browser', 'in_mode', 'out_latitude', 'out_longitude', 'out_country_name',
            'out_city', 'out_ip_address', 'out_browser', 'out_mode', 'expected_hours',
            'overtime_wage_coefficient', 'is_within_geofence', 'is_offline', 'face_id_result', 'face_id_timestamp',
            'create_uid', 'create_date', 'write_uid', 'write_date'
        ]
        result = self._handle_request(
            model='hr.attendance',
            fields=fields,
            domain=[('id', '=', attendance_id)]
        )
        if result.get('success') and result.get('count') > 0:
            result['data'] = result['data'][0]
        result = self._json_serializable(result)
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/attendances/kiosk_url', type='http', auth='public', methods=['GET'], csrf=False)
    def get_attendance_kiosk_url(self, **kw):
        """Get the kiosk URL for the current user"""
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        employee = request.env.user.employee_id
        if not employee:
            result = {'success': False, 'error': 'No employee linked to current user'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        kiosk_url = request.env['hr.attendance'].get_kiosk_url()
        result = {'success': True, 'kiosk_url': kiosk_url}
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/attendances/has_demo_data', type='http', auth='public', methods=['GET'], csrf=False)
    def get_attendance_has_demo_data(self, **kw):
        """Check if demo data exists for hr.attendance"""
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        has_demo = request.env['hr.attendance'].has_demo_data()
        result = {'success': True, 'has_demo_data': has_demo}
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/employees/<int:employee_id>/avatar', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_employee_avatar(self, employee_id, **kw):
        """Upload avatar image for an employee, store as ir_attachment (base64 in 'image_base64')"""
        # Validate API key
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Parse input
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        image_base64 = data.get('image_base64')
        if not image_base64:
            result = {'success': False, 'error': 'Missing image_base64 in request body'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Check employee exists
        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists():
            result = {'success': False, 'error': f'Employee not found with ID {employee_id}'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Save image as ir_attachment
        IrAttachment = request.env['ir.attachment'].sudo()
        domain = [
            ('res_model', '=', 'hr.employee'),
            ('res_id', '=', employee_id),
            ('name', '=', 'image_1920')
        ]
        attachment = IrAttachment.search(domain, limit=1)
        vals = {
            'res_model': 'hr.employee',
            'res_id': employee_id,
            'res_field': 'image_1920',
            'name': 'image_1920',
            'type': 'binary',
            'mimetype': 'image/png',  # hoặc xác định từ dữ liệu nếu cần
            'datas': image_base64,
        }
        try:
            if attachment:
                attachment.write(vals)
            else:
                IrAttachment.create(vals)
            result = {'success': True, 'message': 'Avatar image uploaded and saved to ir_attachment successfully'}
        except Exception as e:
            result = {'success': False, 'error': str(e)}
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/employees/<int:employee_id>/avatar', type='json', auth='public', methods=['OPTIONS'], csrf=False)
    def options_employee_avatar(self, employee_id, **kw):
        """Handle OPTIONS request for employee avatar endpoint"""
        return self._handle_options_request()
    
    @http.route('/api/hr/employees/find_by_email', type='http', auth='public', methods=['POST'], csrf=False)
    def find_employee_by_email(self, **kw):
        """Tìm employee theo work_email, trả về id nếu tồn tại"""
        # Validate API key
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Parse input
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        work_email = data.get('work_email')
        if not work_email:
            result = {'success': False, 'error': 'Missing work_email in request body'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Tìm employee theo work_email
        employee = request.env['hr.employee'].sudo().search([('work_email', '=', work_email)], limit=1)
        if employee:
            result = {'success': True, 'employee_id': employee.id}
        else:
            result = {'success': False, 'error': 'No employee found with this work_email'}
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/employees/find_by_email', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_find_employee_by_email(self, **kw):
        """Handle OPTIONS request for find_by_email endpoint"""
        return self._handle_options_request()
    

    #API ROUTE cho phần nhận diện khuôn mặt để chấm công
    @http.route('/api/hr/attendances/face_checkin', type='json', auth='public', methods=['POST'], csrf=False)
    def face_checkin(self, **kw):
        """
        Check-in/out bằng khuôn mặt.
        Body: {
            "image_base64": "data:image/png;base64,..."
        }
        """
        # Validate API key
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest

        image_base64 = data.get('image_base64')
        if not image_base64:
            result = {'success': False, 'error': 'Missing image_base64 in request body'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Giải mã ảnh gửi lên
        if image_base64.startswith('data:image'):
            image_base64 = image_base64.split('base64,')[1]
        try:
            upload_image = base64.b64decode(image_base64)
        except Exception as e:
            result = {'success': False, 'error': f'Invalid base64 image: {str(e)}'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Lấy tất cả nhân viên có ảnh khuôn mặt
        employees = request.env['hr.employee'].sudo().search([('image_1920', '!=', False)])
        matched_employee = None

        def get_face_encoding(image_bytes):
            # Đọc ảnh từ bytes, chuyển sang numpy array
            img = np.array(Image.open(io.BytesIO(image_bytes)))
            encodings = face_recognition.face_encodings(img)
            if encodings:
                return encodings[0]
            return None

        upload_encoding = get_face_encoding(upload_image)
        if upload_encoding is None:
            result = {'success': False, 'error': 'No face found in uploaded image'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        for employee in employees:
            try:
                face_image = base64.b64decode(employee.image_1920)
                employee_encoding = get_face_encoding(face_image)
                if employee_encoding is not None:
                    # So sánh khuôn mặt (distance < 0.6 là trùng)
                    matches = face_recognition.compare_faces([employee_encoding], upload_encoding, tolerance=0.6)
                    if matches[0]:
                        matched_employee = employee
                        break
            except Exception as e:
                continue

        if not matched_employee:
            result = {'success': False, 'error': 'Face not recognized'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Tạo bản ghi chấm công (check-in hoặc check-out)
        attendance = request.env['hr.attendance'].sudo().create({
            'employee_id': matched_employee.id,
            'check_in': fields.Datetime.now(),
            # hoặc 'check_out': fields.Datetime.now() nếu là check-out
        })

        result = {'success': True, 'attendance_id': attendance.id, 'employee_id': matched_employee.id}
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/attendances/face_checkin', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_face_checkin(self, **kw):
        """Handle OPTIONS request for face_checkin endpoint"""
        return self._handle_options_request()

    @http.route('/api/hr/attendances/confirm', type='json', auth='public', methods=['POST'], csrf=False)
    def confirm_attendance(self, **kw):
        """
        Xác nhận đã nhận diện khuôn mặt thành công từ client.
        Body: {
            "employee_id": 123,
            "action": "check_in",  // hoặc "check_out"
            // Các trường bổ sung (tùy chọn):
            // "in_latitude", "in_longitude", "in_country_name", "in_city", "in_ip_address", "in_browser", ...
            // "out_latitude", "out_longitude", ...
            // "face_id_result", "is_within_geofence", "is_offline", "company_id", ...
        }
        """
        # Validate API key
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest

        employee_id = data.get('employee_id')
        action = data.get('action', 'check_in')
        if not employee_id:
            result = {'success': False, 'error': 'Missing employee_id'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Lấy thông tin bổ sung từ request hoặc client gửi lên
        ip_address = data.get('in_ip_address') or request.httprequest.remote_addr
        browser = data.get('in_browser') or request.httprequest.user_agent.string if hasattr(request.httprequest, 'user_agent') else None
        latitude = data.get('in_latitude')
        longitude = data.get('in_longitude')
        country_name = data.get('in_country_name')
        city = data.get('in_city')
        face_id_result = data.get('face_id_result', 'success')
        is_within_geofence = data.get('is_within_geofence')
        is_offline = data.get('is_offline')
        company_id = data.get('company_id')
        face_id_timestamp = fields.Datetime.now()

        vals = {
            'employee_id': employee_id,
            'face_id_result': face_id_result,
            'face_id_timestamp': face_id_timestamp,
            'in_ip_address': ip_address,
            'in_browser': browser,
            'in_latitude': latitude,
            'in_longitude': longitude,
            'in_country_name': country_name,
            'in_city': city,
            'is_within_geofence': is_within_geofence,
            'is_offline': is_offline,
            'company_id': company_id,
        }
        if action == 'check_in':
            vals['check_in'] = fields.Datetime.now()
            # Nếu có thông tin out_* thì cũng lưu
            for k in ['out_latitude', 'out_longitude', 'out_country_name', 'out_city', 'out_ip_address', 'out_browser', 'out_mode']:
                if data.get(k):
                    vals[k] = data.get(k)
        elif action == 'check_out':
            vals['check_out'] = fields.Datetime.now()
            # Nếu có thông tin out_* thì cũng lưu
            for k in ['out_latitude', 'out_longitude', 'out_country_name', 'out_city', 'out_ip_address', 'out_browser', 'out_mode']:
                if data.get(k):
                    vals[k] = data.get(k)
        else:
            result = {'success': False, 'error': 'Invalid action'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        attendance = request.env['hr.attendance'].sudo().create(vals)
        result = {'success': True, 'attendance_id': attendance.id}
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/attendances/confirm', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_attendance_confirm(self, **kw):
        """Handle OPTIONS request for attendance confirm endpoint"""
        return self._handle_options_request()

    @http.route('/api/hr/employees/<int:employee_id>/image/<string:field_name>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_image(self, employee_id, field_name, **kw):
        """Get employee image by ID and field name directly as binary"""
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists():
            return request.not_found()

        try:
            # Tìm attachment mới nhất dựa vào create_date
            domain = [
                ('res_model', '=', 'hr.employee'),
                ('res_id', '=', employee_id),
                ('res_field', '=', field_name)
            ]
            latest_attachment = request.env['ir.attachment'].sudo().search(
                domain, order='create_date desc', limit=1
            )
            
            if latest_attachment and latest_attachment.datas:
                # Nếu tìm thấy attachment, trả về dữ liệu từ attachment
                image_data = latest_attachment.datas
                content_type = latest_attachment.mimetype or 'image/png'
            else:
                # Nếu không tìm được attachment, thử lấy từ field của employee
                image_data = employee[field_name]
                content_type = 'image/png'
                
            if not image_data:
                return request.not_found()
            
            # Trả về binary image trực tiếp
            response = request.make_response(
                base64.b64decode(image_data), 
                headers=[('Content-Type', content_type)]
            )
            return self._add_cors_headers(response)
        except Exception as e:
            return request.make_response(
                json.dumps({'success': False, 'error': str(e)}), 
                headers=[('Content-Type', 'application/json')]
            )

    @http.route('/api/hr/auth/session', type='http', auth='none', methods=['POST'], csrf=False)
    def get_session_id(self, **kw):
        """
        Authenticate user and return a valid session_id that can be used to access protected resources like images.
        
        Expected JSON body:
        {
            "db": "database_name",
            "login": "user_email",
            "password": "user_password"
        }
        
        Returns session_id that can be used in Cookie header for subsequent requests to /web/image/...
        """
        try:
            # Parse input
            try:
                data = json.loads(request.httprequest.data.decode('utf-8'))
            except Exception:
                data = request.jsonrequest
                
            # Validate required fields
            if not all(key in data for key in ['db', 'login', 'password']):
                result = {'success': False, 'error': 'Missing required fields: db, login, or password'}
                response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
                return self._add_cors_headers(response)
                
            db = data.get('db')
            login = data.get('login')
            password = data.get('password')
            
            # Use Odoo's built-in authentication
            uid = request.session.authenticate(db, login, password)
            
            if not uid:
                result = {'success': False, 'error': 'Authentication failed. Invalid credentials.'}
                response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
                return self._add_cors_headers(response)
                
            # Get current session ID
            session_id = request.session.sid
            
            result = {
                'success': True,
                'uid': uid,
                'session_id': session_id,
                'usage': {
                    'description': 'Use this session_id in Cookie header for requests to protected resources',
                    'example': f'Cookie: session_id={session_id}'
                }
            }
            
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {'success': False, 'error': str(e)}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
    @http.route('/api/hr/auth/session', type='http', auth='none', methods=['OPTIONS'], csrf=False)
    def options_session_auth(self, **kw):
        """Handle OPTIONS request for session authentication endpoint"""
        return self._handle_options_request()