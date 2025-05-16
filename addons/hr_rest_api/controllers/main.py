from odoo import http
from odoo.http import request, Response
import json
from werkzeug.exceptions import BadRequest


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
    
    