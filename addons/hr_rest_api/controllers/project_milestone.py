from odoo import http
from odoo.http import request, Response
import json
from .main import HrRestApiController


class ProjectMilestoneRestApiController(HrRestApiController):
    
    # CORS preflight OPTIONS handling
    @http.route([
        '/api/milestones',
        '/api/milestones/<int:milestone_id>',
        '/api/projects/<int:project_id>/milestones',
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_milestones(self, **kw):
        """Handle OPTIONS request for milestone endpoints"""
        return self._handle_options_request()
    
    # Milestone routes
    @http.route('/api/milestones', type='http', auth='public', methods=['GET'], csrf=False)
    def get_milestones(self, **kw):
        """Get all milestones across projects"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'deadline, is_reached desc, name')
            
            # Optional filtering
            domain = []
            
            if 'name' in kw:
                domain.append(('name', 'ilike', kw.get('name')))
            if 'project_id' in kw:
                domain.append(('project_id', '=', int(kw.get('project_id'))))
            if 'is_reached' in kw:
                domain.append(('is_reached', '=', kw.get('is_reached') == 'true'))
            
            # Get milestone data
            milestones = request.env['project.milestone'].sudo().search_read(
                domain=domain,
                fields=[
                    'id', 'name', 'project_id', 'deadline', 'is_reached',
                    'reached_date', 'is_deadline_exceeded', 'is_deadline_future',
                    'task_count', 'done_task_count'
                ],
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(milestones),
                'data': milestones
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/projects/<int:project_id>/milestones', type='http', auth='public', methods=['GET'], csrf=False)
    def get_project_milestones(self, project_id, **kw):
        """Get all milestones for a specific project"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Check if project exists
            project = request.env['project.project'].sudo().browse(project_id)
            if not project.exists():
                result = {
                    'success': False,
                    'error': f'Project not found with ID {project_id}'
                }
                return self._add_cors_headers(Response(json.dumps(result), status=404, content_type='application/json'))
            
            # Get parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'deadline, is_reached desc, name')
            
            # Optional filtering
            domain = [('project_id', '=', project_id)]
            
            if 'name' in kw:
                domain.append(('name', 'ilike', kw.get('name')))
            if 'is_reached' in kw:
                domain.append(('is_reached', '=', kw.get('is_reached') == 'true'))
            
            # Get milestone data
            milestones = request.env['project.milestone'].sudo().search_read(
                domain=domain,
                fields=[
                    'id', 'name', 'project_id', 'deadline', 'is_reached',
                    'reached_date', 'is_deadline_exceeded', 'is_deadline_future',
                    'task_count', 'done_task_count'
                ],
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(milestones),
                'data': milestones
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/milestones/<int:milestone_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_milestone(self, milestone_id, **kw):
        """Get details of a specific milestone"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get milestone
            milestone = request.env['project.milestone'].sudo().browse(milestone_id)
            if not milestone.exists():
                result = {
                    'success': False,
                    'error': f'Milestone not found with ID {milestone_id}'
                }
                return self._add_cors_headers(Response(json.dumps(result), status=404, content_type='application/json'))
            
            # Get detailed milestone data
            milestone_data = milestone.read([
                'id', 'name', 'project_id', 'deadline', 'is_reached',
                'reached_date', 'is_deadline_exceeded', 'is_deadline_future',
                'task_count', 'done_task_count', 'can_be_marked_as_done'
            ])[0]
            
            # Get related tasks
            tasks = request.env['project.task'].sudo().search_read(
                [('milestone_id', '=', milestone_id)],
                ['id', 'name', 'state', 'is_closed', 'stage_id', 'user_ids', 'date_deadline']
            )
            
            milestone_data['tasks'] = tasks
            
            result = {
                'success': True,
                'data': milestone_data
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/milestones', type='json', auth='public', methods=['POST'], csrf=False)
    def create_milestone(self, **kw):
        """Create a new milestone"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Required fields
            required_fields = ['name', 'project_id']
            for field in required_fields:
                if field not in kw:
                    return {
                        'success': False,
                        'error': f'Missing required field: {field}'
                    }
            
            # Create milestone
            milestone_vals = {
                'name': kw.get('name'),
                'project_id': kw.get('project_id'),
                'deadline': kw.get('deadline', False),
                'is_reached': kw.get('is_reached', False),
            }
            
            # Create the milestone
            milestone = request.env['project.milestone'].sudo().create(milestone_vals)
            
            return {
                'success': True,
                'id': milestone.id,
                'message': 'Milestone created successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/milestones/<int:milestone_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_milestone(self, milestone_id, **kw):
        """Update an existing milestone"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Get milestone
            milestone = request.env['project.milestone'].sudo().browse(milestone_id)
            if not milestone.exists():
                return {
                    'success': False,
                    'error': f'Milestone not found with ID {milestone_id}'
                }
            
            # Update milestone
            update_vals = {}
            allowed_fields = ['name', 'project_id', 'deadline', 'is_reached']
            
            for field in allowed_fields:
                if field in kw:
                    update_vals[field] = kw[field]
            
            milestone.write(update_vals)
            
            return {
                'success': True,
                'id': milestone.id,
                'message': 'Milestone updated successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/milestones/<int:milestone_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_milestone(self, milestone_id, **kw):
        """Delete a milestone"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get milestone
            milestone = request.env['project.milestone'].sudo().browse(milestone_id)
            if not milestone.exists():
                result = {
                    'success': False,
                    'error': f'Milestone not found with ID {milestone_id}'
                }
                return self._add_cors_headers(Response(json.dumps(result), status=404, content_type='application/json'))
            
            # Delete milestone
            milestone.unlink()
            
            result = {
                'success': True,
                'message': 'Milestone deleted successfully'
            }
            return self._add_cors_headers(Response(json.dumps(result), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/milestones/<int:milestone_id>/toggle_reached', type='json', auth='public', methods=['POST'], csrf=False)
    def toggle_milestone_reached(self, milestone_id, **kw):
        """Toggle milestone reached status"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Get milestone
            milestone = request.env['project.milestone'].sudo().browse(milestone_id)
            if not milestone.exists():
                return {
                    'success': False,
                    'error': f'Milestone not found with ID {milestone_id}'
                }
            
            # Toggle is_reached state
            is_reached = not milestone.is_reached
            data = milestone.toggle_is_reached(is_reached)
            
            return {
                'success': True,
                'id': milestone.id,
                'is_reached': is_reached,
                'data': data,
                'message': f'Milestone {"marked as reached" if is_reached else "marked as not reached"} successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            } 