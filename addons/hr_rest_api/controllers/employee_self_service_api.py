# -*- coding: utf-8 -*-
#############################################################################
# REST API for Employee Self-Service
#############################################################################

import logging
import werkzeug.exceptions
import json
from datetime import datetime, date, timedelta
from odoo import http, fields, models, _
from odoo.http import request, Response
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.addons.hr_rest_api.controllers.main import HrRestApiController
import base64
import uuid
import jwt
from odoo.exceptions import AccessDenied
from odoo.api import Environment


_logger = logging.getLogger(__name__)

def valid_response(data=None, status=200):
    """Returns a valid json response with data and status code"""
    data = data or {}
    response_data = {
        'jsonrpc': '2.0',
        'result': data,
        'success': True
    }
    return response_data

def invalid_response(error_title, error_message, status=400):
    """Returns an invalid json response with error and status code"""
    response_data = {
        'jsonrpc': '2.0',
        'error': {
            'code': status,
            'message': error_title,
            'data': {
                'name': error_title,
                'debug': error_message,
                'status': status
            }
        },
        'success': False
    }
    return response_data

class EmployeeSelfServiceAPIController(HrRestApiController):
    """
    This controller provides API endpoints for employee self-service functionality,
    allowing employees to manage their own information.
    """

    def _handle_options_request(self):
        """Handle OPTIONS requests for CORS preflight"""
        response = request.make_response('', headers=[('Content-Type', 'text/plain')])
        return self._add_cors_headers(response)

    def _validate_employee_access(self, employee_id=None):
        """
        Validates that the authenticated user has access to the specified employee data
        or is accessing their own data when no employee_id is specified.
        
        Returns the employee record if access is allowed.
        """
        user = request.env.user
        if not user:
            return invalid_response("Access Denied", "Authentication required")

        # Check for user's employee record
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            return invalid_response("Access Denied", "User is not linked to an employee record")
            
        # If employee_id is provided, check if the user has rights to access it
        if employee_id and employee_id != employee.id:
            # Only HR managers or officers can access other employees' data
            if not user.has_group('hr.group_hr_user') and not user.has_group('hr.group_hr_manager'):
                return invalid_response("Access Denied", "You can only access your own employee data")
            
            # Get the requested employee record
            target_employee = request.env['hr.employee'].sudo().browse(employee_id)
            if not target_employee.exists():
                return invalid_response("Not Found", "Employee not found")
            return target_employee
            
        return employee

    # ===== PERSONAL INFORMATION ENDPOINTS =====
    
    @http.route('/api/employee/profile', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    def get_employee_profile_http(self, **kw):
        """Get authenticated employee's profile information via HTTP"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
        
        # Default response headers
        headers = [('Content-Type', 'application/json')]
        
        try:
            # Check authentication - either through session or API key
            user = request.env.user
            
            # If not authenticated through session, try API key
            if user.id == request.env.ref('base.public_user').id:
                # Get authentication from Basic Auth or API key
                auth_header = request.httprequest.headers.get('Authorization')
                api_key = request.httprequest.headers.get('X-API-Key')
                
                if not auth_header and not api_key:
                    result = {
                        'success': False, 
                        'error': 'Authentication required. Please provide an API key or login.'
                    }
                    response = request.make_response(json.dumps(result), headers=headers)
                    return self._add_cors_headers(response)
                    
                # Validate using parent class method
                is_valid, user_result = self._validate_api_key()
                if not is_valid:
                    result = {
                        'success': False,
                        'error': user_result.get('error', 'Authentication failed'),
                    }
                    response = request.make_response(json.dumps(result), headers=headers)
                    return self._add_cors_headers(response)
                    
                user = user_result
            
            # Now that we have a user, get the associated employee
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            if not employee:
                result = {
                    'success': False,
                    'error': 'User is not associated with an employee record.'
                }
                response = request.make_response(json.dumps(result), headers=headers)
                return self._add_cors_headers(response)
            
            # Employee found, return profile data
            result = {
                "success": True,
                "data": {
                    "id": employee.id,
                    "name": employee.name or "",
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
                    "work_location_id": employee.work_location_id.id if employee.work_location_id else False,
                    "work_location": employee.work_location_id.name if employee.work_location_id else "",
                    "company_id": employee.company_id.id if employee.company_id else False,
                    "company_name": employee.company_id.name if employee.company_id else "",
                    "private_email": employee.private_email or "",
                    "has_photo": bool(employee.image_1920),
                }
            }
            
            response = request.make_response(json.dumps(result), headers=headers)
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error in get_employee_profile_http: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'debug': str(e) if request.env.user.has_group('base.group_system') else None
            }
            response = request.make_response(json.dumps(result), headers=headers, status=500)
            return self._add_cors_headers(response)
    
    # @http.route('/api/employee/profile', type='json', auth='public', methods=['GET', 'OPTIONS'])
    # def get_employee_profile(self, **kw):
    #     """Get authenticated employee's profile information via JSON-RPC"""
    #     if request.httprequest.method == 'OPTIONS':
    #         return self._handle_options_request()
        
    #     try:
    #         # First try to get user from session
    #         user = request.env.user
    #         if user.id == request.env.ref('base.public_user').id:
    #             # If public user, try to validate API key
    #             try:
    #                 is_valid, result = self._validate_api_key()
    #                 if not is_valid:
    #                     _logger.warning("API key validation failed: %s", result)
    #                     return {
    #                         'success': False,
    #                         'error': "Authentication Error: Invalid or missing API key"
    #                     }
    #                 user = result  # Use the authenticated user
    #             except Exception as auth_error:
    #                 _logger.error("Authentication error: %s", str(auth_error))
    #                 return {
    #                     'success': False,
    #                     'error': f"Authentication Error: {str(auth_error)}"
    #                 }
            
    #         # Get employee based on user
    #         employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
    #         if not employee:
    #             return {
    #                 'success': False,
    #                 'error': "Access Denied: User is not linked to an employee record"
    #             }
                
    #         # Format employee data - exclude binary fields for performance
    #         return {
    #             'success': True,
    #             'data': {
    #                 "id": employee.id,
    #                 "name": employee.name or "",
    #                 "job_title": employee.job_title or "",
    #                 "work_email": employee.work_email or "",
    #                 "work_phone": employee.work_phone or "",
    #                 "mobile_phone": employee.mobile_phone or "",
    #                 "department_id": employee.department_id.id if employee.department_id else False,
    #                 "department_name": employee.department_id.name if employee.department_id else "",
    #                 "job_id": employee.job_id.id if employee.job_id else False,
    #                 "job_position": employee.job_id.name if employee.job_id else "",
    #                 "parent_id": employee.parent_id.id if employee.parent_id else False,
    #                 "manager_name": employee.parent_id.name if employee.parent_id else "",
    #                 "coach_id": employee.coach_id.id if employee.coach_id else False,
    #                 "coach_name": employee.coach_id.name if employee.coach_id else "",
    #                 "work_location_id": employee.work_location_id.id if employee.work_location_id else False,
    #                 "work_location": employee.work_location_id.name if employee.work_location_id else "",
    #                 "company_id": employee.company_id.id if employee.company_id else False,
    #                 "company_name": employee.company_id.name if employee.company_id else "",
    #                 "private_email": employee.private_email or "",
    #                 "has_photo": bool(employee.image_1920),
    #             }
    #         }
    #     except Exception as e:
    #         _logger.error("Error in get_employee_profile: %s", str(e), exc_info=True)
    #         return {
    #             'success': False,
    #             'error': f"Server Error: {str(e)}"
    #         }
        
    @http.route('/api/employee/profile/update', type='json', auth='user', methods=['POST', 'OPTIONS'])
    def update_employee_profile(self, **kw):
        """Update employee's profile information"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
        
        # First get the authenticated employee
        try:
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
            if not employee:
                return {
                    'success': False,
                    'error': "Access Denied: User is not linked to an employee record"
                }
            
            allowed_fields = [
                'private_email', 'private_phone', 'work_phone', 'mobile_phone',
                'private_street', 'private_street2', 'private_city', 'private_state_id',
                'private_zip', 'private_country_id', 'emergency_contact', 'emergency_phone',
            ]
            
            # Filter out fields that are not allowed to be updated by the employee
            update_values = {k: v for k, v in kw.items() if k in allowed_fields}
            
            if not update_values:
                return {
                    'success': False,
                    'error': "No valid fields to update"
                }
            
            employee.sudo().write(update_values)
            return {
                "success": True,
                "message": "Profile updated successfully"
            }
        except Exception as e:
            _logger.error("Error in update_employee_profile: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': f"Update Error: {str(e)}"
            }
            
    @http.route('/api/employee/photo', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_employee_photo(self, **kw):
        """Get employee's profile photo"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        if not employee.image_1920:
            return invalid_response("Not Found", "No profile photo found")
            
        return valid_response({
            "image": employee.image_1920.decode('utf-8') if employee.image_1920 else False
        })
        
    @http.route('/api/employee/photo/update', type='json', auth='user', methods=['POST', 'OPTIONS'])
    def update_employee_photo(self, **kw):
        """Update employee's profile photo"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        image_data = kw.get('image_data')
        if not image_data:
            return invalid_response("Bad Request", "No image data provided")
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        try:
            employee.sudo().write({
                'image_1920': image_data
            })
            return valid_response({
                "success": True,
                "message": "Photo updated successfully"
            })
        except Exception as e:
            return invalid_response("Update Error", str(e))
    
    # ===== TIME OFF ENDPOINTS =====
    
    @http.route('/api/employee/timeoff/balance', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_leave_balances(self, **kw):
        """Get employee's leave balances"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        try:
            # Get the authenticated employee
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
            if not employee:
                return {
                    'success': False,
                    'error': "Access Denied: User is not linked to an employee record"
                }
            
            # Get leave types and balances
            allocations = request.env['hr.leave.allocation'].sudo().search([
                ('employee_id', '=', employee.id),
                ('state', '=', 'validate'),
            ])
            
            leave_types = request.env['hr.leave.type'].sudo().search([])
            
            result = []
            for leave_type in leave_types:
                allocation = allocations.filtered(lambda a: a.holiday_status_id.id == leave_type.id)
                
                # Calculate days taken
                leaves_taken = request.env['hr.leave'].sudo().search([
                    ('employee_id', '=', employee.id),
                    ('holiday_status_id', '=', leave_type.id),
                    ('state', '=', 'validate'),
                ])
                days_taken = sum(leaves_taken.mapped('number_of_days'))
                
                # Get allocation or default to 0
                if allocation:
                    max_leaves = sum(allocation.mapped('number_of_days'))
                    leaves_remaining = max_leaves - days_taken
                else:
                    max_leaves = 0
                    leaves_remaining = 0
                    
                result.append({
                    'id': leave_type.id,
                    'name': leave_type.name,
                    'code': leave_type.code or '',
                    'max_leaves': max_leaves,
                    'leaves_taken': days_taken,
                    'leaves_remaining': leaves_remaining,
                    'virtual_remaining_leaves': leaves_remaining,
                    'requires_allocation': leave_type.requires_allocation,
                })
                
            return {
                'success': True,
                'data': result
            }
        except Exception as e:
            _logger.error("Error in get_leave_balances: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': f"Server Error: {str(e)}"
            }
        
    @http.route('/api/employee/timeoff/request', type='json', auth='user', methods=['POST', 'OPTIONS'])
    def request_time_off(self, **kw):
        """Create a new time off request"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        try:
            # Get the authenticated employee
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
            if not employee:
                return {
                    'success': False,
                    'error': "Access Denied: User is not linked to an employee record"
                }
            
            required_fields = ['holiday_status_id', 'date_from', 'date_to', 'request_unit']
            for field in required_fields:
                if field not in kw:
                    return {
                        'success': False,
                        'error': f"Bad Request: Missing required field: {field}"
                    }
                
            # Convert string dates to datetime objects
            date_from = fields.Datetime.from_string(kw['date_from'])
            date_to = fields.Datetime.from_string(kw['date_to'])
            
            # Create leave request
            leave_values = {
                'holiday_status_id': kw['holiday_status_id'],
                'date_from': date_from,
                'date_to': date_to,
                'request_date_from': date_from.date(),
                'request_date_to': date_to.date(),
                'employee_id': employee.id,
                'request_unit': kw.get('request_unit', 'day'),
                'name': kw.get('name', 'Time Off Request'),
                'number_of_days': kw.get('number_of_days', 0),
            }
            
            time_off = request.env['hr.leave'].sudo().create(leave_values)
            
            # Submit for approval
            time_off.action_confirm()
            
            return {
                'success': True,
                'data': {
                    'id': time_off.id,
                    'state': time_off.state,
                    'message': 'Time off request submitted successfully'
                }
            }
            
        except Exception as e:
            _logger.error("Error in request_time_off: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': f"Request Error: {str(e)}"
            }
            
    @http.route('/api/employee/timeoff/list', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_time_off_requests(self, **kw):
        """Get employee's time off requests"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        state = kw.get('state')
        year = kw.get('year')
        
        domain = [('employee_id', '=', employee.id)]
        
        # Filter by state if provided
        if state:
            domain.append(('state', '=', state))
            
        # Filter by year if provided
        if year:
            date_from = datetime(int(year), 1, 1)
            date_to = datetime(int(year), 12, 31)
            domain.extend([
                ('date_from', '>=', date_from),
                ('date_to', '<=', date_to)
            ])
            
        leave_requests = request.env['hr.leave'].sudo().search(domain)
        
        result = []
        for leave in leave_requests:
            result.append({
                'id': leave.id,
                'name': leave.name,
                'state': leave.state,
                'leave_type_id': leave.holiday_status_id.id,
                'leave_type_name': leave.holiday_status_id.name,
                'date_from': fields.Datetime.to_string(leave.date_from),
                'date_to': fields.Datetime.to_string(leave.date_to),
                'number_of_days': leave.number_of_days,
                'can_cancel': leave.state in ['draft', 'confirm', 'validate1'],
            })
            
        return valid_response(result)
        
    @http.route('/api/employee/timeoff/cancel/<int:leave_id>', type='json', auth='user', methods=['POST', 'OPTIONS'])
    def cancel_time_off_request(self, leave_id, **kw):
        """Cancel a time off request"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        leave = request.env['hr.leave'].sudo().browse(leave_id)
        
        if not leave.exists():
            return invalid_response("Not Found", "Time off request not found")
            
        if leave.employee_id.id != employee.id:
            return invalid_response("Access Denied", "You can only cancel your own time off requests")
            
        if leave.state not in ['draft', 'confirm', 'validate1']:
            return invalid_response("Invalid Operation", "This time off request cannot be cancelled in its current state")
            
        try:
            leave.action_cancel()
            return valid_response({
                'success': True,
                'message': 'Time off request cancelled successfully'
            })
        except Exception as e:
            return invalid_response("Cancel Error", str(e))
    
    # ===== ATTENDANCE ENDPOINTS =====
    
    @http.route('/api/employee/attendance/check_in', type='json', auth='user', methods=['POST', 'OPTIONS'])
    def check_in(self, **kw):
        """Employee check-in"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        if employee.attendance_state == 'checked_in':
            return invalid_response("Already Checked In", "You are already checked in")
            
        try:
            attendance = request.env['hr.attendance'].sudo().create({
                'employee_id': employee.id,
                'check_in': fields.Datetime.now(),
            })
            return valid_response({
                'id': attendance.id,
                'check_in': fields.Datetime.to_string(attendance.check_in),
                'message': 'Check-in recorded successfully'
            })
        except Exception as e:
            return invalid_response("Check-in Error", str(e))
            
    @http.route('/api/employee/attendance/check_out', type='json', auth='user', methods=['POST', 'OPTIONS'])
    def check_out(self, **kw):
        """Employee check-out"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        if employee.attendance_state == 'checked_out':
            return invalid_response("Already Checked Out", "You are already checked out")
            
        try:
            attendance = employee.attendance_ids.filtered(lambda att: not att.check_out)
            if attendance:
                attendance = attendance[0]
                attendance.check_out = fields.Datetime.now()
                return valid_response({
                    'id': attendance.id,
                    'check_in': fields.Datetime.to_string(attendance.check_in),
                    'check_out': fields.Datetime.to_string(attendance.check_out),
                    'worked_hours': attendance.worked_hours,
                    'message': 'Check-out recorded successfully'
                })
            else:
                return invalid_response("No Check-in", "No matching check-in found")
        except Exception as e:
            return invalid_response("Check-out Error", str(e))
            
    @http.route('/api/employee/attendance/history', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_attendance_history(self, **kw):
        """Get employee's attendance history"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        start_date = kw.get('start_date')
        end_date = kw.get('end_date')
        
        domain = [('employee_id', '=', employee.id)]
        
        # Add date filters if provided
        if start_date:
            domain.append(('check_in', '>=', start_date))
        if end_date:
            domain.append(('check_in', '<=', end_date))
            
        attendances = request.env['hr.attendance'].sudo().search(domain)
        
        result = []
        for attendance in attendances:
            result.append({
                'id': attendance.id,
                'check_in': fields.Datetime.to_string(attendance.check_in),
                'check_out': fields.Datetime.to_string(attendance.check_out) if attendance.check_out else False,
                'worked_hours': attendance.worked_hours,
            })
            
        return valid_response(result)
    
    # ===== CONTRACT ENDPOINTS =====
    
    @http.route('/api/employee/contracts', type='http', auth='user', methods=['GET', 'OPTIONS'], csrf=False)
    def get_employee_contracts(self, **kw):
        """Get employee's contracts"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        headers = [('Content-Type', 'application/json')]
        
        try:
            # Get the authenticated employee
            employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)
            if not employee:
                result = {
                    'success': False,
                    'error': "Access Denied: User is not linked to an employee record"
                }
                response = request.make_response(json.dumps(result), headers=headers)
                return self._add_cors_headers(response)
            
            contracts = request.env['hr.contract'].sudo().search([
                ('employee_id', '=', employee.id)
            ])
            
            result_data = []
            for contract in contracts:
                result_data.append({
                    'id': contract.id,
                    'name': contract.name,
                    'state': contract.state,
                    'date_start': fields.Date.to_string(contract.date_start),
                    'date_end': fields.Date.to_string(contract.date_end) if contract.date_end else False,
                    'wage': contract.wage,
                    'department_id': contract.department_id.id if contract.department_id else False,
                    'department_name': contract.department_id.name if contract.department_id else "",
                    'job_id': contract.job_id.id if contract.job_id else False,
                    'job_title': contract.job_id.name if contract.job_id else "",
                    'resource_calendar_id': contract.resource_calendar_id.id if contract.resource_calendar_id else False,
                    'work_schedule': contract.resource_calendar_id.name if contract.resource_calendar_id else "",
                    'trial_date_end': fields.Date.to_string(contract.trial_date_end) if contract.trial_date_end else False,
                })
            
            result = {
                'success': True,
                'data': result_data
            }
            
            response = request.make_response(json.dumps(result), headers=headers)
            return self._add_cors_headers(response)
        except Exception as e:
            _logger.error("Error in get_employee_contracts: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': f"Server Error: {str(e)}"
            }
            response = request.make_response(json.dumps(result), headers=headers, status=500)
            return self._add_cors_headers(response)
    
    # ===== FAMILY INFORMATION ENDPOINTS =====
    
    @http.route('/api/employee/family', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_family_information(self, **kw):
        """Get employee's family information"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if the family module is installed
        if not request.env['ir.model'].sudo().search([('model', '=', 'hr.employee.family')]):
            return invalid_response("Not Available", "Family information module is not installed")
            
        family_members = request.env['hr.employee.family'].sudo().search([
            ('employee_id', '=', employee.id)
        ])
        
        result = []
        for member in family_members:
            result.append({
                'id': member.id,
                'member_name': member.member_name,
                'relation': member.relation_id.name if member.relation_id else "",
                'member_contact': member.member_contact or "",
                'birth_date': fields.Date.to_string(member.birth_date) if member.birth_date else False,
            })
            
        return valid_response(result)
        
    @http.route('/api/employee/family/add', type='json', auth='user', methods=['POST', 'OPTIONS'])
    def add_family_member(self, **kw):
        """Add a new family member"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if the family module is installed
        if not request.env['ir.model'].sudo().search([('model', '=', 'hr.employee.family')]):
            return invalid_response("Not Available", "Family information module is not installed")
            
        required_fields = ['member_name', 'relation_id']
        for field in required_fields:
            if field not in kw:
                return invalid_response("Bad Request", f"Missing required field: {field}")
                
        try:
            family_values = {
                'employee_id': employee.id,
                'member_name': kw['member_name'],
                'relation_id': kw['relation_id'],
                'member_contact': kw.get('member_contact', False),
                'birth_date': kw.get('birth_date', False),
            }
            
            family_member = request.env['hr.employee.family'].sudo().create(family_values)
            
            return valid_response({
                'id': family_member.id,
                'message': 'Family member added successfully'
            })
            
        except Exception as e:
            return invalid_response("Creation Error", str(e))
            
    @http.route('/api/employee/family/update/<int:member_id>', type='json', auth='user', methods=['POST', 'OPTIONS'])
    def update_family_member(self, member_id, **kw):
        """Update a family member"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if the family module is installed
        if not request.env['ir.model'].sudo().search([('model', '=', 'hr.employee.family')]):
            return invalid_response("Not Available", "Family information module is not installed")
            
        family_member = request.env['hr.employee.family'].sudo().browse(member_id)
        
        if not family_member.exists():
            return invalid_response("Not Found", "Family member not found")
            
        if family_member.employee_id.id != employee.id:
            return invalid_response("Access Denied", "You can only update your own family members")
            
        try:
            allowed_fields = ['member_name', 'relation_id', 'member_contact', 'birth_date']
            update_values = {k: v for k, v in kw.items() if k in allowed_fields}
            
            family_member.write(update_values)
            
            return valid_response({
                'id': family_member.id,
                'message': 'Family member updated successfully'
            })
            
        except Exception as e:
            return invalid_response("Update Error", str(e))
            
    @http.route('/api/employee/family/delete/<int:member_id>', type='json', auth='user', methods=['POST', 'OPTIONS'])
    def delete_family_member(self, member_id, **kw):
        """Delete a family member"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if the family module is installed
        if not request.env['ir.model'].sudo().search([('model', '=', 'hr.employee.family')]):
            return invalid_response("Not Available", "Family information module is not installed")
            
        family_member = request.env['hr.employee.family'].sudo().browse(member_id)
        
        if not family_member.exists():
            return invalid_response("Not Found", "Family member not found")
            
        if family_member.employee_id.id != employee.id:
            return invalid_response("Access Denied", "You can only delete your own family members")
            
        try:
            family_member.unlink()
            
            return valid_response({
                'message': 'Family member deleted successfully'
            })
            
        except Exception as e:
            return invalid_response("Delete Error", str(e))
    
    # ===== DOCUMENT ENDPOINTS =====
    
    @http.route('/api/employee/documents', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_employee_documents(self, **kw):
        """Get employee's documents"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if the documents module is installed
        if not request.env['ir.model'].sudo().search([('model', '=', 'hr.employee.document')]):
            return invalid_response("Not Available", "Employee documents module is not installed")
            
        documents = request.env['hr.employee.document'].sudo().search([
            ('employee_ref_id', '=', employee.id)
        ])
        
        result = []
        for doc in documents:
            result.append({
                'id': doc.id,
                'name': doc.name,
                'document_type': doc.document_type_id.name if doc.document_type_id else "",
                'description': doc.description or "",
                'issue_date': fields.Date.to_string(doc.issue_date) if doc.issue_date else False,
                'expiry_date': fields.Date.to_string(doc.expiry_date) if doc.expiry_date else False,
                'has_attachment': bool(doc.doc_attachment_ids),
            })
            
        return valid_response(result)
    
    # ===== LOAN ENDPOINTS =====
    
    @http.route('/api/employee/loans', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_employee_loans(self, **kw):
        """Get employee's loans"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if the loan module is installed
        if not request.env['ir.model'].sudo().search([('model', '=', 'hr.loan')]):
            return invalid_response("Not Available", "Employee loan module is not installed")
            
        loans = request.env['hr.loan'].sudo().search([
            ('employee_id', '=', employee.id)
        ])
        
        result = []
        for loan in loans:
            result.append({
                'id': loan.id,
                'name': loan.name,
                'date': fields.Date.to_string(loan.date) if loan.date else False,
                'state': loan.state,
                'loan_amount': loan.loan_amount,
                'total_amount': loan.total_amount,
                'balance_amount': loan.balance_amount,
                'installment': loan.installment,
                'payment_date': fields.Date.to_string(loan.payment_date) if loan.payment_date else False,
            })
            
        return valid_response(result)
        
    # ===== RESIGNATION ENDPOINTS =====
    
    @http.route('/api/employee/resignation/status', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_resignation_status(self, **kw):
        """Get employee's resignation status"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if the resignation module is installed
        if not hasattr(employee, 'resigned'):
            return invalid_response("Not Available", "Resignation module is not installed")
            
        return valid_response({
            'resigned': employee.resigned,
            'fired': employee.fired,
            'resign_date': fields.Date.to_string(employee.resign_date) if employee.resign_date else False,
        })
        
    # ===== SKILLS & EDUCATION ENDPOINTS =====
    
    @http.route('/api/employee/skills', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_employee_skills(self, **kw):
        """Get employee's skills"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if the skills module is installed
        if not hasattr(employee, 'employee_skill_ids'):
            return invalid_response("Not Available", "Skills module is not installed")
            
        result = []
        for skill in employee.sudo().employee_skill_ids:
            result.append({
                'id': skill.id,
                'skill_id': skill.skill_id.id,
                'skill_name': skill.skill_id.name,
                'skill_type_id': skill.skill_type_id.id,
                'skill_type_name': skill.skill_type_id.name,
                'level': skill.level,
                'level_progress': skill.level_progress,
            })
            
        return valid_response(result)
        
    @http.route('/api/employee/education', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_employee_education(self, **kw):
        """Get employee's education history"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if the resume/employee education module is installed
        if not request.env['ir.model'].sudo().search([('model', '=', 'hr.resume.line')]):
            return invalid_response("Not Available", "Education/Resume module is not installed")
            
        education_lines = request.env['hr.resume.line'].sudo().search([
            ('employee_id', '=', employee.id),
            ('line_type_id.name', 'ilike', 'education')
        ])
        
        result = []
        for line in education_lines:
            result.append({
                'id': line.id,
                'name': line.name,
                'date_start': fields.Date.to_string(line.date_start) if line.date_start else False,
                'date_end': fields.Date.to_string(line.date_end) if line.date_end else False,
                'description': line.description or "",
                'type': line.line_type_id.name,
            })
            
        return valid_response(result)
        
    # ===== EMERGENCY CONTACTS ENDPOINTS =====
    
    @http.route('/api/employee/emergency_contacts', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_emergency_contacts(self, **kw):
        """Get employee's emergency contacts"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # First, check if there's a dedicated model for emergency contacts
        if request.env['ir.model'].sudo().search([('model', '=', 'hr.emergency.contact')]):
            contacts = request.env['hr.emergency.contact'].sudo().search([
                ('employee_id', '=', employee.id)
            ])
            
            result = []
            for contact in contacts:
                result.append({
                    'id': contact.id,
                    'name': contact.name,
                    'relationship': contact.relationship or "",
                    'phone': contact.phone or "",
                    'notes': contact.notes or "",
                })
                
            return valid_response(result)
            
        # If no dedicated model, check if stored in employee record
        elif hasattr(employee, 'emergency_contact') or hasattr(employee, 'emergency_phone'):
            return valid_response([{
                'name': employee.emergency_contact if hasattr(employee, 'emergency_contact') else "",
                'phone': employee.emergency_phone if hasattr(employee, 'emergency_phone') else "",
            }])
            
        else:
            return invalid_response("Not Available", "Emergency contact information is not available")
            
    @http.route('/api/employee/emergency_contacts/update', type='json', auth='user', methods=['POST', 'OPTIONS'])
    def update_emergency_contacts(self, **kw):
        """Update employee's emergency contact information"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # If stored directly on employee record
        if hasattr(employee, 'emergency_contact') or hasattr(employee, 'emergency_phone'):
            update_values = {}
            
            if 'emergency_contact' in kw and hasattr(employee, 'emergency_contact'):
                update_values['emergency_contact'] = kw['emergency_contact']
                
            if 'emergency_phone' in kw and hasattr(employee, 'emergency_phone'):
                update_values['emergency_phone'] = kw['emergency_phone']
                
            if update_values:
                try:
                    employee.sudo().write(update_values)
                    return valid_response({
                        'success': True,
                        'message': 'Emergency contact updated successfully'
                    })
                except Exception as e:
                    return invalid_response("Update Error", str(e))
                    
        return invalid_response("Not Available", "Emergency contact update is not available")
        
    # ===== EMPLOYEE CATEGORIES/TAGS ENDPOINTS =====
    
    @http.route('/api/employee/tags', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_employee_tags(self, **kw):
        """Get employee's tags/categories"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if employee has category_ids field
        if not hasattr(employee, 'category_ids'):
            return invalid_response("Not Available", "Employee tags/categories are not available")
            
        result = []
        for category in employee.sudo().category_ids:
            result.append({
                'id': category.id,
                'name': category.name,
                'color': category.color if hasattr(category, 'color') else 0,
            })
            
        return valid_response(result)
        
    # ===== BANK ACCOUNT ENDPOINTS =====
    
    @http.route('/api/employee/bank_accounts', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_bank_accounts(self, **kw):
        """Get employee's bank account information"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if employee has bank_account_id field
        if not hasattr(employee, 'bank_account_id'):
            return invalid_response("Not Available", "Bank account information is not available")
            
        if not employee.bank_account_id:
            return valid_response([])
            
        return valid_response([{
            'id': employee.bank_account_id.id,
            'acc_number': employee.bank_account_id.acc_number or "",
            'acc_holder_name': employee.bank_account_id.acc_holder_name or "",
            'bank_name': employee.bank_account_id.bank_id.name if employee.bank_account_id.bank_id else "",
            'bank_id': employee.bank_account_id.bank_id.id if employee.bank_account_id.bank_id else False,
        }])
        
    # ===== WORK HISTORY ENDPOINTS =====
    
    @http.route('/api/employee/work_history', type='json', auth='user', methods=['GET', 'OPTIONS'])
    def get_work_history(self, **kw):
        """Get employee's work history"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
            
        employee = self._validate_employee_access()
        if not isinstance(employee, models.Model):
            return employee  # It's an error response
            
        # Check if the resume module is installed
        if not request.env['ir.model'].sudo().search([('model', '=', 'hr.resume.line')]):
            return invalid_response("Not Available", "Work history module is not installed")
            
        work_lines = request.env['hr.resume.line'].sudo().search([
            ('employee_id', '=', employee.id),
            ('line_type_id.name', 'ilike', 'experience')
        ])
        
        result = []
        for line in work_lines:
            result.append({
                'id': line.id,
                'name': line.name,
                'date_start': fields.Date.to_string(line.date_start) if line.date_start else False,
                'date_end': fields.Date.to_string(line.date_end) if line.date_end else False,
                'description': line.description or "",
                'type': line.line_type_id.name,
            })
            
        return valid_response(result)
    
    @http.route('/api/auth/diagnostic', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    def auth_diagnostic(self, **kw):
        """Diagnostic endpoint to troubleshoot authentication issues"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()

        headers = [('Content-Type', 'application/json')]
        
        try:
            # Get request headers (excluding sensitive ones)
            safe_headers = {k: v for k, v in request.httprequest.headers.items() 
                           if k.lower() not in ['cookie', 'authorization'] or k.lower() == 'authorization' and v.startswith('Basic ')}
            
            if 'authorization' in safe_headers:
                auth_header = safe_headers['authorization']
                if auth_header.startswith('Basic '):
                    safe_headers['authorization'] = 'Basic *****' 
            
            # Collect diagnostic information
            diagnostics = {
                'timestamp': fields.Datetime.now().isoformat(),
                'request': {
                    'method': request.httprequest.method,
                    'path': request.httprequest.path,
                    'headers': safe_headers,
                    'has_api_key': bool(request.httprequest.headers.get('X-API-Key')),
                    'has_auth_header': bool(request.httprequest.headers.get('Authorization')),
                    'content_type': request.httprequest.headers.get('Content-Type'),
                    'accept': request.httprequest.headers.get('Accept'),
                    'user_agent': request.httprequest.headers.get('User-Agent'),
                    'origin': request.httprequest.headers.get('Origin'),
                    'remote_addr': request.httprequest.remote_addr,
                },
                'session': {
                    'authenticated': request.session.uid is not None,
                    'uid': request.session.uid,
                },
                'user': {
                    'id': request.env.user.id,
                    'login': request.env.user.login,
                    'is_public': request.env.user.id == request.env.ref('base.public_user').id,
                    'has_employee': bool(request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1)),
                }
            }
            
            # Try to validate API key
            auth_result = {'tested': False}
            
            if request.httprequest.headers.get('X-API-Key') or request.httprequest.headers.get('Authorization'):
                auth_result['tested'] = True
                is_valid, result = self._validate_api_key()
                auth_result['valid'] = is_valid
                
                if is_valid:
                    auth_result['user_id'] = result.id
                    auth_result['user_login'] = result.login
                    
                    # Check if user has an employee record
                    employee = request.env['hr.employee'].sudo().search([('user_id', '=', result.id)], limit=1)
                    auth_result['has_employee'] = bool(employee)
                    if employee:
                        auth_result['employee_id'] = employee.id
                        auth_result['employee_name'] = employee.name
                else:
                    auth_result['error'] = result.get('error')
            
            diagnostics['auth_test'] = auth_result
            
            # Suggest fix based on diagnostics
            suggestion = "Unknown issue. Please check all parameters."
            
            if not auth_result.get('tested', False):
                suggestion = "No authentication credentials provided. Add an X-API-Key header or Basic Auth."
            elif not auth_result.get('valid', False):
                suggestion = f"Authentication failed: {auth_result.get('error', 'Unknown reason')}"
            elif not auth_result.get('has_employee', False):
                suggestion = "Authentication successful, but user is not linked to an employee record."
            else:
                suggestion = "Authentication successful! You should be able to access the API."
            
            diagnostics['suggestion'] = suggestion
            
            # Return diagnostic information
            result = {
                'success': True,
                'diagnostics': diagnostics
            }
            
            response = request.make_response(json.dumps(result), headers=headers)
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error in auth_diagnostic: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred during diagnostic.',
                'debug': str(e)
            }
            response = request.make_response(json.dumps(result), headers=headers, status=500)
            return self._add_cors_headers(response)
    
    @http.route('/api/employee/test', type='http', auth='public', methods=['GET', 'OPTIONS'], csrf=False)
    def test_employee_api(self, **kw):
        """Test endpoint to diagnose authentication and access issues (legacy endpoint)"""
        if request.httprequest.method == 'OPTIONS':
            return self._handle_options_request()
        
        # Redirect to the new diagnostic endpoint
        return self.auth_diagnostic(**kw)

    def _validate_api_key(self):
        """
        Simplified API key validation method that uses HTTP Basic Auth or API key.
        Returns a tuple (is_valid, result) where:
        - is_valid: boolean indicating if authentication is valid
        - result: the user object if valid, error dict with specific message if not
        """
        # Check for X-API-Key first
        api_key = request.httprequest.headers.get('X-API-Key')
        if api_key:
            try:
                if not hasattr(request, 'env') or request.env is None or not isinstance(request.env, Environment):
                    _logger.error(f"Invalid request.env: type={type(request.env)}, value={request.env}")
                    return False, {"error": "Internal error: Invalid environment configuration"}

                api_key_record = request.env['res.users'].sudo().search([('api_key', '=', api_key)], limit=1)
                if not api_key_record:
                    _logger.warning("API key not found")
                    return False, {"error": "Authentication failed: Invalid API key"}

                user = request.env['res.users'].sudo().browse(api_key_record.user_id.id)
                if not user.exists() or not user.active:
                    _logger.warning(f"User not found or inactive for API key")
                    return False, {"error": "Authentication failed: User not found or inactive"}

                _logger.info(f"API key authentication successful for user: {user.login}")
                return True, user
            except Exception as e:
                _logger.error(f"API key auth error: {str(e)}")
                return False, {"error": f"Authentication error: {str(e)}"}

        # Get authentication from Basic Auth or JWT
        auth_header = request.httprequest.headers.get('Authorization')
        
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
                employee_id = payload.get('employee_id')
                if not user_id or not employee_id:
                    _logger.warning("JWT validation failed: Missing user_id or employee_id in payload")
                    return False, {"error": "Authentication failed: Invalid JWT payload"}
                
                user = request.env['res.users'].sudo().browse(user_id)
                if not user.exists():
                    _logger.warning("JWT validation failed: User ID %s not found", user_id)
                    return False, {"error": "Authentication failed: User not found"}
                
                employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id), ('id', '=', employee_id)], limit=1)
                if not employee:
                    _logger.warning("JWT validation failed: Employee ID %s not found or not linked to user", employee_id)
                    return False, {"error": "Authentication failed: Invalid employee ID"}
                
                _logger.info("JWT authentication successful for user: %s, employee: %s", user.login, employee_id)
                return True, user
            except jwt.ExpiredSignatureError:
                _logger.warning("JWT validation failed: Token expired")
                return False, {"error": "Authentication failed: Token expired"}
            except jwt.InvalidTokenError as e:
                _logger.warning("JWT validation failed: %s", str(e))
                return False, {"error": "Authentication failed: Invalid token"}
            except Exception as e:
                _logger.error("JWT authentication error: %s", str(e))
                return False, {"error": f"Authentication error: {str(e)}"}

        # 2. Handle Basic Authentication
        if auth_header and auth_header.startswith('Basic '):
            try:
                if not hasattr(request, 'env') or request.env is None or not isinstance(request.env, Environment):
                    _logger.error(f"Invalid request.env: type={type(request.env)}, value={request.env}")
                    return False, {"error": "Internal error: Invalid environment configuration"}

                _logger.debug(f"Raw auth_header: {auth_header}")
                auth_decoded = base64.b64decode(auth_header[6:].strip()).decode('utf-8')
                login, password = auth_decoded.split(':', 1)
                _logger.debug(f"Basic Auth attempt with login: {login}")
                _logger.debug(f"Password length: {len(password)}")
                
                try:
                    user = request.env['res.users'].sudo().search([('login', '=', login)], limit=1)
                    if not user:
                        _logger.warning(f"Basic Auth failed: User not found with login {login}")
                        return False, {"error": "Authentication failed: Invalid login or password"}
                    
                    if not user.active:
                        _logger.warning(f"Basic Auth failed: User {login} is not active")
                        return False, {"error": "Authentication failed: User account is inactive"}
                    
                    _logger.debug(f"User ID: {user.id}, Has API access: {user.has_group('base.group_user')}")
                    
                    # Method 1: Try _check_credentials
                    try:
                        user.sudo()._check_credentials(password)
                        _logger.info(f"Basic Auth successful for user: {user.login} (using _check_credentials)")
                        return True, user
                    except Exception as cred_error:
                        _logger.debug(f"_check_credentials failed: {str(cred_error)}")
                    
                    # Method 2: Try direct authenticate method
                    try:
                        db_name = request.env.cr.dbname
                        uid = request.env['res.users'].authenticate(db_name, login, password)
                        if uid:
                            authenticated_user = request.env['res.users'].sudo().browse(uid)
                            _logger.info(f"Basic Auth successful for user: {authenticated_user.login} (using authenticate)")
                            return True, authenticated_user
                        else:
                            _logger.debug(f"authenticate method returned: {uid}")
                    except Exception as auth_error:
                        _logger.debug(f"authenticate method failed: {str(auth_error)}")
                    
                    # Method 3: Check if it's an API key instead of password
                    try:
                        api_keys = request.env['res.users.apikeys'].sudo().search([('user_id', '=', user.id)])
                        if api_keys:
                            _logger.debug(f"User has {len(api_keys)} API keys")
                            for api_key in api_keys:
                                if api_key.key and api_key.key == password:
                                    _logger.info(f"Basic Auth successful for user: {user.login} (using API key)")
                                    return True, user
                        else:
                            _logger.debug("User has no API keys")
                    except Exception as api_error:
                        _logger.debug(f"API key check failed: {str(api_error)}")
                    
                    _logger.warning(f"Basic Auth failed: All authentication methods failed for user {login}")
                    return False, {"error": "Authentication failed: Invalid login or password"}
                        
                except Exception as auth_error:
                    _logger.error(f"Basic Auth authentication error for user {login}: {str(auth_error)}")
                    return False, {"error": "Authentication failed: Invalid login or password"}
                        
            except ValueError as ve:
                _logger.warning(f"Basic Auth failed: Invalid format - {str(ve)}")
                return False, {"error": "Authentication failed: Invalid Basic Auth format (should be 'login:password')"}
            except Exception as e:
                _logger.error(f"Basic Auth decoding error: {str(e)}")
                return False, {"error": f"Authentication error: {str(e)}"}
        
        _logger.warning("Authentication failed: No valid authentication method provided")
        return False, {"error": "Authentication required: missing Authorization header"}

    @http.route('/api/auth/get_api_key', type='http', auth='user', methods=['GET'], csrf=False)
    def get_api_key(self, **kw):
        """Generate a session-based API key for testing"""
        headers = [('Content-Type', 'application/json')]
        
        try:
            # Generate a new API key (UUID)
            api_key = str(uuid.uuid4())
            
            # Store in session
            request.session['api_key'] = api_key
            request.session['user_id'] = request.env.user.id
            
            result = {
                'success': True,
                'api_key': api_key,
                'user_id': request.env.user.id,
                'username': request.env.user.name,
                'instructions': 'Use this API key in the X-API-Key header for subsequent requests'
            }
            
            response = request.make_response(json.dumps(result), headers=headers)
            return self._add_cors_headers(response)
        except Exception as e:
            _logger.error("Error generating API key: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': f"Failed to generate API key: {str(e)}"
            }
            response = request.make_response(json.dumps(result), headers=headers, status=500)
            return self._add_cors_headers(response) 