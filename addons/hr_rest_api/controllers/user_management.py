from odoo import http, _
from odoo.http import request, Response
from odoo.addons.hr_rest_api.controllers.main import HrRestApiController
import json
import logging
from werkzeug.exceptions import BadRequest, Forbidden
from werkzeug.wrappers import Response as WerkzeugResponse
from datetime import datetime

_logger = logging.getLogger(__name__)

class UserManagementAPI(HrRestApiController):
    
    def _validate_admin_rights(self, user):
        """Check if the user has user management rights"""
        return user.has_group('base.group_erp_manager') or user.has_group('base.group_system')
    
    # CORS preflight handler for all routes
    @http.route([
        '/api/users',
        '/api/users/<int:user_id>',
        '/api/users/search',
        '/api/users/count',
        '/api/users/check-email',
        '/api/users/bulk',
        '/api/users/activate/<int:user_id>',
        '/api/users/deactivate/<int:user_id>',
        '/api/public/register'
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_user_endpoints(self, **kw):
        """Handle OPTIONS requests for CORS preflight"""
        return self._handle_options_request()
    
    # ========== CREATE ==========
    @http.route('/api/users', type='json', auth='public', methods=['POST'], csrf=False)
    def create_user(self, **kw):
        """
        Create a new user
        
        Required params:
        - name: User's full name
        - login: User's email (used as login)
        - password: Initial password
        
        Optional params:
        - lang: Language code (e.g., 'en_US')
        - tz: Timezone (e.g., 'Europe/Brussels')
        - phone: Phone number
        - mobile: Mobile number
        - active: Boolean, active status
        - company_id: ID of the company
        - groups_id: List of security group IDs
        """
        # Validate API key and admin rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            return result
        
        user = result
        if not self._validate_admin_rights(user):
            return {"error": "Insufficient rights to create users"}
        
        # Validate required fields
        required_fields = ['name', 'login', 'password']
        for field in required_fields:
            if field not in kw:
                return {"error": f"Missing required field: {field}"}
        
        # Check if login (email) already exists
        if request.env['res.users'].sudo().search_count([('login', '=', kw['login'])]) > 0:
            return {"error": "Email already exists"}
        
        # Prepare user values
        user_values = {
            'name': kw['name'],
            'login': kw['login'],
            'password': kw['password'],
            'active': kw.get('active', True),
        }
        
        # Add optional fields if provided
        optional_fields = ['lang', 'tz', 'phone', 'mobile']
        for field in optional_fields:
            if field in kw:
                user_values[field] = kw[field]
        
        # Handle company
        if 'company_id' in kw:
            company_id = int(kw['company_id'])
            company = request.env['res.company'].sudo().browse(company_id)
            if company.exists():
                user_values['company_id'] = company_id
                user_values['company_ids'] = [(4, company_id)]
        
        # Create user
        try:
            new_user = request.env['res.users'].sudo().create(user_values)
            
            # Handle groups if provided
            if 'groups_id' in kw and isinstance(kw['groups_id'], list):
                groups_to_add = []
                for group_id in kw['groups_id']:
                    groups_to_add.append((4, int(group_id)))
                
                if groups_to_add:
                    new_user.sudo().write({'groups_id': groups_to_add})
            
            return {
                "success": True,
                "id": new_user.id,
                "name": new_user.name,
                "login": new_user.login
            }
        except Exception as e:
            _logger.error("Error creating user: %s", str(e))
            return {"error": f"Failed to create user: {str(e)}"}
    
    # ========== READ ==========
    @http.route('/api/users/<int:user_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_user(self, user_id, **kw):
        """Get user details by ID"""
        # Validate API key
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        
        # Check permissions - users can view their own data or admin can view any
        if user.id != user_id and not self._validate_admin_rights(user):
            result = {"error": "Access denied"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the requested user
        target_user = request.env['res.users'].sudo().browse(user_id)
        if not target_user.exists():
            result = {"error": "User not found"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Format user data
        user_data = {
            "id": target_user.id,
            "name": target_user.name,
            "login": target_user.login,
            "active": target_user.active,
            "lang": target_user.lang,
            "tz": target_user.tz,
            "phone": target_user.phone or "",
            "mobile": target_user.mobile or "",
            "company_id": target_user.company_id.id if target_user.company_id else False,
            "company_name": target_user.company_id.name if target_user.company_id else "",
            "groups": [{
                "id": group.id,
                "name": group.name,
                "category": group.category_id.name if group.category_id else "Uncategorized"
            } for group in target_user.groups_id] if self._validate_admin_rights(user) else []
        }
        
        result = {"success": True, "user": user_data}
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/users', type='http', auth='public', methods=['GET'], csrf=False)
    def get_users(self, **kw):
        """
        Get a list of users with optional filtering
        
        Optional params:
        - limit: Maximum number of records to return
        - offset: Number of records to skip
        - active: Filter by active status (true/false)
        - search: Search term for name or login
        """
        # Validate API key and admin rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_admin_rights(user):
            result = {"error": "Insufficient rights to list users"}
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
        
        # Search term
        if 'search' in kw and kw['search']:
            search_term = kw['search']
            domain.append(['|', ('name', 'ilike', search_term), ('login', 'ilike', search_term)])
        
        # Get users
        users = request.env['res.users'].sudo().search(domain, limit=limit, offset=offset)
        total_count = request.env['res.users'].sudo().search_count(domain)
        
        # Format response
        users_data = [{
            "id": u.id,
            "name": u.name,
            "login": u.login,
            "active": u.active,
            "company_name": u.company_id.name if u.company_id else ""
        } for u in users]
        
        result = {
            "success": True,
            "count": len(users_data),
            "total": total_count,
            "users": users_data
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    @http.route('/api/users/search', type='http', auth='public', methods=['GET'], csrf=False)
    def search_users(self, **kw):
        """
        Search for users with advanced filtering
        
        Required params:
        - query: Search term
        
        Optional params:
        - limit: Maximum number of records to return
        - offset: Number of records to skip
        - fields: Comma-separated list of fields to search in (default: name,login)
        """
        # Validate API key and admin rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_admin_rights(user):
            result = {"error": "Insufficient rights to search users"}
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
        fields = kw.get('fields', 'name,login').split(',')
        
        # Validate fields
        valid_fields = ['name', 'login', 'email', 'phone', 'mobile']
        search_fields = [f for f in fields if f in valid_fields]
        
        if not search_fields:
            search_fields = ['name', 'login']
        
        # Build domain
        domain = []
        for field in search_fields:
            if len(domain) > 0:
                domain.insert(0, '|')
            domain.append((field, 'ilike', query))
        
        # Get users
        users = request.env['res.users'].sudo().search(domain, limit=limit, offset=offset)
        total_count = request.env['res.users'].sudo().search_count(domain)
        
        # Format response
        users_data = [{
            "id": u.id,
            "name": u.name,
            "login": u.login,
            "active": u.active
        } for u in users]
        
        result = {
            "success": True,
            "count": len(users_data),
            "total": total_count,
            "users": users_data
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/users/count', type='http', auth='public', methods=['GET'], csrf=False)
    def count_users(self, **kw):
        """Get user counts with optional filtering"""
        # Validate API key and admin rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_admin_rights(user):
            result = {"error": "Insufficient rights to count users"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get counts
        total_users = request.env['res.users'].sudo().search_count([])
        active_users = request.env['res.users'].sudo().search_count([('active', '=', True)])
        inactive_users = request.env['res.users'].sudo().search_count([('active', '=', False)])
        
        result = {
            "success": True,
            "total": total_users,
            "active": active_users,
            "inactive": inactive_users
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    @http.route('/api/users/check-email', type='http', auth='public', methods=['GET'], csrf=False)
    def check_email_exists(self, **kw):
        """Check if an email (login) already exists"""
        # Validate API key and admin rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_admin_rights(user):
            result = {"error": "Insufficient rights to check email"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Validate required parameters
        if 'email' not in kw or not kw['email']:
            result = {"error": "Email parameter is required"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        email = kw['email']
        exists = request.env['res.users'].sudo().search_count([('login', '=', email)]) > 0
        
        result = {
            "success": True,
            "email": email,
            "exists": exists
        }
        
        response = request.make_response(json.dumps(result), 
                                       headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    # ========== UPDATE ==========
    @http.route('/api/users/<int:user_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_user(self, user_id, **kw):
        """
        Update an existing user
        
        Optional params:
        - name: User's full name
        - login: User's email (used as login)
        - password: New password
        - lang: Language code
        - tz: Timezone
        - phone: Phone number
        - mobile: Mobile number
        - groups_id: List of security group IDs to set
        - groups_add: List of security group IDs to add
        - groups_remove: List of security group IDs to remove
        """
        # Validate API key and admin rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            return result
        
        user = result
        if not self._validate_admin_rights(user):
            return {"error": "Insufficient rights to update users"}
        
        # Get the target user
        target_user = request.env['res.users'].sudo().browse(user_id)
        if not target_user.exists():
            return {"error": "User not found"}
        
        # Check if we're trying to update login and it already exists
        if 'login' in kw and kw['login'] != target_user.login:
            if request.env['res.users'].sudo().search_count([('login', '=', kw['login'])]) > 0:
                return {"error": "Email already exists"}
        
        # Prepare values to update
        update_values = {}
        for field in ['name', 'login', 'password', 'lang', 'tz', 'phone', 'mobile']:
            if field in kw:
                update_values[field] = kw[field]
        
        # Handle company
        if 'company_id' in kw:
            company_id = int(kw['company_id'])
            company = request.env['res.company'].sudo().browse(company_id)
            if company.exists():
                update_values['company_id'] = company_id
                update_values['company_ids'] = [(4, company_id)]
        
        # Update user
        try:
            if update_values:
                target_user.sudo().write(update_values)
            
            # Handle groups
            if 'groups_id' in kw and isinstance(kw['groups_id'], list):
                # Replace all groups with the provided list
                groups_commands = [(6, 0, [int(g) for g in kw['groups_id']])]
                target_user.sudo().write({'groups_id': groups_commands})
            else:
                # Handle adding groups
                if 'groups_add' in kw and isinstance(kw['groups_add'], list):
                    groups_to_add = []
                    for group_id in kw['groups_add']:
                        groups_to_add.append((4, int(group_id)))
                    
                    if groups_to_add:
                        target_user.sudo().write({'groups_id': groups_to_add})
                
                # Handle removing groups
                if 'groups_remove' in kw and isinstance(kw['groups_remove'], list):
                    groups_to_remove = []
                    for group_id in kw['groups_remove']:
                        groups_to_remove.append((3, int(group_id)))
                    
                    if groups_to_remove:
                        target_user.sudo().write({'groups_id': groups_to_remove})
            
            return {
                "success": True,
                "id": target_user.id,
                "name": target_user.name,
                "login": target_user.login,
                "message": "User updated successfully"
            }
        except Exception as e:
            _logger.error("Error updating user: %s", str(e))
            return {"error": f"Failed to update user: {str(e)}"}
    
    # ========== ACTIVATE/DEACTIVATE ==========
    @http.route('/api/users/activate/<int:user_id>', type='http', auth='public', methods=['POST'], csrf=False)
    def activate_user(self, user_id, **kw):
        """Activate a user"""
        # Validate API key and admin rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_admin_rights(user):
            result = {"error": "Insufficient rights to activate users"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the target user
        target_user = request.env['res.users'].sudo().browse(user_id)
        if not target_user.exists():
            result = {"error": "User not found"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Don't allow activating protected system users
        if target_user.id <= 2:  # admin and system users
            result = {"error": "Cannot modify system users"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        try:
            target_user.sudo().write({'active': True})
            result = {
                "success": True,
                "id": target_user.id,
                "active": True,
                "message": "User activated successfully"
            }
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        except Exception as e:
            _logger.error("Error activating user: %s", str(e))
            result = {"error": f"Failed to activate user: {str(e)}"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
    
    @http.route('/api/users/deactivate/<int:user_id>', type='http', auth='public', methods=['POST'], csrf=False)
    def deactivate_user(self, user_id, **kw):
        """Deactivate a user"""
        # Validate API key and admin rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_admin_rights(user):
            result = {"error": "Insufficient rights to deactivate users"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the target user
        target_user = request.env['res.users'].sudo().browse(user_id)
        if not target_user.exists():
            result = {"error": "User not found"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Don't allow deactivating protected system users
        if target_user.id <= 2:  # admin and system users
            result = {"error": "Cannot modify system users"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Don't allow deactivating self
        if target_user.id == user.id:
            result = {"error": "Cannot deactivate your own account"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        try:
            target_user.sudo().write({'active': False})
            result = {
                "success": True,
                "id": target_user.id,
                "active": False,
                "message": "User deactivated successfully"
            }
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        except Exception as e:
            _logger.error("Error deactivating user: %s", str(e))
            result = {"error": f"Failed to deactivate user: {str(e)}"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
    
    # ========== DELETE ==========
    @http.route('/api/users/<int:user_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_user(self, user_id, **kw):
        """Delete a user (or archive if permanent=false)"""
        # Validate API key and admin rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        user = result
        if not self._validate_admin_rights(user):
            result = {"error": "Insufficient rights to delete users"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the target user
        target_user = request.env['res.users'].sudo().browse(user_id)
        if not target_user.exists():
            result = {"error": "User not found"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Don't allow deleting protected system users
        if target_user.id <= 2:  # admin and system users
            result = {"error": "Cannot delete system users"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Don't allow deleting self
        if target_user.id == user.id:
            result = {"error": "Cannot delete your own account"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Check if permanent deletion is requested
        permanent = kw.get('permanent', 'false').lower() in ['true', '1', 't', 'y', 'yes']
        
        try:
            if permanent:
                # Permanent deletion - may fail due to constraints
                target_user.sudo().unlink()
                message = "User deleted permanently"
            else:
                # Archive instead of delete (safer)
                target_user.sudo().write({'active': False})
                message = "User archived successfully"
            
            result = {
                "success": True,
                "id": user_id,
                "message": message
            }
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        except Exception as e:
            _logger.error("Error deleting user: %s", str(e))
            result = {"error": f"Failed to delete user: {str(e)}"}
            response = request.make_response(json.dumps(result), 
                                           headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
    
    # ========== BULK OPERATIONS ==========
    @http.route('/api/users/bulk', type='json', auth='public', methods=['POST'], csrf=False)
    def bulk_create_users(self, **kw):
        """
        Create multiple users at once
        
        Required param:
        - users: List of user objects with required fields (name, login, password)
        """
        # Validate API key and admin rights
        is_valid, result = self._validate_api_key()
        if not is_valid:
            return result
        
        user = result
        if not self._validate_admin_rights(user):
            return {"error": "Insufficient rights to create users"}
        
        # Validate users parameter
        if 'users' not in kw or not isinstance(kw['users'], list):
            return {"error": "Missing or invalid 'users' parameter"}
        
        if not kw['users']:
            return {"error": "Empty users list"}
        
        # Process each user
        results = []
        for user_data in kw['users']:
            # Validate required fields
            required_fields = ['name', 'login', 'password']
            missing_fields = [field for field in required_fields if field not in user_data]
            
            if missing_fields:
                results.append({
                    "success": False,
                    "login": user_data.get('login', 'Unknown'),
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                })
                continue
            
            # Check if login (email) already exists
            if request.env['res.users'].sudo().search_count([('login', '=', user_data['login'])]) > 0:
                results.append({
                    "success": False,
                    "login": user_data['login'],
                    "error": "Email already exists"
                })
                continue
            
            # Prepare user values
            user_values = {
                'name': user_data['name'],
                'login': user_data['login'],
                'password': user_data['password'],
                'active': user_data.get('active', True),
            }
            
            # Add optional fields if provided
            optional_fields = ['lang', 'tz', 'phone', 'mobile']
            for field in optional_fields:
                if field in user_data:
                    user_values[field] = user_data[field]
            
            # Handle company
            if 'company_id' in user_data:
                company_id = int(user_data['company_id'])
                company = request.env['res.company'].sudo().browse(company_id)
                if company.exists():
                    user_values['company_id'] = company_id
                    user_values['company_ids'] = [(4, company_id)]
            
            # Create user
            try:
                new_user = request.env['res.users'].sudo().create(user_values)
                
                # Handle groups if provided
                if 'groups_id' in user_data and isinstance(user_data['groups_id'], list):
                    groups_to_add = []
                    for group_id in user_data['groups_id']:
                        groups_to_add.append((4, int(group_id)))
                    
                    if groups_to_add:
                        new_user.sudo().write({'groups_id': groups_to_add})
                
                results.append({
                    "success": True,
                    "id": new_user.id,
                    "login": new_user.login
                })
            except Exception as e:
                _logger.error("Error creating user %s: %s", user_data.get('login'), str(e))
                results.append({
                    "success": False,
                    "login": user_data['login'],
                    "error": f"Failed to create user: {str(e)}"
                })
        
        # Summarize results
        success_count = sum(1 for r in results if r['success'])
        failure_count = len(results) - success_count
        
        return {
            "success": True,
            "total": len(results),
            "created": success_count,
            "failed": failure_count,
            "results": results
        }
    
    # ========== PUBLIC USER REGISTRATION ==========
    
    @http.route('/api/public/register', type='json', auth='public', methods=['POST'], csrf=False)
    def public_user_registration(self, **kw):
        """
        Public endpoint to register a new user (self-service signup)
        
        Required params:
        - name: User's full name
        - login: User's email (used as login)
        - password: Initial password
        
        Optional params:
        - lang: Language code (e.g., 'en_US')
        - tz: Timezone (e.g., 'Europe/Brussels')
        - phone: Phone number
        - mobile: Mobile number
        - work_email: Work email (defaults to login if not provided)
        - job_title: Job title
        - department_id: Department ID
        - company_id: Company ID
        """
        # Extract params from JSON-RPC body if present
        params = kw.get('params', kw)
        _logger.info("Received request body: %s", params)
        
        # Validate required fields
        required_fields = ['name', 'login', 'password']
        for field in required_fields:
            if field not in params:
                _logger.error("Missing required field: %s", field)
                return {"error": f"Missing required field: {field}"}
        
        try:
            with request.env.cr.savepoint():
                # Create partner first to ensure name is set properly
                partner_values = {
                    'name': params['name'],
                    'phone': params.get('phone', False),
                    'mobile': params.get('mobile', False),
                }
                partner = request.env['res.partner'].sudo().create(partner_values)
                
                # Prepare user values with the partner_id
                user_values = {
                    'partner_id': partner.id,
                    'login': params['login'],
                    'password': params['password'],
                    'active': True,
                }
                
                # Add optional fields if provided
                optional_user_fields = ['lang', 'tz']
                for field in optional_user_fields:
                    if field in params:
                        user_values[field] = params[field]
                
                # Create user linked to the partner
                new_user = request.env['res.users'].sudo().with_context(
                    no_reset_password=True
                ).create(user_values)
                
                # Check for existing employee
                company_id = params.get('company_id', request.env.company.id)
                existing_employee = request.env['hr.employee'].sudo().search([
                    ('user_id', '=', new_user.id),
                    ('company_id', '=', company_id)
                ], limit=1)
                
                employee_id = None
                if existing_employee:
                    # Update existing employee
                    employee_values = {
                        'name': params['name'],
                        'work_email': params.get('work_email', params['login']),
                        'work_phone': params.get('phone', False),
                        'mobile_phone': params.get('mobile', False),
                        'company_id': company_id,
                        'image_1024': False,
                    }
                    if 'job_title' in params:
                        employee_values['job_title'] = params['job_title']
                    if 'department_id' in params and params['department_id']:
                        try:
                            department_id = int(params['department_id'])
                            if request.env['hr.department'].sudo().browse(department_id).exists():
                                employee_values['department_id'] = department_id
                        except (ValueError, TypeError):
                            pass
                    existing_employee.sudo().write(employee_values)
                    employee_id = existing_employee.id
                else:
                    # Create new employee
                    employee_values = {
                        'name': params['name'],
                        'user_id': new_user.id,
                        'work_email': params.get('work_email', params['login']),
                        'work_phone': params.get('phone', False),
                        'mobile_phone': params.get('mobile', False),
                        'company_id': company_id,
                        'image_1024': False,
                    }
                    if 'job_title' in params:
                        employee_values['job_title'] = params['job_title']
                    if 'department_id' in params and params['department_id']:
                        try:
                            department_id = int(params['department_id'])
                            if request.env['hr.department'].sudo().browse(department_id).exists():
                                employee_values['department_id'] = department_id
                        except (ValueError, TypeError):
                            pass
                    employee = request.env['hr.employee'].sudo().with_context(
                        skip_image_computation=True
                    ).create(employee_values)
                    employee_id = employee.id
                
                return {
                    "success": True,
                    "user_id": new_user.id,
                    "employee_id": employee_id,
                    "partner_id": partner.id,
                    "name": params['name'],
                    "login": new_user.login,
                    "message": "Registration successful. Your account is pending approval."
                }
        except Exception as e:
            import traceback
            _logger.error("Error in public user registration: %s\n%s", str(e), traceback.format_exc())
            return {"error": f"Failed to register user: {str(e)}"}
