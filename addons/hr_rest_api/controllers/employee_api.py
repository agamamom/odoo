from odoo import http, _
from odoo.http import request, Response
from odoo.addons.hr_rest_api.controllers.main import HrRestApiController
import json
import logging
from werkzeug.exceptions import BadRequest, Forbidden
from werkzeug.wrappers import Response as WerkzeugResponse
from datetime import datetime, date
from odoo.tools import DEFAULT_SERVER_DATE_FORMAT
import base64

_logger = logging.getLogger(__name__)

class EmployeeAPIController(HrRestApiController):
    
    def _validate_hr_rights(self, user):
        """Check if the user has HR management rights"""
        return user.has_group('hr.group_hr_manager') or user.has_group('hr.group_hr_user')
    
    # CORS preflight handler for all routes
    @http.route([
        '/api/employees',
        '/api/employees/<int:employee_id>',
        '/api/employees/search',
        '/api/employees/count',
        '/api/employees/departments',
        '/api/employees/job-positions',
        '/api/employees/<int:employee_id>/photo'
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_employee_endpoints(self, **kw):
        """Handle OPTIONS requests for CORS preflight"""
        return self._handle_options_request()
    
    # ========== CREATE ==========
    @http.route('/api/employees', type='json', auth='public', methods=['POST'], csrf=False)
    def create_employee(self, **kw):
        """
        Create a new employee
        
        Required params:
        - name: Employee name
        
        Optional params:
        - job_title: Job title
        - department_id: Department ID
        - job_id: Job position ID
        - work_email: Work email
        - work_phone: Work phone
        - mobile_phone: Mobile phone
        - address_id: Address ID
        - private_email: Private email
        - coach_id: Coach/mentor ID
        - parent_id: Manager ID
        - notes: Notes
        - photo: Base64 encoded employee photo
        """
        # Validate API key and HR rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            return result
        
        user = result
        if not self._validate_hr_rights(user):
            return {"error": "Insufficient rights to create employees"}
        
        # Validate required fields
        if 'name' not in kw:
            return {"error": "Employee name is required"}
        
        # Prepare employee values
        employee_values = {
            'name': kw['name'],
            'active': kw.get('active', True),
        }
        
        # Add optional fields if provided
        optional_fields = [
            'job_title', 'department_id', 'job_id', 'work_email', 'work_phone',
            'mobile_phone', 'address_id', 'private_email', 'coach_id', 'parent_id', 'notes'
        ]
        
        for field in optional_fields:
            if field in kw:
                employee_values[field] = kw[field]
        
        # Handle photo
        if 'photo' in kw and kw['photo']:
            try:
                employee_values['image_1920'] = kw['photo']
            except Exception as e:
                _logger.error("Error processing employee photo: %s", str(e))
        
        # Create employee
        try:
            new_employee = request.env['hr.employee'].sudo().create(employee_values)
            
            return {
                "success": True,
                "id": new_employee.id,
                "name": new_employee.name
            }
        except Exception as e:
            _logger.error("Error creating employee: %s", str(e))
            return {"error": f"Failed to create employee: {str(e)}"}
    
    # ========== READ ==========
    @http.route('/api/employees/<int:employee_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee(self, employee_id, **kw):
        """Get employee details by ID"""
        # Validate API key
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_hr_rights(user):
            result = {"error": "Insufficient rights to view employee details"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the requested employee
        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists():
            result = {"error": "Employee not found"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Format employee data - exclude binary fields for performance
        employee_data = {
            "id": employee.id,
            "name": employee.name,
            "job_title": employee.job_title or "",
            "work_email": employee.work_email or "",
            "work_phone": employee.work_phone or "",
            "mobile_phone": employee.mobile_phone or "",
            "department_id": employee.department_id.id if employee.department_id else False,
            "department_name": employee.department_id.name if employee.department_id else "",
            "job_id": employee.job_id.id if employee.job_id else False,
            "job_position": employee.job_id.name if employee.job_id else "",
            "parent_id": employee.parent_id.id if employee.parent_id else False,
            "manager_name": employee.parent_id.name if employee.parent_id else "",
            "coach_id": employee.coach_id.id if employee.coach_id else False,
            "coach_name": employee.coach_id.name if employee.coach_id else "",
            "active": employee.active,
            "address_id": employee.address_id.id if employee.address_id else False,
            "work_location_id": employee.work_location_id.id if employee.work_location_id else False,
            "work_location": employee.work_location_id.name if employee.work_location_id else "",
            "private_email": employee.private_email or "",
            "user_id": employee.user_id.id if employee.user_id else False,
            "user_partner_id": employee.user_partner_id.id if employee.user_partner_id else False,
            "has_photo": bool(employee.image_1920),
        }
        
        # Optional include notes
        if kw.get('include_notes'):
            employee_data['notes'] = employee.notes or ""
        
        # Include hr.employee.public fields if accessible
        if hasattr(employee, 'employee_type'):
            employee_data['employee_type'] = employee.employee_type or ""
        
        result = {
            "success": True,
            "employee": employee_data
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/employees/<int:employee_id>/photo', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_photo(self, employee_id, **kw):
        """Get employee photo"""
        # Validate API key
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_hr_rights(user):
            result = {"error": "Insufficient rights to access employee photo"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the requested employee
        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists():
            result = {"error": "Employee not found"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Check if employee has a photo
        if not employee.image_1920:
            result = {"error": "Employee has no photo"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Return photo
        image_base64 = employee.image_1920
        
        # If requesting base64 format
        if kw.get('format') == 'base64':
            if isinstance(image_base64, bytes):
                image_base64 = base64.b64encode(image_base64).decode('utf-8')
            
            result = {
                "success": True,
                "image": image_base64
            }
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Default: return binary image
        if isinstance(image_base64, str):
            image_data = base64.b64decode(image_base64)
        else:
            image_data = image_base64
        
        response = request.make_response(image_data)
        response.headers['Content-Type'] = 'image/png'  # Assuming PNG, could be improved with image detection
        return self._add_cors_headers(response)
    
    @http.route('/api/employees', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employees(self, **kw):
        """
        Get a list of employees with optional filtering
        
        Optional params:
        - limit: Maximum number of records to return
        - offset: Number of records to skip
        - active: Filter by active status (true/false)
        - department_id: Filter by department ID
        - search: Search term for name or work email
        """
        # Validate API key and HR rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_hr_rights(user):
            result = {"error": "Insufficient rights to list employees"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Parse parameters
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        
        # Build domain
        domain = []
        
        # Active filter
        if 'active' in kw:
            active = kw['active'].lower() in ['true', '1', 't', 'y', 'yes']
            domain.append(('active', '=', active))
        
        # Department filter
        if 'department_id' in kw and kw['department_id']:
            try:
                department_id = int(kw['department_id'])
                domain.append(('department_id', '=', department_id))
            except ValueError:
                pass
        
        # Job position filter
        if 'job_id' in kw and kw['job_id']:
            try:
                job_id = int(kw['job_id'])
                domain.append(('job_id', '=', job_id))
            except ValueError:
                pass
        
        # Manager filter
        if 'manager_id' in kw and kw['manager_id']:
            try:
                manager_id = int(kw['manager_id'])
                domain.append(('parent_id', '=', manager_id))
            except ValueError:
                pass
        
        # Search term
        if 'search' in kw and kw['search']:
            search_term = kw['search']
            domain.append(['|', '|', 
                ('name', 'ilike', search_term), 
                ('work_email', 'ilike', search_term),
                ('job_title', 'ilike', search_term)
            ])
        
        # Get employees
        employees = request.env['hr.employee'].sudo().search(domain, limit=limit, offset=offset)
        total_count = request.env['hr.employee'].sudo().search_count(domain)
        
        # Format response
        employees_data = [{
            "id": e.id,
            "name": e.name,
            "job_title": e.job_title or "",
            "work_email": e.work_email or "",
            "department_id": e.department_id.id if e.department_id else False,
            "department_name": e.department_id.name if e.department_id else "",
            "job_id": e.job_id.id if e.job_id else False,
            "job_position": e.job_id.name if e.job_id else "",
            "manager_id": e.parent_id.id if e.parent_id else False,
            "manager_name": e.parent_id.name if e.parent_id else "",
            "work_phone": e.work_phone or "",
            "mobile_phone": e.mobile_phone or "",
            "active": e.active,
            "has_photo": bool(e.image_1920),
        } for e in employees]
        
        result = {
            "success": True,
            "count": len(employees_data),
            "total": total_count,
            "employees": employees_data
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/employees/search', type='http', auth='public', methods=['GET'], csrf=False)
    def search_employees(self, **kw):
        """
        Search for employees with advanced filtering
        
        Required params:
        - query: Search term
        
        Optional params:
        - limit: Maximum number of records to return
        - offset: Number of records to skip
        - fields: Comma-separated list of fields to search in (default: name,work_email)
        """
        # Validate API key and HR rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_hr_rights(user):
            result = {"error": "Insufficient rights to search employees"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Validate required parameters
        if 'query' not in kw or not kw['query']:
            result = {"error": "Search query is required"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Parse parameters
        query = kw['query']
        limit = int(kw.get('limit', 20))
        offset = int(kw.get('offset', 0))
        fields = kw.get('fields', 'name,work_email').split(',')
        
        # Validate fields
        valid_fields = ['name', 'work_email', 'job_title', 'work_phone', 'mobile_phone', 'private_email']
        search_fields = [f for f in fields if f in valid_fields]
        
        if not search_fields:
            search_fields = ['name', 'work_email']
        
        # Build domain
        domain = []
        for field in search_fields:
            if len(domain) > 0:
                domain.insert(0, '|')
            domain.append((field, 'ilike', query))
        
        # Get employees
        employees = request.env['hr.employee'].sudo().search(domain, limit=limit, offset=offset)
        total_count = request.env['hr.employee'].sudo().search_count(domain)
        
        # Format response
        employees_data = [{
            "id": e.id,
            "name": e.name,
            "job_title": e.job_title or "",
            "work_email": e.work_email or "",
            "department_name": e.department_id.name if e.department_id else "",
            "job_position": e.job_id.name if e.job_id else "",
            "work_phone": e.work_phone or "",
            "mobile_phone": e.mobile_phone or "",
        } for e in employees]
        
        result = {
            "success": True,
            "count": len(employees_data),
            "total": total_count,
            "employees": employees_data
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/employees/count', type='http', auth='public', methods=['GET'], csrf=False)
    def count_employees(self, **kw):
        """Get employee counts with optional filtering"""
        # Validate API key and HR rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_hr_rights(user):
            result = {"error": "Insufficient rights to count employees"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get counts
        total_employees = request.env['hr.employee'].sudo().search_count([])
        active_employees = request.env['hr.employee'].sudo().search_count([('active', '=', True)])
        inactive_employees = request.env['hr.employee'].sudo().search_count([('active', '=', False)])
        
        # Department counts
        departments = request.env['hr.department'].sudo().search([])
        dept_counts = []
        for dept in departments:
            count = request.env['hr.employee'].sudo().search_count([
                ('department_id', '=', dept.id),
                ('active', '=', True)
            ])
            if count > 0:
                dept_counts.append({
                    "id": dept.id,
                    "name": dept.name,
                    "count": count
                })
        
        result = {
            "success": True,
            "total": total_employees,
            "active": active_employees,
            "inactive": inactive_employees,
            "by_department": dept_counts
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/employees/departments', type='http', auth='public', methods=['GET'], csrf=False)
    def get_departments(self, **kw):
        """Get all departments"""
        # Validate API key and HR rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_hr_rights(user):
            result = {"error": "Insufficient rights to view departments"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get departments
        departments = request.env['hr.department'].sudo().search([])
        
        # Format response
        dept_data = [{
            "id": d.id,
            "name": d.name,
            "manager_id": d.manager_id.id if d.manager_id else False,
            "manager_name": d.manager_id.name if d.manager_id else "",
            "parent_id": d.parent_id.id if d.parent_id else False,
            "parent_name": d.parent_id.name if d.parent_id else "",
            "company_id": d.company_id.id if d.company_id else False,
            "company_name": d.company_id.name if d.company_id else "",
            "total_employees": d.total_employee if hasattr(d, 'total_employee') else 0,
        } for d in departments]
        
        result = {
            "success": True,
            "count": len(dept_data),
            "departments": dept_data
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/employees/job-positions', type='http', auth='public', methods=['GET'], csrf=False)
    def get_job_positions(self, **kw):
        """Get all job positions"""
        # Validate API key and HR rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_hr_rights(user):
            result = {"error": "Insufficient rights to view job positions"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get job positions
        jobs = request.env['hr.job'].sudo().search([])
        
        # Format response
        jobs_data = [{
            "id": j.id,
            "name": j.name,
            "department_id": j.department_id.id if j.department_id else False,
            "department_name": j.department_id.name if j.department_id else "",
            "company_id": j.company_id.id if j.company_id else False,
            "company_name": j.company_id.name if j.company_id else "",
            "no_of_employees": j.no_of_employee if hasattr(j, 'no_of_employee') else 0,
            "no_of_recruitment": j.no_of_recruitment if hasattr(j, 'no_of_recruitment') else 0,
            "description": j.description or ""
        } for j in jobs]
        
        result = {
            "success": True,
            "count": len(jobs_data),
            "jobs": jobs_data
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    # ========== UPDATE ==========
    @http.route('/api/employees/<int:employee_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_employee(self, employee_id, **kw):
        """
        Update an existing employee
        
        Optional params:
        - name: Employee name
        - job_title: Job title
        - department_id: Department ID
        - job_id: Job position ID
        - work_email: Work email
        - work_phone: Work phone
        - mobile_phone: Mobile phone
        - parent_id: Manager ID
        - coach_id: Coach ID
        - address_id: Work address ID
        - notes: Notes
        - photo: Base64 encoded employee photo
        """
        # Validate API key and HR rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            return result
        
        user = result
        if not self._validate_hr_rights(user):
            return {"error": "Insufficient rights to update employees"}
        
        # Get the employee
        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists():
            return {"error": "Employee not found"}
        
        # Prepare values to update
        update_values = {}
        
        # Simple fields
        for field in ['name', 'job_title', 'work_email', 'work_phone', 'mobile_phone', 
                     'private_email', 'notes', 'active']:
            if field in kw:
                update_values[field] = kw[field]
        
        # Relational fields
        for field in ['department_id', 'job_id', 'parent_id', 'coach_id', 'address_id']:
            if field in kw:
                # Handle false/null values
                if kw[field] in [False, None, 0, '0', 'false', 'False']:
                    update_values[field] = False
                else:
                    update_values[field] = int(kw[field])
        
        # Handle photo
        if 'photo' in kw:
            if not kw['photo']:
                # Clear photo
                update_values['image_1920'] = False
            else:
                try:
                    update_values['image_1920'] = kw['photo']
                except Exception as e:
                    _logger.error("Error processing employee photo: %s", str(e))
                    return {"error": f"Failed to process photo: {str(e)}"}
        
        # Update employee
        try:
            employee.write(update_values)
            
            return {
                "success": True,
                "id": employee.id,
                "name": employee.name,
                "message": "Employee updated successfully"
            }
        except Exception as e:
            _logger.error("Error updating employee: %s", str(e))
            return {"error": f"Failed to update employee: {str(e)}"}
    
    # ========== DELETE/ARCHIVE ==========
    @http.route('/api/employees/<int:employee_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_employee(self, employee_id, **kw):
        """Delete or archive an employee"""
        # Validate API key and HR rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_hr_rights(user):
            result = {"error": "Insufficient rights to delete employees"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the employee
        employee = request.env['hr.employee'].sudo().browse(employee_id)
        if not employee.exists():
            result = {"error": "Employee not found"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Check if permanent deletion is requested
        permanent = kw.get('permanent', 'false').lower() in ['true', '1', 't', 'y', 'yes']
        
        try:
            if permanent:
                # Permanent deletion (may fail due to constraints)
                employee.unlink()
                message = "Employee deleted permanently"
            else:
                # Archive instead of delete (safer)
                employee.write({'active': False})
                message = "Employee archived successfully"
            
            result = {
                "success": True,
                "id": employee_id,
                "message": message
            }
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        except Exception as e:
            _logger.error("Error deleting employee: %s", str(e))
            result = {"error": f"Failed to delete employee: {str(e)}"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response) 