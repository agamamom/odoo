from odoo import http, _
from odoo.http import request, Response
import json
import logging
from werkzeug.exceptions import BadRequest, Forbidden
from werkzeug.wrappers import Response as WerkzeugResponse
from datetime import datetime, timedelta
from odoo import fields
import io
from PIL import Image
import base64
import binascii
import jwt
from odoo.api import Environment


from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)

class HrRestApiController(http.Controller):
    
    def _validate_api_key(self):
        auth_header = request.httprequest.headers.get('Authorization')
        _logger.info(f"Authorization header: {auth_header}")

        if auth_header and auth_header.startswith('Basic '):
            _logger.info("Processing Basic Auth credentials")
            try:
                auth_decoded = base64.b64decode(auth_header[6:].strip()).decode('utf-8')
                login, password = auth_decoded.split(':', 1)
                _logger.info(f"Decoded Basic Auth - login: {login}, password length: {len(password)}")

                user = request.env['res.users'].sudo().search([('login', '=', login)], limit=1)
                if not user:
                    _logger.warning(f"User not found with login: {login}")
                    return False, {"error": "Authentication failed: Invalid login or password"}

                if not user.active:
                    _logger.warning(f"User {login} is not active")
                    return False, {"error": "Authentication failed: User account is inactive"}

                _logger.debug(f"User found: ID={user.id}, Has API access: {user.has_group('base.group_user')}")

                try:
                    db_name = request.env.cr.dbname
                    _logger.info(f"Authenticating with database: {db_name}, login: {login}")
                    
                    # First try the authenticate method with proper parameters
                    try:
                        credential = {
                            'type': 'password',
                            'login': login, 
                            'password': password
                        }
                        user_agent_env = dict(request.httprequest.environ)
                        user_agent_env['interactive'] = False  # Set interactive flag for API usage
                        
                        _logger.info(f"Credential dict: {credential}")
                        
                        auth_info = request.env['res.users'].authenticate(db_name, credential, user_agent_env)
                        _logger.info(f"authenticate returned: {auth_info} (type: {type(auth_info)})")
                        
                        if auth_info and isinstance(auth_info, dict) and 'uid' in auth_info:
                            uid = auth_info['uid']
                            if isinstance(uid, int) and uid > 0:
                                authenticated_user = request.env['res.users'].sudo().browse(uid)
                                _logger.info(f"Basic Auth successful for user: {authenticated_user.login} (using authenticate)")
                                return True, authenticated_user
                            else:
                                _logger.warning(f"authenticate method returned invalid UID: {uid} (type: {type(uid)})")
                                return False, {"error": f"Authentication failed: Invalid UID returned ({uid})"}
                        else:
                            _logger.warning(f"authenticate method returned invalid auth_info: {auth_info}")
                            return False, {"error": "Authentication failed: Invalid authentication response"}
                            
                    except Exception as auth_error:
                        _logger.error(f"authenticate method failed: {str(auth_error)}", exc_info=True)
                        
                        # Fallback: Use direct password verification
                        _logger.info("Trying fallback authentication method")
                        try:
                            # Verify password directly
                            if user.check_password(password):
                                _logger.info(f"Basic Auth successful for user: {user.login} (using fallback)")
                                return True, user
                            else:
                                _logger.warning(f"Password verification failed for user: {login}")
                                return False, {"error": "Authentication failed: Invalid password"}
                        except Exception as fallback_error:
                            _logger.error(f"Fallback authentication failed: {str(fallback_error)}", exc_info=True)
                            return False, {"error": f"Authentication failed: {str(fallback_error)}"}
                            
                except Exception as e:
                    _logger.error(f"General authentication error: {str(e)}", exc_info=True)
                    return False, {"error": f"Authentication error: {str(e)}"}

            except ValueError as ve:
                _logger.warning(f"Basic Auth failed: Invalid format - {str(ve)}")
                return False, {"error": "Authentication failed: Invalid Basic Auth format (should be 'login:password')"}
            except Exception as e:
                _logger.error(f"Basic Auth decoding error: {str(e)}", exc_info=True)
                return False, {"error": f"Authentication error: {str(e)}"}
        
       
        # 1. Handle JWT Authentication
        if auth_header and auth_header.startswith('Bearer '):
            try:
                secret_key = request.env['ir.config_parameter'].sudo().get_param('jwt_secret')
                if not secret_key:
                    _logger.error("JWT secret key not configured in ir.config_parameter")
                    return False, {"error": "Server configuration error: JWT secret key not set"}

                token = auth_header[7:]
                payload = jwt.decode(token, secret_key, algorithms=['HS256'])
                user_id = payload.get('user_id')
                # employee_id = payload.get('employee_id')
                # if not user_id or not employee_id:
                #     _logger.warning("JWT validation failed: Missing user_id or employee_id in payload")
                #     return False, {"error": "Authentication failed: Invalid JWT payload"}
                
                user = request.env['res.users'].sudo().browse(user_id)
                if not user.exists():
                    _logger.warning("JWT validation failed: User ID %s not found", user_id)
                    return False, {"error": "Authentication failed: User not found"}
                
                # employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id), ('id', '=', employee_id)], limit=1)
                # if not employee:
                #     _logger.warning("JWT validation failed: Employee ID %s not found or not linked to user", employee_id)
                #     return False, {"error": "Authentication failed: Invalid employee ID"}
                
                
                return True, user
            except jwt.ExpiredSignatureError:
                _logger.warning("JWT validation failed: Token expired")
                return False, {"error": "Authentication failed: Token expired"}
            except jwt.InvalidTokenError as e:
                _logger.warning("JWT validation failed: %s", str(e))
                return False, {"error": "Authentication failed: Invalid token"}
            except Exception as e:
                _logger.error("JWT authentication error: %s", str(e))
                return False, {"error": f"Authentication error xx: {str(e)}"}

        _logger.warning("Authentication failed: No valid authentication method provided")
        return False, {"error": "Authentication required: missing Authorization header"}

        # Check for X-API-Key first
        # api_key = request.httprequest.headers.get('X-API-Key')
        # if api_key:
        #     try:
        #         if not hasattr(request, 'env') or request.env is None or not isinstance(request.env, Environment):
        #             _logger.error(f"Invalid request.env: type={type(request.env)}, value={request.env}")
        #             return False, {"error": "Internal error: Invalid environment configuration"}

        #         api_key_record = request.env['res.users.apikeys'].sudo().search([('key', '=', api_key)], limit=1)
        #         if not api_key_record:
        #             _logger.warning("API key not found")
        #             return False, {"error": "Authentication failed: Invalid API key"}

        #         user = request.env['res.users'].sudo().browse(api_key_record.user_id.id)
        #         if not user.exists() or not user.active:
        #             _logger.warning(f"User not found or inactive for API key")
        #             return False, {"error": "Authentication failed: User not found or inactive"}

        #         _logger.info(f"API key authentication successful for user: {user.login}")
        #         return True, user
        #     except Exception as e:
        #         _logger.error(f"API key auth error: {str(e)}")
        #         return False, {"error": f"Authentication error: {str(e)}"}

    
    def _add_cors_headers(self, response):
        """Add CORS headers to the response"""
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        response.headers.add('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, X-API-Key')
        return response
    
    def _handle_options_request(self):
        """Handle OPTIONS requests for CORS preflight"""
        response = request.make_response('', headers=[('Content-Type', 'text/plain')])
        return self._add_cors_headers(response)
    
    @http.route('/api/ping', type='http', auth='public', methods=['GET'], csrf=False)
    def ping(self, **kw):
        """Simple ping endpoint to test if the API is running"""
        result = {
            "success": True,
            "message": "Odoo HR REST API is running",
            "timestamp": datetime.now().isoformat(),
        }
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/auth/verify', type='http', auth='public', methods=['GET'], csrf=False)
    def verify_auth(self, **kw):
        """Verify API key and return user information"""
        # Validate API key
        is_valid, result = self._validate_api_key()
        
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Extract user info
        user = result
        user_data = {
            "id": user.id,
            "name": user.name,
            "login": user.login,
            "is_admin": user.has_group('base.group_system'),
            "is_hr_manager": user.has_group('hr.group_hr_manager'),
            "is_hr_user": user.has_group('hr.group_hr_user'),
        }
        
        result = {
            "success": True,
            "auth": "valid",
            "user": user_data
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
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
        # For type='json' routes, kw already contains the parsed JSON data
        data = kw
        if not data:
            return {'success': False, 'error': 'No data provided in request body'}
        
        required_fields = ['name']
        for field in required_fields:
            if field not in data:
                return {'success': False, 'error': f'Missing required field: {field}'}
        
        result = self._handle_create(
            model='hr.employee',
            data=data
        )
        
        return result
    
    @http.route('/api/hr/employees/<int:employee_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_employee(self, employee_id, **kw):
        """Update an employee"""
        # For type='json' routes, kw already contains the parsed JSON data
        data = kw
        if not data:
            return {'success': False, 'error': 'No data provided in request body'}
        
        result = self._handle_update(
            model='hr.employee',
            record_id=employee_id,
            data=data
        )
        
        return result
    
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
        # For type='json' routes, kw already contains the parsed JSON data
        data = kw
        if not data:
            return {'success': False, 'error': 'No data provided in request body'}
        
        required_fields = ['name']
        for field in required_fields:
            if field not in data:
                return {'success': False, 'error': f'Missing required field: {field}'}
        
        result = self._handle_create(
            model='hr.department',
            data=data
        )
        
        return result
    
    @http.route('/api/hr/departments/<int:department_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_department(self, department_id, **kw):
        """Update a department"""
        # For type='json' routes, kw already contains the parsed JSON data
        data = kw
        if not data:
            return {'success': False, 'error': 'No data provided in request body'}
        
        result = self._handle_update(
            model='hr.department',
            record_id=department_id,
            data=data
        )
        
        return result
    
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
        # For type='json' routes, kw already contains the parsed JSON data
        data = kw
        if not data:
            return {'success': False, 'error': 'No data provided in request body'}
        
        required_fields = ['name']
        for field in required_fields:
            if field not in data:
                return {'success': False, 'error': f'Missing required field: {field}'}
        
        result = self._handle_create(
            model='hr.job',
            data=data
        )
        
        return result
    
    @http.route('/api/hr/jobs/<int:job_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_job(self, job_id, **kw):
        """Update a job position"""
        # For type='json' routes, kw already contains the parsed JSON data
        data = kw
        if not data:
            return {'success': False, 'error': 'No data provided in request body'}
        
        result = self._handle_update(
            model='hr.job',
            record_id=job_id,
            data=data
        )
        
        return result
    
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
    
    @http.route('/api/hr/employees/<int:employee_id>/avatar/multi', type='http', auth='public', methods=['POST'], csrf=False)
    def update_employee_avatar_all_sizes(self, employee_id, **kw):
        """
        Update employee avatar for all standard image sizes and store each in ir_attachment
        
        POST with form-data:
        - image: The image file to upload
        
        OR with JSON:
        - image_base64: Base64 encoded image data (can include data:image/png;base64, prefix)
        
        Returns success status and IDs of created attachments
        """
        # Validate API key
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Check employee exists
        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists():
            result = {'success': False, 'error': f'Employee not found with ID {employee_id}'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        # Get image data from request
        image_data = None
        mimetype = 'image/png'  # Default mimetype
        
        # Check if request has files (multipart/form-data)
        if request.httprequest.files and 'image' in request.httprequest.files:
            file = request.httprequest.files['image']
            image_data = file.read()
            mimetype = file.content_type
            # Convert to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        else:
            # Try to get base64 encoded image from JSON body
            try:
                data = json.loads(request.httprequest.data.decode('utf-8'))
            except Exception:
                data = request.jsonrequest or {}
                
            image_base64 = data.get('image_base64', '')
            
            # Remove data URI prefix if present
            if image_base64.startswith('data:'):
                # Extract mimetype from data URI if available
                mime_match = image_base64.split(';')[0]
                if mime_match.startswith('data:'):
                    mimetype = mime_match[5:]  # Remove 'data:' prefix
                
                # Remove prefix part before the base64 data
                image_base64 = image_base64.split('base64,')[1]
                
        if not image_base64:
            result = {'success': False, 'error': 'No image data provided'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        try:
            # Process and resize image
            image_sizes = {
                'image_1920': (1920, 1920),
                'image_1024': (1024, 1024),
                'image_512': (512, 512),
                'image_256': (256, 256),
                'image_128': (128, 128)
            }
            
            # Decode base64 image
            original_image_data = base64.b64decode(image_base64)
            
            # Create PIL Image object
            img = Image.open(io.BytesIO(original_image_data))
            
            # Process each image size
            IrAttachment = request.env['ir.attachment'].sudo()
            attachment_ids = {}
            
            for field_name, size in image_sizes.items():
                # Resize image maintaining aspect ratio
                img_copy = img.copy()
                img_copy.thumbnail(size, Image.LANCZOS)
                
                # Convert to binary and base64
                buffer = io.BytesIO()
                img_format = img.format or 'PNG'
                img_copy.save(buffer, format=img_format)
                img_binary = buffer.getvalue()
                img_base64 = base64.b64encode(img_binary).decode('utf-8')
                
                # Check if attachment already exists
                domain = [
                    ('res_model', '=', 'hr.employee'),
                    ('res_id', '=', employee_id),
                    ('res_field', '=', field_name)
                ]
                existing_attachment = IrAttachment.search(domain, limit=1)
                
                # Prepare attachment values
                attachment_vals = {
                    'name': f"{field_name}_{employee.name}",
                    'datas': img_base64,
                    'res_model': 'hr.employee',
                    'res_id': employee_id,
                    'res_field': field_name,
                    'type': 'binary',
                    'mimetype': mimetype
                }
                
                # Update or create attachment
                if existing_attachment:
                    existing_attachment.write(attachment_vals)
                    attachment_ids[field_name] = existing_attachment.id
                else:
                    new_attachment = IrAttachment.create(attachment_vals)
                    attachment_ids[field_name] = new_attachment.id
                    
                # Update employee record with the image
                if field_name == 'image_1920':
                    employee.write({field_name: img_base64})
                
            result = {
                'success': True,
                'message': 'Avatar images updated successfully for all sizes',
                'attachment_ids': attachment_ids
            }
            
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {'success': False, 'error': str(e)}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
    
    @http.route('/api/hr/employees/<int:employee_id>/avatar/multi', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_employee_avatar_all_sizes(self, employee_id, **kw):
        """Handle OPTIONS request for update employee avatar all sizes endpoint"""
        return self._handle_options_request()

    @http.route('/api/hr/employees/find_by_email', type='http', auth='public', methods=['POST'], csrf=False)
    def find_employee_by_email(self, **kw):
        """Find employee by email and generate a JWT token"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()

        # Kiểm tra xác thực
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        # Parse input
        data = {}
        try:
            if request.httprequest.data:
                data = json.loads(request.httprequest.data.decode('utf-8'))
            elif hasattr(request, 'params'):
                data = request.params
        except json.JSONDecodeError:
            result = {'success': False, 'error': 'Invalid JSON data in request body'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        except Exception as e:
            result = {'success': False, 'error': f'Error parsing request data: {str(e)}'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        work_email = data.get('work_email')
        if not work_email:
            result = {'success': False, 'error': 'Missing work_email in request body'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # Tìm employee theo work_email
        employee = request.env['hr.employee'].sudo().search([('work_email', '=', work_email)], limit=1)
        if not employee:
            result = {'success': False, 'error': 'No employee found with this work_email'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Tạo JWT token
        secret_key = request.env['ir.config_parameter'].sudo().get_param('jwt_secret')
        if not secret_key:
            _logger.error("JWT secret key not configured in ir.config_parameter")
            result = {'success': False, 'error': 'Server configuration error: JWT secret key not set'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        try:
            token = jwt.encode({
                'user_id': user.id,
                'employee_id': employee.id,
                'company_id': employee.company_id.id if employee.company_id else None,
                'company_name': employee.company_id.name if employee.company_id else None,
                'exp': datetime.utcnow() + timedelta(hours=1)
            }, secret_key, algorithm='HS256')
        except Exception as e:
            _logger.error("Error generating JWT token: %s", str(e))
            result = {'success': False, 'error': f'Failed to generate token: {str(e)}'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        result = {
            'success': True,
            'token': token
        }
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/hr/employees/find_by_email', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_find_employee_by_email(self, **kw):
        """Handle OPTIONS request for find_by_email endpoint"""
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
            return {'success': False, 'error': user.get('error', 'Authentication failed')}

        # For type='json' routes, Odoo automatically parses the JSON and makes it available in kw
        data = kw
        if not data:
            return {'success': False, 'error': 'No data provided in request body'}

        employee_id = data.get('employee_id')
        action = data.get('action', 'check_in')
        if not employee_id:
            return {'success': False, 'error': 'Missing employee_id'}

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
            return {'success': False, 'error': 'Invalid action'}

        attendance = request.env['hr.attendance'].sudo().create(vals)
        return {'success': True, 'attendance_id': attendance.id}

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
        
        user_id = request.env['res.users'].sudo().search([('id', '=', employee_id)], limit=1)
        if not user_id.exists():
            return request.not_found()

        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user_id.id)], limit=1)
        if not employee.exists():
            return request.not_found()

        try:
            # Tìm attachment mới nhất dựa vào create_date
            domain = [
                ('res_model', '=', 'hr.employee'),
                ('res_id', '=', employee.id),
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

    @http.route('/api/departments/all', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_departments(self, **kw):
        """
        Get all departments information with optional filtering
        
        Optional params:
        - limit: Maximum number of departments to return (default: 100)
        - offset: Number of departments to skip for pagination (default: 0)
        - active: Filter by active status (true/false)
        - parent_id: Filter by parent department ID
        - search: Search term for department name
        - include_employees: Include count and list of employees (true/false, default: false)
        """
        # Validate API key or auth
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Parse parameters
        limit = min(int(kw.get('limit', 100)), 500)  # Cap at 500 records
        offset = int(kw.get('offset', 0))
        include_employees = kw.get('include_employees', 'false').lower() in ['true', '1', 't', 'yes']
        
        # Build domain
        domain = []
        
        # Active filter
        if 'active' in kw:
            active = kw['active'].lower() in ['true', '1', 't', 'yes']
            domain.append(('active', '=', active))
        
        # Parent filter
        if 'parent_id' in kw and kw['parent_id']:
            try:
                parent_id = int(kw['parent_id'])
                if parent_id == 0:
                    # Special case: filter for top-level departments (no parent)
                    domain.append(('parent_id', '=', False))
                else:
                    domain.append(('parent_id', '=', parent_id))
            except ValueError:
                pass
        
        # Name search
        if 'search' in kw and kw['search']:
            domain.append(('name', 'ilike', kw['search']))
        
        # Fetch departments
        try:
            departments = request.env['hr.department'].sudo().search(domain, limit=limit, offset=offset)
            total_count = request.env['hr.department'].sudo().search_count(domain)
            
            # Format department data
            dept_data = []
            for dept in departments:
                # Basic department info
                dept_info = {
                    'id': dept.id,
                    'name': dept.name,
                    'complete_name': dept.complete_name if hasattr(dept, 'complete_name') else dept.name,
                    'active': dept.active,
                    'manager_id': dept.manager_id.id if dept.manager_id else False,
                    'manager_name': dept.manager_id.name if dept.manager_id else "",
                    'parent_id': dept.parent_id.id if dept.parent_id else False,
                    'parent_name': dept.parent_id.name if dept.parent_id else "",
                    'company_id': dept.company_id.id if dept.company_id else False,
                    'company_name': dept.company_id.name if dept.company_id else "",
                    'note': dept.note if hasattr(dept, 'note') else "",
                    'total_employees': len(dept.member_ids) if hasattr(dept, 'member_ids') else 0
                }
                
                # Include employee details if requested
                if include_employees:
                    employees = request.env['hr.employee'].sudo().search([
                        ('department_id', '=', dept.id),
                        ('active', '=', True)
                    ])
                    dept_info['employees'] = [{
                        'id': emp.id,
                        'name': emp.name,
                        'job_title': emp.job_title or "",
                        'work_email': emp.work_email or ""
                    } for emp in employees]
                
                dept_data.append(dept_info)
            
            result = {
                'success': True,
                'count': len(dept_data),
                'total': total_count,
                'departments': dept_data
            }
            
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        except Exception as e:
            import traceback
            _logger.error("Error fetching departments: %s\n%s", str(e), traceback.format_exc())
            
            result = {
                'success': False,
                'error': str(e)
            }
            
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
    
    @http.route('/api/departments/all', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_all_departments(self, **kw):
        """Handle OPTIONS request for departments/all endpoint"""
        return self._handle_options_request()

    @http.route('/api/companies/all', type='http', auth='public', methods=['GET'], csrf=False)
    def get_all_companies(self, **kw):
        """
        Get all companies information for dropdown selection
        
        Optional params:
        - limit: Maximum number of companies to return (default: 100)
        - offset: Number of companies to skip for pagination (default: 0)
        - active: Filter by active status (true/false)
        - search: Search term for company name
        """
        # Parse parameters
        limit = min(int(kw.get('limit', 100)), 500)  # Cap at 500 records
        offset = int(kw.get('offset', 0))
        
        # Build domain
        domain = []
        
        # Active filter
        if 'active' in kw:
            active = kw['active'].lower() in ['true', '1', 't', 'yes']
            domain.append(('active', '=', active))
        
        # Name search
        if 'search' in kw and kw['search']:
            domain.append(('name', 'ilike', kw['search']))
        
        # Fetch companies
        try:
            companies = request.env['res.company'].sudo().search(domain, limit=limit, offset=offset)
            total_count = request.env['res.company'].sudo().search_count(domain)
            
            # Format company data
            company_data = []
            for company in companies:
                company_info = {
                    'id': company.id,
                    'name': company.name,
                    'currency_id': company.currency_id.id if company.currency_id else False,
                    'currency_name': company.currency_id.name if company.currency_id else "",
                    'currency_symbol': company.currency_id.symbol if company.currency_id else "",
                    'email': company.email or "",
                    'phone': company.phone or "",
                    'website': company.website or "",
                    'vat': company.vat or "",
                    'company_registry': company.company_registry if hasattr(company, 'company_registry') else "",
                    'country_id': company.country_id.id if company.country_id else False,
                    'country_name': company.country_id.name if company.country_id else "",
                    'logo_url': f"/web/image/res.company/{company.id}/logo/128x128",
                    'parent_id': company.parent_id.id if company.parent_id else False,
                    'parent_name': company.parent_id.name if company.parent_id else "",
                }
                company_data.append(company_info)
            
            result = {
                'success': True,
                'count': len(company_data),
                'total': total_count,
                'companies': company_data
            }
            
            response = request.make_response(json.dumps(result), 
                                        headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        except Exception as e:
            import traceback
            _logger.error("Error fetching companies: %s\n%s", str(e), traceback.format_exc())
            
            result = {
                'success': False,
                'error': str(e)
            }
            
            response = request.make_response(json.dumps(result), 
                                        headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

    
    @http.route('/api/companies/all', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_all_companies(self, **kw):
        """Handle OPTIONS request for companies/all endpoint"""
        return self._handle_options_request()
    
    @http.route('/api/res_groups_users_rel/find_by_uid', type='http', auth='public', methods=['POST'], csrf=False)
    def find_groups_by_uid(self, **kw):
        """Find group IDs associated with a given user ID (uid) from res_groups_users_rel table"""
        # Parse input
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = request.jsonrequest
        uid = data.get('uid')
        if not uid or not isinstance(uid, int):
            result = {'success': False, 'error': 'Missing or invalid uid in request body'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)

        # # Find groups associated with the user using ORM
        # groups = request.env['res.groups.users.rel'].sudo().search([('uid', 'in', [uid])])
        # if groups:
        #     group_ids = groups.mapped('gid').ids
        #     result = {'success': True, 'group_ids': group_ids}
        # else:
        #     result = {'success': False, 'error': 'No groups found for this user ID'}
        # Direct SQL query on the actual table
        request.env.cr.execute("SELECT gid FROM res_groups_users_rel WHERE uid = %s", (uid,))
        results = request.env.cr.fetchall()
        
        if results:
            group_ids = [row[0] for row in results]
            result = {'success': True, 'group_ids': group_ids}
        else:
            result = {'success': False, 'error': 'No groups found for this user ID'}

        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/res_groups_users_rel/find_by_uid', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_find_groups_by_uid(self, **kw):
        """Handle OPTIONS request for find_by_uid endpoint"""
        return self._handle_options_request()

    @http.route('/api/hr/employees/current/avatar', type='http', auth='public', methods=['GET'], csrf=False)
    def get_current_employee_avatar(self, **kw):
        """Get avatar image as base64 for the current authenticated employee"""
        # Validate API key or session
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the current user
        user = result
        
        # Find the employee record associated with the user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        
        if not employee:
            result = {
                'success': False,
                'error': 'No employee record found for the current user'
            }
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the image field (image_1920 is the full-size image in Odoo)
        if employee.image_1920:
            # The image is already stored as base64 in the database
            image_base64 = employee.image_1920
            
            result = {
                'success': True,
                'image_1920': image_base64,
                'employee_id': employee.id,
                'employee_name': employee.name
            }
        else:
            result = {
                'success': False,
                'error': 'Employee has no avatar image'
            }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/employees/current/avatar', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_current_employee_avatar(self, **kw):
        """Handle OPTIONS request for the avatar endpoint"""
        return self._handle_options_request()

    @http.route('/api/hr/employees/<int:employee_id>/avatar_image', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_avatar_image(self, employee_id, **kw):
        """Get avatar image as binary data for an employee"""
        # Validate API key or session
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(
                json.dumps(result), 
                headers=[('Content-Type', 'application/json')]
            )
            return self._add_cors_headers(response)
        
        # Find the employee record
        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists():
            error_msg = {'success': False, 'error': f'Employee not found with ID {employee_id}'}
            response = request.make_response(
                json.dumps(error_msg),
                headers=[('Content-Type', 'application/json')],
                status=404
            )
            return self._add_cors_headers(response)

        try:
            # First check for avatar_1920 (the high-resolution avatar field)
            image_field = 'avatar_1920'
            
            # Look for the attachment first (might have better quality)
            domain = [
                ('res_model', '=', 'hr.employee'),
                ('res_id', '=', employee_id),
                ('res_field', '=', image_field)
            ]
            
            latest_attachment = request.env['ir.attachment'].sudo().search(
                domain, order='create_date desc', limit=1
            )
            
            if latest_attachment and latest_attachment.datas:
                # If attachment found, use its data
                image_data = latest_attachment.datas
                content_type = latest_attachment.mimetype or 'image/png'
            else:
                # Try employee's avatar fields in order of preference
                if employee.avatar_1920:
                    image_data = employee.avatar_1920
                    content_type = 'image/png'
                elif employee.image_1920:
                    image_data = employee.image_1920
                    content_type = 'image/png'
                else:
                    # No avatar found
                    error_msg = {'success': False, 'error': f'No avatar image found for employee {employee.name} (ID: {employee_id})'}
                    response = request.make_response(
                        json.dumps(error_msg),
                        headers=[('Content-Type', 'application/json')],
                        status=404
                    )
                    return self._add_cors_headers(response)
                
            if not image_data:
                error_msg = {'success': False, 'error': 'Image data is empty or corrupted'}
                response = request.make_response(
                    json.dumps(error_msg),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )
                return self._add_cors_headers(response)
            
            try:
                # Verify that image data is valid base64
                decoded_image = base64.b64decode(image_data)
                if not decoded_image:
                    raise ValueError("Decoded image data is empty")
                    
                # Return the binary image directly
                response = request.make_response(
                    decoded_image, 
                    headers=[('Content-Type', content_type)]
                )
                
                # Add cache control headers to improve performance
                response.headers.add('Cache-Control', 'public, max-age=86400')  # Cache for 24 hours
                
                return self._add_cors_headers(response)
                
            except binascii.Error:
                error_msg = {'success': False, 'error': 'Invalid base64 encoding in image data'}
                response = request.make_response(
                    json.dumps(error_msg),
                    headers=[('Content-Type', 'application/json')],
                    status=500
                )
                return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error fetching employee avatar: %s", str(e))
            error_msg = {
                'success': False, 
                'error': f'Failed to retrieve avatar: {str(e)}',
                'error_type': type(e).__name__
            }
            response = request.make_response(
                json.dumps(error_msg),
                headers=[('Content-Type', 'application/json')],
                status=500
            )
            return self._add_cors_headers(response)

    @http.route('/api/hr/employees/<int:employee_id>/avatar_image', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_employee_avatar_image(self, employee_id, **kw):
        """Handle OPTIONS request for avatar image endpoint"""
        return self._handle_options_request()
    
    @http.route('/api/hr/attendance/employee/<int:employee_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_attendance_records(self, employee_id, **kw):
        """
        Get all attendance records (check-ins and check-outs) for a specific employee
        
        Optional query parameters:
        - limit: Maximum number of records to return (default: 100)
        - offset: Number of records to skip for pagination (default: 0)
        - from_date: Filter records from this date (format: YYYY-MM-DD)
        - to_date: Filter records to this date (format: YYYY-MM-DD)
        - current_date_only: If 'true', only returns records for the current date (default: 'true')
        - sort_by: Field to sort by (default: 'check_in desc')
        
        Note: By default, this endpoint returns only the current day's records.
        Set current_date_only=false to use from_date/to_date filters or to get all records.
        """
        # Validate API key or session
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )
            return self._add_cors_headers(response)
        
        try:
            # Parse parameters
            limit = min(int(kw.get('limit', 100)), 500)  # Cap at 500 records
            offset = int(kw.get('offset', 0))
            sort_by = kw.get('sort_by', 'check_in desc')
            
            # Default to current date filtering if no date parameters are explicitly provided
            has_date_filters = 'from_date' in kw or 'to_date' in kw or 'current_date_only' in kw
            current_date_only = kw.get('current_date_only', 'true' if not has_date_filters else 'false').lower() in ['true', '1', 't', 'yes']
            
            # Build domain for date filtering
            domain = [('employee_id', '=', employee_id)]
            
            # Current date filter takes precedence if specified
            if current_date_only:
                # Get today's date in the user's timezone
                user_tz = request.env.user.tz or 'UTC'
                today = fields.Date.context_today(request.env['hr.attendance'].with_context(tz=user_tz))
                domain.append(('check_in', '>=', fields.Datetime.to_string(datetime.combine(today, datetime.min.time()))))
                domain.append(('check_in', '<=', fields.Datetime.to_string(datetime.combine(today, datetime.max.time()))))
            else:
                # Apply from_date and to_date filters if current_date_only is not set
                if 'from_date' in kw and kw['from_date']:
                    try:
                        from_date = fields.Date.from_string(kw['from_date'])
                        domain.append(('check_in', '>=', datetime.combine(from_date, datetime.min.time())))
                    except ValueError:
                        error_msg = {'success': False, 'error': f"Invalid from_date format: {kw['from_date']}. Use YYYY-MM-DD."}
                        response = request.make_response(
                            json.dumps(error_msg),
                            headers=[('Content-Type', 'application/json')],
                            status=400
                        )
                        return self._add_cors_headers(response)
                        
                if 'to_date' in kw and kw['to_date']:
                    try:
                        to_date = fields.Date.from_string(kw['to_date'])
                        domain.append(('check_in', '<=', datetime.combine(to_date, datetime.max.time())))
                    except ValueError:
                        error_msg = {'success': False, 'error': f"Invalid to_date format: {kw['to_date']}. Use YYYY-MM-DD."}
                        response = request.make_response(
                            json.dumps(error_msg),
                            headers=[('Content-Type', 'application/json')],
                            status=400
                        )
                        return self._add_cors_headers(response)
            
            # Check if employee exists
            employee = request.env['hr.employee'].sudo().browse(employee_id)
            if not employee.exists():
                error_msg = {'success': False, 'error': f'Employee not found with ID {employee_id}'}
                response = request.make_response(
                    json.dumps(error_msg),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )
                return self._add_cors_headers(response)
            
            # Get attendance records
            attendance_records = request.env['hr.attendance'].sudo().search(
                domain,
                limit=limit,
                offset=offset,
                order=sort_by
            )
            
            # Count total records for this employee (for pagination info)
            total_records = request.env['hr.attendance'].sudo().search_count(domain)
            
            # Format records with all relevant information
            attendance_data = []
            for record in attendance_records:
                # Create base record with required fields
                record_data = {
                    'id': record.id,
                    'employee_id': record.employee_id.id,
                    'check_in': record.check_in.isoformat() if record.check_in else None,
                    'check_out': record.check_out.isoformat() if record.check_out else None,
                    'worked_hours': record.worked_hours,
                    'create_date': record.create_date.isoformat() if record.create_date else None,
                    'write_date': record.write_date.isoformat() if record.write_date else None,
                    'company_id': record.company_id.id if record.company_id else None,
                }
                
                # Add all additional fields that exist in the hr.attendance model
                optional_fields = [
                    'overtime_hours', 'overtime_status', 'validated_overtime_hours',
                    'expected_hours', 'overtime_wage_coefficient',
                    'in_latitude', 'in_longitude', 'in_country_name', 'in_city', 'in_ip_address', 
                    'in_browser', 'in_mode',
                    'out_latitude', 'out_longitude', 'out_country_name', 'out_city', 'out_ip_address',
                    'out_browser', 'out_mode',
                    'face_id_result', 'is_within_geofence', 'is_offline', 'face_id_timestamp'
                ]
                
                for field in optional_fields:
                    if hasattr(record, field):
                        value = getattr(record, field)
                        # Handle timestamp fields
                        if field == 'face_id_timestamp' and value:
                            record_data[field] = value.isoformat()
                        else:
                            record_data[field] = value
                
                attendance_data.append(record_data)
            
            # Prepare the response
            result = {
                'success': True,
                'count': len(attendance_data),
                'total': total_records,
                'employee': {
                    'id': employee.id,
                    'name': employee.name,
                    'company_id': employee.company_id.id if employee.company_id else None,
                },
                'filters_applied': {
                    'current_date_only': current_date_only,
                    'from_date': kw.get('from_date') if not current_date_only and 'from_date' in kw else None,
                    'to_date': kw.get('to_date') if not current_date_only and 'to_date' in kw else None,
                },
                'attendance_records': attendance_data,
                'pagination': {
                    'limit': limit,
                    'offset': offset,
                    'total_pages': (total_records + limit - 1) // limit if limit > 0 else 0
                }
            }
            
            response = request.make_response(
                json.dumps(result, default=self._json_serializable),
                headers=[('Content-Type', 'application/json')]
            )
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error fetching attendance records: %s", str(e))
            error_msg = {
                'success': False,
                'error': f'Failed to retrieve attendance records: {str(e)}',
                'error_type': type(e).__name__
            }
            response = request.make_response(
                json.dumps(error_msg),
                headers=[('Content-Type', 'application/json')],
                status=500
            )
            return self._add_cors_headers(response)

    @http.route('/api/hr/attendance/employee/<int:employee_id>', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_employee_attendance_records(self, employee_id, **kw):
        """Handle OPTIONS request for employee attendance records endpoint"""
        return self._handle_options_request()

    @http.route('/api/company/<int:company_id>/location', type='http', auth='public', methods=['GET'], csrf=False)
    def get_company_location(self, company_id, **kw):
        """
        Get longitude and latitude for a specific company
        
        :param company_id: ID of the company
        :return: JSON with company location data
        """
        try:
            # Validate API key or session
            is_valid, result = self._validate_api_key()
            if not is_valid:
                response = request.make_response(
                    json.dumps(result),
                    headers=[('Content-Type', 'application/json')]
                )
                return self._add_cors_headers(response)
                
            # Check if company exists
            company = request.env['res.company'].sudo().browse(company_id)
            if not company.exists():
                result = {
                    "success": False,
                    "error": f"Company with ID {company_id} not found"
                }
                response = request.make_response(
                    json.dumps(result),
                    headers=[('Content-Type', 'application/json')]
                )
                return self._add_cors_headers(response)
                
            # Get location data
            result = {
                "success": True,
                "company_id": company_id,
                "name": company.name,
                "latitude": company.latitude if hasattr(company, 'latitude') else None,
                "longitude": company.longitude if hasattr(company, 'longitude') else None,
            }
            
            response = request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )
            return self._add_cors_headers(response)
            
        except Exception as e:
            result = {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }
            response = request.make_response(
                json.dumps(result),
                headers=[('Content-Type', 'application/json')]
            )
            return self._add_cors_headers(response)

    @http.route('/api/company/<int:company_id>/location', type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_company_location(self, company_id, **kw):
        """Handle OPTIONS request for company location endpoint"""
        return self._handle_options_request()

    def _get_json_data(self):
        """Helper method to safely get JSON data from request
        
        For type='json' routes, data should be available in **kw of the route method.
        For http routes that need to parse JSON manually, this provides a safe way to do so.
        """
        # For type='json' routes, kw will already contain the parsed JSON
        if hasattr(request, 'jsonrequest') and request.jsonrequest:
            return request.jsonrequest
        
        # For type='http' routes, try to parse JSON from the request body
        if request.httprequest.data:
            try:
                return json.loads(request.httprequest.data.decode('utf-8'))
            except json.JSONDecodeError:
                _logger.warning("Invalid JSON data in request body")
        
        # Fallback to form-encoded params
        if hasattr(request, 'params'):
            return request.params
        
        # Last resort, return empty dict
        return {}