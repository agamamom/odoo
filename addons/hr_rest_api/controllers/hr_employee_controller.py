from odoo import http, _
from odoo.http import request, Response
from odoo.addons.hr_rest_api.controllers.main import HrRestApiController
import json
import logging
import traceback
from werkzeug.exceptions import BadRequest
from datetime import datetime, date
import base64
import io

_logger = logging.getLogger(__name__)

class HrEmployeeController(HrRestApiController):
    """
    Controller to expose the ORM methods from hr_employee.py as API endpoints
    """
    
    # CORS preflight handler for all routes
    @http.route([
        '/api/employee/profile',
        '/api/employee/project-summary',
        '/api/employee/skill-summary',
        '/api/employee/shift-summary',
        '/api/employee/contract-summary',
        '/api/employee/tax-summary',
        '/api/employee/export/excel',
        '/api/employee/export/pdf',
        '/api/employee/export/labor-report',
        '/api/employee/export/bhxh-c12ts',
        '/api/employee/export/bhxh-d02ts',
        '/api/employee/export/tax-report',
        '/api/employee/export/tax-finalization',
        '/api/employee/bhxh/create-profile',
        '/api/employee/bhxh/send-profile',
        '/api/employee/bhxh/respond-profile',
        '/api/employee/bhxh/mark-done',
        '/api/employee/contract/check-expiry',
        '/api/employee/contract/generate-template',
        '/api/employee/skill/check',
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_employee_controller_endpoints(self, **kw):
        """Handle OPTIONS requests for CORS preflight"""
        return self._handle_options_request()
    
    def _prepare_response(self, result, status=200):
        """Helper to prepare a JSON response with CORS headers"""
        headers = [('Content-Type', 'application/json')]
        response = request.make_response(json.dumps(result), headers=headers, status=status)
        return self._add_cors_headers(response)
    
    def _get_employee_from_user(self, include_current_user=False):
        """
        Helper to get the employee record from the authenticated user.
        Returns (employee, error_response) where error_response is None if successful.
        """
        # Validate API key
        is_valid, result = self._validate_api_key()
        if not is_valid:
            return None, self._prepare_response(result, 401)
        
        user = result
        _logger.info("user= %s", user.id)
        # If include_current_user is True, return the user even if not an employee
        if include_current_user:
            return user, None
        
        # Look up employee record for the user
        employee = request.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
        if not employee:
            result = {
                'success': False,
                'error': 'User is not associated with an employee record.',
                'status_code': 404
            }
            return None, self._prepare_response(result, 404)
        
        return employee, None
    
    # ===== EMPLOYEE PROFILE ENDPOINTS =====
    
    @http.route('/api/employee/profile', type='http', auth='public', methods=['GET'], csrf=False)
    def get_employee_profile(self, **kw):
        _logger.info("GET /api/employee/profile called with params: %s", kw)
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                _logger.warning("Access denied or invalid user: %s", error_response)
                return error_response

            # Log chi tiết employee
            _logger.debug(
                "Fetched employee id=%s name=%s company=%s",
                employee.id, employee.name, employee.company_id.name if employee.company_id else None
            )
            

            result = {
                "success": True,
                "data": {
                    "id": employee.id,
                    "name": employee.name or "",
                    "department_id": employee.department_id.id if employee.department_id else False,
                    "department_name": employee.department_id.name if employee.department_id else "",
                    "job_id": employee.job_id.id if employee.job_id else False,
                    "job_position": employee.job_id.name if employee.job_id else "",
                    "parent_id": employee.parent_id.id if employee.parent_id else False,
                    "manager_name": employee.parent_id.name if employee.parent_id else "",
                    "work_email": employee.work_email or "",
                    "work_phone": employee.work_phone or "",
                    "mobile_phone": employee.mobile_phone or "",
                    "private_email": employee.private_email or "",
                    "company_id": employee.company_id.id if employee.company_id else False,
                    "company_name": employee.company_id.name if employee.company_id else "",
                    # Vietnam-specific fields
                    "bhxh_code": employee.bhxh_code or "",
                    "bhyt_code": employee.bhyt_code or "",
                    "bhtn_code": employee.bhtn_code or "",
                    "kcb_place": employee.kcb_place or "",
                    "labor_contract_number": employee.labor_contract_number or "",
                    "labor_contract_sign_date": employee.labor_contract_sign_date.strftime('%Y-%m-%d') if employee.labor_contract_sign_date else "",
                    "labor_contract_expiry_date": employee.labor_contract_expiry_date.strftime('%Y-%m-%d') if employee.labor_contract_expiry_date else "",
                    "labor_contract_type": employee.labor_contract_type or "",
                    "detailed_contract_type": employee.detailed_contract_type or "",
                    "minimum_wage_region": employee.minimum_wage_region or "",
                    "personal_tax_code": employee.personal_tax_code or "",
                }
            }

            _logger.info("Successfully prepared profile for employee id=%s", employee.id)
            _logger.info("name= %s", employee.name)
            return self._prepare_response(result)

        except Exception as e:
            # Ghi log lỗi chi tiết bao gồm traceback
            _logger.exception("Error in get_employee_profile")
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500,
                'debug': {
                    'exception': str(e),
                    'traceback': traceback.format_exc()
                } if request.env.user.has_group('base.group_system') else None
            }
            return self._prepare_response(result, 500)
    
    # ===== PROJECT SUMMARY ENDPOINTS =====
    
    @http.route('/api/employee/project-summary', type='json', auth='public', methods=['POST'], csrf=False)
    def get_project_summary(self, **kw):
        """Get employee project assignment summary"""
        try:
            # Get the authenticated employee or error response
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response

            # Fetch project performance summary
            project_summary = employee.get_project_performance_summary()

            # Return JSON response with success and data
            return {
                'success': True,
                'data': project_summary
            }

        except Exception as e:
            _logger.error("Error in get_project_summary: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
    
    # ===== SKILL SUMMARY ENDPOINTS =====
    
    @http.route('/api/employee/skill-summary', type='json', auth='public', methods=['POST'], csrf=False)
    def get_skill_summary(self, **kw):
        """Get employee skill summary"""
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            skill_summary = employee.get_skill_performance_summary()
            
            return {
                "success": True,
                "data": skill_summary
            }
            
        except Exception as e:
            _logger.error("Error in get_skill_summary: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
    
    @http.route('/api/employee/skill/check', type='json', auth='public', methods=['POST'], csrf=False)
    def check_skill_for_task(self, **kw):
        """
        Check if employee has required skills for a task
        
        Required params:
        - required_skills: List of dict with skill_name and skill_level
          Example: [{"skill_name": "Python", "skill_level": "advanced"}]
        """
        try:
            employee, error = self._get_employee_from_user()
            if error:
                return error
            
            required_skills = kw.get('required_skills', [])
            if not required_skills:
                return {
                    'success': False,
                    'error': 'No required skills provided',
                    'status_code': 400
                }
            
            has_skills = employee.has_skill_for_task(required_skills)
            
            return {
                'success': True,
                'has_required_skills': has_skills
            }
            
        except Exception as e:
            _logger.error("Error in check_skill_for_task: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
    
    # ===== SHIFT SUMMARY ENDPOINTS =====
    
    @http.route('/api/employee/shift-summary', type='http', auth='public', methods=['GET'], csrf=False)
    def get_shift_summary(self, **kw):
        """Get employee shift summary"""
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            shift_summary = employee.get_shift_summary()
            
            result = {
                "success": True,
                "data": shift_summary
            }
            
            return self._prepare_response(result)
            
        except Exception as e:
            _logger.error("Error in get_shift_summary: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500)
    
    # ===== CONTRACT SUMMARY ENDPOINTS =====
    
    @http.route('/api/employee/contract-summary', type='http', auth='public', methods=['GET'], csrf=False)
    def get_contract_summary(self, **kw):
        """Get employee contract summary"""
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            contract_summary = employee.get_contract_summary()
            
            result = {
                "success": True,
                "data": contract_summary
            }
            
            return self._prepare_response(result)
            
        except Exception as e:
            _logger.error("Error in get_contract_summary: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500)
    
    @http.route('/api/employee/contract/check-expiry', type='http', auth='public', methods=['POST'], csrf=False)
    def check_contract_expiry(self, **kw):
        """Check if employee contract has expired and update status"""
        try:
            employee, error = self._get_employee_from_user()
            if error:
                return error
            
            employee.check_contract_expiry()
            
            return {
                'success': True,
                'message': 'Contract expiry check completed'
            }
            
        except Exception as e:
            _logger.error("Error in check_contract_expiry: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
    
    @http.route('/api/employee/contract/generate-template', type='http', auth='public', methods=['GET'], csrf=False)
    def generate_contract_template(self, **kw):
        """
        Generate a contract template for the employee
        
        Optional params:
        - contract_type: Type of contract (definite, indefinite, etc.)
        """
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            contract_type = kw.get('contract_type', 'definite')
            template = employee.generate_contract_template(contract_type)
            
            result = {
                "success": True,
                "data": {
                    "contract_type": contract_type,
                    "template": template
                }
            }
            
            return self._prepare_response(result)
            
        except Exception as e:
            _logger.error("Error in generate_contract_template: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500)
    
    # ===== TAX SUMMARY ENDPOINTS =====
    
    @http.route('/api/employee/tax-summary', type='http', auth='public', methods=['GET'], csrf=False)
    def get_tax_summary(self, **kw):
        """Get employee personal income tax summary"""
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            tax_summary = employee.get_personal_income_tax_summary()
            
            result = {
                "success": True,
                "data": tax_summary
            }
            
            return self._prepare_response(result)
            
        except Exception as e:
            _logger.error("Error in get_tax_summary: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500)
    
    # ===== BHXH (VIETNAMESE SOCIAL INSURANCE) ENDPOINTS =====
    
    @http.route('/api/employee/bhxh/create-profile', type='json', auth='public', methods=['POST'], csrf=False)
    def create_bhxh_profile(self, **kw):
        """
        Create BHXH profile for the employee
        
        Optional params:
        - action_type: Type of BHXH action (register, update, etc.)
        """
        try:
            employee, error = self._get_employee_from_user()
            if error:
                return error
            
            action_type = kw.get('action_type', 'register')
            history = employee.create_bhxh_profile(action_type)
            
            return {
                'success': True,
                'profile_id': history.id,
                'message': f'BHXH profile created with action type: {action_type}'
            }
            
        except Exception as e:
            _logger.error("Error in create_bhxh_profile: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
    
    @http.route('/api/employee/bhxh/send-profile', type='json', auth='public', methods=['POST'], csrf=False)
    def send_bhxh_profile(self, **kw):
        """Send BHXH profile for the employee"""
        try:
            employee, error = self._get_employee_from_user()
            if error:
                return error
            
            success = employee.send_bhxh_profile()
            
            return {
                'success': success,
                'transaction_code': employee.bhxh_transaction_code,
                'status': employee.bhxh_profile_status
            }
            
        except Exception as e:
            _logger.error("Error in send_bhxh_profile: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
    
    @http.route('/api/employee/bhxh/respond-profile', type='json', auth='public', methods=['POST'], csrf=False)
    def receive_bhxh_response(self, **kw):
        """
        Receive response for BHXH profile
        
        Optional params:
        - response_note: Response note
        - file_response: Base64 encoded response file
        """
        try:
            employee, error = self._get_employee_from_user()
            if error:
                return error
            
            response_note = kw.get('response_note', 'Phản hồi thành công')
            file_response = kw.get('file_response', None)
            
            success = employee.receive_bhxh_response(response_note, file_response)
            
            return {
                'success': success,
                'status': employee.bhxh_profile_status,
                'response_note': employee.bhxh_response_note
            }
            
        except Exception as e:
            _logger.error("Error in receive_bhxh_response: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
    
    @http.route('/api/employee/bhxh/mark-done', type='json', auth='public', methods=['POST'], csrf=False)
    def mark_bhxh_done(self, **kw):
        """Mark BHXH profile as done"""
        try:
            employee, error = self._get_employee_from_user()
            if error:
                return error
            
            success = employee.mark_bhxh_done()
            
            return {
                'success': success,
                'status': employee.bhxh_profile_status
            }
            
        except Exception as e:
            _logger.error("Error in mark_bhxh_done: %s", str(e), exc_info=True)
            return {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
    
    # ===== EXPORT ENDPOINTS =====
    
    @http.route('/api/employee/export/excel', type='http', auth='public', methods=['GET'], csrf=False)
    def export_employee_list_excel(self, **kw):
        """
        Export employee list to Excel
        
        Optional params:
        - fields: Comma-separated list of fields to export
        """
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            fields_str = kw.get('fields', None)
            fields_to_export = fields_str.split(',') if fields_str else None
            
            filename, file_content = employee.export_employee_list_excel(fields_to_export)
            
            headers = [
                ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(file_content)))
            ]
            
            response = request.make_response(file_content, headers=headers)
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error in export_employee_list_excel: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500)
    
    @http.route('/api/employee/export/pdf', type='http', auth='public', methods=['GET'], csrf=False)
    def export_employee_list_pdf(self, **kw):
        """
        Export employee list to PDF
        
        Optional params:
        - fields: Comma-separated list of fields to export
        """
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            fields_str = kw.get('fields', None)
            fields_to_export = fields_str.split(',') if fields_str else None
            
            filename, file_content = employee.export_employee_list_pdf(fields_to_export)
            
            headers = [
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(file_content)))
            ]
            
            response = request.make_response(file_content, headers=headers)
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error in export_employee_list_pdf: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500)
    
    @http.route('/api/employee/export/labor-report', type='http', auth='public', methods=['GET'], csrf=False)
    def export_labor_report(self, **kw):
        """Export state report on labor usage"""
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            filename, file_content = employee.export_state_report_labor_usage()
            
            headers = [
                ('Content-Type', 'text/csv'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(file_content)))
            ]
            
            response = request.make_response(file_content, headers=headers)
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error in export_labor_report: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500)
    
    @http.route('/api/employee/export/bhxh-c12ts', type='http', auth='public', methods=['GET'], csrf=False)
    def export_bhxh_c12ts(self, **kw):
        """Export BHXH report C12-TS"""
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            filename, file_content = employee.export_bhxh_report_c12ts()
            
            headers = [
                ('Content-Type', 'text/csv'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(file_content)))
            ]
            
            response = request.make_response(file_content, headers=headers)
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error in export_bhxh_c12ts: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500)
    
    @http.route('/api/employee/export/bhxh-d02ts', type='http', auth='public', methods=['GET'], csrf=False)
    def export_bhxh_d02ts(self, **kw):
        """Export BHXH report D02-TS"""
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            filename, file_content = employee.export_bhxh_report_d02ts()
            
            headers = [
                ('Content-Type', 'text/csv'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(file_content)))
            ]
            
            response = request.make_response(file_content, headers=headers)
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error in export_bhxh_d02ts: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500)
    
    @http.route('/api/employee/export/tax-report', type='http', auth='public', methods=['GET'], csrf=False)
    def export_tax_report(self, **kw):
        """Export tax report on personal income"""
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            filename, file_content = employee.export_tax_report_personal_income()
            
            headers = [
                ('Content-Type', 'text/csv'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(file_content)))
            ]
            
            response = request.make_response(file_content, headers=headers)
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error in export_tax_report: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500)
    
    @http.route('/api/employee/export/tax-finalization', type='http', auth='public', methods=['GET'], csrf=False)
    def export_tax_finalization(self, **kw):
        """
        Export tax finalization report
        
        Required params:
        - year: Year for tax finalization
        """
        try:
            employee, error_response = self._get_employee_from_user()
            if error_response:
                return error_response
            
            year_str = kw.get('year')
            if not year_str:
                result = {
                    'success': False,
                    'error': 'Year parameter is required',
                    'status_code': 400
                }
                return self._prepare_response(result, 400)
            
            try:
                year = int(year_str)
            except ValueError:
                result = {
                    'success': False,
                    'error': 'Year must be a valid integer',
                    'status_code': 400
                }
                return self._prepare_response(result, 400)
            
            export_result = employee.export_tax_finalization_report(year)
            if not export_result:
                result = {
                    'success': False,
                    'error': f'No tax finalization data found for year {year}',
                    'status_code': 404
                }
                return self._prepare_response(result, 404)
            
            filename, file_content = export_result
            
            headers = [
                ('Content-Type', 'text/csv'),
                ('Content-Disposition', f'attachment; filename="{filename}"'),
                ('Content-Length', str(len(file_content)))
            ]
            
            response = request.make_response(file_content, headers=headers)
            return self._add_cors_headers(response)
            
        except Exception as e:
            _logger.error("Error in export_tax_finalization: %s", str(e), exc_info=True)
            result = {
                'success': False,
                'error': 'Server error occurred while processing your request.',
                'status_code': 500
            }
            return self._prepare_response(result, 500) 