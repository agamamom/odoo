from odoo import http
from odoo.http import request, Response
import json
from .main import HrRestApiController


class ProjectConfigRestApiController(HrRestApiController):
    
    # CORS preflight OPTIONS handling
    @http.route([
        '/api/project_tags',
        '/api/project_tags/<int:tag_id>',
        '/api/project_stages',
        '/api/project_stages/<int:stage_id>',
        '/api/task_types',
        '/api/task_types/<int:type_id>',
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_project_config(self, **kw):
        """Handle OPTIONS request for project configuration endpoints"""
        return self._handle_options_request()
    
    # Project Tags routes
    @http.route('/api/project_tags', type='http', auth='public', methods=['GET'], csrf=False)
    def get_project_tags(self, **kw):
        """Get all project tags"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'name')
            
            # Optional filtering
            domain = []
            if 'name' in kw:
                domain.append(('name', 'ilike', kw.get('name')))
            
            # Get tag data
            tags = request.env['project.tags'].sudo().search_read(
                domain=domain,
                fields=['id', 'name', 'color'],
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(tags),
                'data': tags
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/project_tags/<int:tag_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_project_tag(self, tag_id, **kw):
        """Get a specific project tag"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get tag
            tag = request.env['project.tags'].sudo().browse(tag_id)
            if not tag.exists():
                result = {
                    'success': False,
                    'error': f'Project tag not found with ID {tag_id}'
                }
                return self._add_cors_headers(Response(json.dumps(result), status=404, content_type='application/json'))
            
            # Get detailed tag data
            tag_data = tag.read(['id', 'name', 'color'])[0]
            
            result = {
                'success': True,
                'data': tag_data
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/project_tags', type='json', auth='public', methods=['POST'], csrf=False)
    def create_project_tag(self, **kw):
        """Create a new project tag"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Required fields
            required_fields = ['name']
            for field in required_fields:
                if field not in kw:
                    return {
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }
            
            # Create tag
            tag_vals = {
                'name': kw.get('name'),
                'color': kw.get('color', 0),
            }
            
            # Create the tag
            tag = request.env['project.tags'].sudo().create(tag_vals)
            
            return {
                'success': True,
                'id': tag.id,
                'message': 'Project tag created successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/project_tags/<int:tag_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_project_tag(self, tag_id, **kw):
        """Update an existing project tag"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Get tag
            tag = request.env['project.tags'].sudo().browse(tag_id)
            if not tag.exists():
                return {
                    'success': False,
                    'error': f'Project tag not found with ID {tag_id}'
                }
            
            # Update tag
            update_vals = {}
            allowed_fields = ['name', 'color']
            
            for field in allowed_fields:
                if field in kw:
                    update_vals[field] = kw[field]
            
            tag.write(update_vals)
            
            return {
                'success': True,
                'id': tag.id,
                'message': 'Project tag updated successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/project_tags/<int:tag_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_project_tag(self, tag_id, **kw):
        """Delete a project tag"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get tag
            tag = request.env['project.tags'].sudo().browse(tag_id)
            if not tag.exists():
                result = {
                    'success': False,
                    'error': f'Project tag not found with ID {tag_id}'
                }
                return self._add_cors_headers(Response(json.dumps(result), status=404, content_type='application/json'))
            
            # Delete tag
            tag.unlink()
            
            result = {
                'success': True,
                'message': 'Project tag deleted successfully'
            }
            return self._add_cors_headers(Response(json.dumps(result), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    # Project Stages routes
    @http.route('/api/project_stages', type='http', auth='public', methods=['GET'], csrf=False)
    def get_project_stages(self, **kw):
        """Get all project stages"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'sequence, name')
            
            # Optional filtering
            domain = []
            if 'name' in kw:
                domain.append(('name', 'ilike', kw.get('name')))
            
            # Get stage data
            stages = request.env['project.project.stage'].sudo().search_read(
                domain=domain,
                fields=['id', 'name', 'sequence', 'mail_template_id', 'company_id'],
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(stages),
                'data': stages
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    # Task Types (stages) routes
    @http.route('/api/task_types', type='http', auth='public', methods=['GET'], csrf=False)
    def get_task_types(self, **kw):
        """Get all task types (stages)"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'sequence, id')
            
            # Optional filtering
            domain = []
            if 'name' in kw:
                domain.append(('name', 'ilike', kw.get('name')))
            if 'project_id' in kw:
                domain.append(('project_ids', 'in', [int(kw.get('project_id'))]))
            if 'fold' in kw:
                domain.append(('fold', '=', kw.get('fold') == 'true'))
            
            # Get task type data
            task_types = request.env['project.task.type'].sudo().search_read(
                domain=domain,
                fields=[
                    'id', 'name', 'description', 'sequence', 'fold',
                    'mail_template_id', 'project_ids', 'legend_blocked',
                    'legend_done', 'legend_normal', 'auto_validation_kanban_state',
                    'rating_template_id', 'user_id', 'company_id'
                ],
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(task_types),
                'data': task_types
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/task_types/<int:type_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_task_type(self, type_id, **kw):
        """Get a specific task type (stage)"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get task type
            task_type = request.env['project.task.type'].sudo().browse(type_id)
            if not task_type.exists():
                result = {
                    'success': False,
                    'error': f'Task type not found with ID {type_id}'
                }
                return self._add_cors_headers(Response(json.dumps(result), status=404, content_type='application/json'))
            
            # Get detailed task type data
            task_type_data = task_type.read([
                'id', 'name', 'description', 'sequence', 'fold',
                'mail_template_id', 'project_ids', 'legend_blocked',
                'legend_done', 'legend_normal', 'auto_validation_kanban_state',
                'rating_template_id', 'user_id', 'company_id'
            ])[0]
            
            result = {
                'success': True,
                'data': task_type_data
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json')) 