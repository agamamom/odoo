from odoo import http
from odoo.http import request, Response
import json
from .main import HrRestApiController


class ProjectRestApiController(HrRestApiController):
    
    # CORS preflight OPTIONS handling
    @http.route([
        '/api/projects',
        '/api/projects/<int:project_id>',
        '/api/projects/<int:project_id>/tasks',
        '/api/tasks',
        '/api/tasks/<int:task_id>',
        '/api/milestones',
        '/api/milestones/<int:milestone_id>',
        '/api/project_tags',
        '/api/project_stages',
        '/api/task_types',
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_projects(self, **kw):
        """Handle OPTIONS request for project endpoints"""
        return self._handle_options_request()
    
    # Project routes
    @http.route('/api/projects', type='http', auth='public', methods=['GET'], csrf=False)
    def get_projects(self, **kw):
        """Get all projects"""
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
            if 'active' in kw:
                domain.append(('active', '=', kw.get('active') == 'true'))
            
            # Get project data
            projects = request.env['project.project'].sudo().search_read(
                domain=domain,
                fields=[
                    'id', 'name', 'description', 'active', 'sequence',
                    'partner_id', 'company_id', 'user_id', 'date_start', 'date',
                    'tag_ids', 'task_count', 'task_ids', 'color', 'privacy_visibility',
                    'last_update_status', 'stage_id', 'is_favorite', 'milestone_count',
                ],
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(projects),
                'data': projects
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/projects/<int:project_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_project(self, project_id, **kw):
        """Get a specific project by ID"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get project
            project = request.env['project.project'].sudo().browse(project_id)
            if not project.exists():
                result = {
                    'success': False,
                    'error': f'Project not found with ID {project_id}'
                }
                return self._add_cors_headers(Response(json.dumps(result), status=404, content_type='application/json'))
            
            # Get detailed project data
            project_data = project.read([
                'id', 'name', 'description', 'active', 'sequence',
                'partner_id', 'company_id', 'user_id', 'date_start', 'date',
                'tag_ids', 'task_count', 'task_ids', 'color', 'privacy_visibility',
                'last_update_status', 'stage_id', 'is_favorite', 'milestone_count',
                'open_task_count', 'closed_task_count', 'task_completion_percentage'
            ])[0]
            
            result = {
                'success': True,
                'data': project_data
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/projects', type='json', auth='public', methods=['POST'], csrf=False)
    def create_project(self, **kw):
        """Create a new project"""
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
            
            # Create project
            project_vals = {
                'name': kw.get('name'),
                'description': kw.get('description', False),
                'active': kw.get('active', True),
                'user_id': kw.get('user_id', False),
                'partner_id': kw.get('partner_id', False),
                'date_start': kw.get('date_start', False),
                'date': kw.get('date', False),
                'privacy_visibility': kw.get('privacy_visibility', 'portal'),
                'company_id': kw.get('company_id', False),
            }
            
            # Create the project
            project = request.env['project.project'].sudo().create(project_vals)
            
            # Add tags if provided
            if 'tag_ids' in kw and kw['tag_ids']:
                project.write({'tag_ids': [(6, 0, kw['tag_ids'])]})
            
            return {
                'success': True,
                'id': project.id,
                'message': 'Project created successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/projects/<int:project_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_project(self, project_id, **kw):
        """Update an existing project"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Get project
            project = request.env['project.project'].sudo().browse(project_id)
            if not project.exists():
                return {
                    'success': False,
                    'error': f'Project not found with ID {project_id}'
                }
            
            # Update project
            update_vals = {}
            allowed_fields = [
                'name', 'description', 'active', 'user_id', 'partner_id',
                'date_start', 'date', 'privacy_visibility', 'company_id'
            ]
            
            for field in allowed_fields:
                if field in kw:
                    update_vals[field] = kw[field]
            
            # Handle tags separately
            if 'tag_ids' in kw:
                update_vals['tag_ids'] = [(6, 0, kw['tag_ids'])]
            
            project.write(update_vals)
            
            return {
                'success': True,
                'id': project.id,
                'message': 'Project updated successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/projects/<int:project_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_project(self, project_id, **kw):
        """Delete a project"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get project
            project = request.env['project.project'].sudo().browse(project_id)
            if not project.exists():
                result = {
                    'success': False,
                    'error': f'Project not found with ID {project_id}'
                }
                return self._add_cors_headers(Response(json.dumps(result), status=404, content_type='application/json'))
            
            # Delete project
            project.unlink()
            
            result = {
                'success': True,
                'message': 'Project deleted successfully'
            }
            return self._add_cors_headers(Response(json.dumps(result), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    # Task routes
    @http.route('/api/projects/<int:project_id>/tasks', type='http', auth='public', methods=['GET'], csrf=False)
    def get_project_tasks(self, project_id, **kw):
        """Get all tasks for a specific project"""
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
            order = kw.get('order', 'priority desc, sequence, date_deadline asc, id desc')
            
            # Optional filtering
            domain = [('project_id', '=', project_id)]
            
            if 'name' in kw:
                domain.append(('name', 'ilike', kw.get('name')))
            if 'stage_id' in kw:
                domain.append(('stage_id', '=', int(kw.get('stage_id'))))
            if 'user_ids' in kw:
                user_ids = [int(user_id) for user_id in kw.get('user_ids').split(',')]
                domain.append(('user_ids', 'in', user_ids))
            if 'is_closed' in kw:
                domain.append(('is_closed', '=', kw.get('is_closed') == 'true'))
            if 'state' in kw:
                domain.append(('state', '=', kw.get('state')))
            if 'milestone_id' in kw:
                domain.append(('milestone_id', '=', int(kw.get('milestone_id'))))
            
            # Get task data
            tasks = request.env['project.task'].sudo().search_read(
                domain=domain,
                fields=[
                    'id', 'name', 'description', 'state', 'is_closed',
                    'stage_id', 'user_ids', 'partner_id', 'date_deadline',
                    'tag_ids', 'priority', 'sequence', 'color',
                    'parent_id', 'child_ids', 'milestone_id',
                    'date_assign', 'date_end', 'company_id'
                ],
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(tasks),
                'data': tasks
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/tasks', type='http', auth='public', methods=['GET'], csrf=False)
    def get_tasks(self, **kw):
        """Get all tasks across projects"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get parameters
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'priority desc, sequence, date_deadline asc, id desc')
            
            # Optional filtering
            domain = []
            
            if 'name' in kw:
                domain.append(('name', 'ilike', kw.get('name')))
            if 'project_id' in kw:
                domain.append(('project_id', '=', int(kw.get('project_id'))))
            if 'stage_id' in kw:
                domain.append(('stage_id', '=', int(kw.get('stage_id'))))
            if 'user_ids' in kw:
                user_ids = [int(user_id) for user_id in kw.get('user_ids').split(',')]
                domain.append(('user_ids', 'in', user_ids))
            if 'is_closed' in kw:
                domain.append(('is_closed', '=', kw.get('is_closed') == 'true'))
            if 'state' in kw:
                domain.append(('state', '=', kw.get('state')))
            if 'milestone_id' in kw:
                domain.append(('milestone_id', '=', int(kw.get('milestone_id'))))
            
            # Get task data
            tasks = request.env['project.task'].sudo().search_read(
                domain=domain,
                fields=[
                    'id', 'name', 'description', 'state', 'is_closed',
                    'stage_id', 'user_ids', 'partner_id', 'date_deadline',
                    'tag_ids', 'priority', 'sequence', 'color',
                    'parent_id', 'child_ids', 'milestone_id', 'project_id',
                    'date_assign', 'date_end', 'company_id'
                ],
                limit=limit,
                offset=offset,
                order=order
            )
            
            result = {
                'success': True,
                'count': len(tasks),
                'data': tasks
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/tasks/<int:task_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_task(self, task_id, **kw):
        """Get details of a specific task"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get task
            task = request.env['project.task'].sudo().browse(task_id)
            if not task.exists():
                result = {
                    'success': False,
                    'error': f'Task not found with ID {task_id}'
                }
                return self._add_cors_headers(Response(json.dumps(result), status=404, content_type='application/json'))
            
            # Get detailed task data
            task_data = task.read([
                'id', 'name', 'description', 'state', 'is_closed',
                'stage_id', 'user_ids', 'partner_id', 'date_deadline',
                'tag_ids', 'priority', 'sequence', 'color',
                'parent_id', 'child_ids', 'milestone_id', 'project_id',
                'date_assign', 'date_end', 'company_id', 'display_in_project',
                'subtask_count', 'closed_subtask_count', 'subtask_completion_percentage',
                'depend_on_ids', 'dependent_ids', 'depend_on_count', 'dependent_tasks_count',
                'recurring_task'
            ])[0]
            
            result = {
                'success': True,
                'data': task_data
            }
            return self._add_cors_headers(Response(json.dumps(result, default=self._json_serializable), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json'))
    
    @http.route('/api/tasks', type='json', auth='public', methods=['POST'], csrf=False)
    def create_task(self, **kw):
        """Create a new task"""
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
            
            # Create task
            task_vals = {
                'name': kw.get('name'),
                'description': kw.get('description', False),
                'project_id': kw.get('project_id'),
                'user_ids': [(6, 0, kw.get('user_ids', []))],
                'partner_id': kw.get('partner_id', False),
                'date_deadline': kw.get('date_deadline', False),
                'priority': kw.get('priority', '0'),
                'parent_id': kw.get('parent_id', False),
                'milestone_id': kw.get('milestone_id', False),
                'stage_id': kw.get('stage_id', False),
                'state': kw.get('state', '01_in_progress'),
                'company_id': kw.get('company_id', False),
                'display_in_project': kw.get('display_in_project', True),
            }
            
            # Create the task
            task = request.env['project.task'].sudo().create(task_vals)
            
            # Add tags if provided
            if 'tag_ids' in kw and kw['tag_ids']:
                task.write({'tag_ids': [(6, 0, kw['tag_ids'])]})
            
            # Add dependencies if provided
            if 'depend_on_ids' in kw and kw['depend_on_ids']:
                task.write({'depend_on_ids': [(6, 0, kw['depend_on_ids'])]})
            
            return {
                'success': True,
                'id': task.id,
                'message': 'Task created successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/tasks/<int:task_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_task(self, task_id, **kw):
        """Update an existing task"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return result
            
            # Get task
            task = request.env['project.task'].sudo().browse(task_id)
            if not task.exists():
                return {
                    'success': False,
                    'error': f'Task not found with ID {task_id}'
                }
            
            # Update task
            update_vals = {}
            allowed_fields = [
                'name', 'description', 'project_id', 'partner_id',
                'date_deadline', 'priority', 'parent_id', 'milestone_id',
                'stage_id', 'state', 'company_id', 'display_in_project'
            ]
            
            for field in allowed_fields:
                if field in kw:
                    update_vals[field] = kw[field]
            
            # Handle many2many fields separately
            if 'user_ids' in kw:
                update_vals['user_ids'] = [(6, 0, kw['user_ids'])]
            
            if 'tag_ids' in kw:
                update_vals['tag_ids'] = [(6, 0, kw['tag_ids'])]
            
            if 'depend_on_ids' in kw:
                update_vals['depend_on_ids'] = [(6, 0, kw['depend_on_ids'])]
            
            task.write(update_vals)
            
            return {
                'success': True,
                'id': task.id,
                'message': 'Task updated successfully'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    @http.route('/api/tasks/<int:task_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_task(self, task_id, **kw):
        """Delete a task"""
        try:
            # Validate API key
            is_valid, result = self._validate_api_key()
            if not is_valid:
                return self._add_cors_headers(Response(json.dumps(result), status=401, content_type='application/json'))
            
            # Get task
            task = request.env['project.task'].sudo().browse(task_id)
            if not task.exists():
                result = {
                    'success': False,
                    'error': f'Task not found with ID {task_id}'
                }
                return self._add_cors_headers(Response(json.dumps(result), status=404, content_type='application/json'))
            
            # Delete task
            task.unlink()
            
            result = {
                'success': True,
                'message': 'Task deleted successfully'
            }
            return self._add_cors_headers(Response(json.dumps(result), status=200, content_type='application/json'))
            
        except Exception as e:
            result = {
                'success': False,
                'error': str(e)
            }
            return self._add_cors_headers(Response(json.dumps(result), status=500, content_type='application/json')) 