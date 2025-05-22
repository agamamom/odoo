from odoo import http
from odoo.http import request
from odoo.addons.hr_rest_api.controllers.main import HrRestApiController
import json
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

# Check if required modules are installed
PAYROLL_INSTALLED = False
PAYROLL_ACCOUNTING_INSTALLED = False

try:
    from dateutil import relativedelta
    from odoo.addons.hr_payroll_community.models.hr_payslip import HrPayslip
    PAYROLL_INSTALLED = True
    try:
        from odoo.addons.hr_payroll_account_community.models.hr_payslip import HrPayslip as HrPayslipAccounting
        PAYROLL_ACCOUNTING_INSTALLED = True
    except ImportError:
        _logger.info("hr_payroll_account_community module not installed, accounting features will be disabled")
except ImportError:
    _logger.info("hr_payroll_community module not installed, payroll features will be disabled")

class HrPayrollAdminRestApiController(HrRestApiController):
    # --- Helper for generic CRUD ---
    def _generic_crud_routes(self, model, route_base, fields=None):
        fields = fields or ['id', 'name']
        # List
        @http.route(f'/api/hr/{route_base}', type='http', auth='public', methods=['GET'], csrf=False)
        def list_records(self, **kw):
            # Check if the model exists in the registry
            if model not in request.env:
                result = {'success': False, 'error': f'Model {model} is not installed'}
                response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
                return self._add_cors_headers(response)
                
            domain = []
            limit = int(kw.get('limit', 100))
            offset = int(kw.get('offset', 0))
            order = kw.get('order', 'id desc')
            result = self._handle_request(model, fields, domain, limit, offset, order)
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        # Get
        @http.route(f'/api/hr/{route_base}/<int:rec_id>', type='http', auth='public', methods=['GET'], csrf=False)
        def get_record(self, rec_id, **kw):
            # Check if the model exists in the registry
            if model not in request.env:
                result = {'success': False, 'error': f'Model {model} is not installed'}
                response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
                return self._add_cors_headers(response)
                
            result = self._handle_request(model, ['*'], [('id', '=', rec_id)], 1)
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        # Create
        @http.route(f'/api/hr/{route_base}', type='json', auth='public', methods=['POST'], csrf=False)
        def create_record(self, **kw):
            # Check if the model exists in the registry
            if model not in request.env:
                result = {'success': False, 'error': f'Model {model} is not installed'}
                response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
                return self._add_cors_headers(response)
                
            data = kw.get('data') or kw
            result = self._handle_create(model, data)
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        # Update
        @http.route(f'/api/hr/{route_base}/<int:rec_id>', type='json', auth='public', methods=['PUT'], csrf=False)
        def update_record(self, rec_id, **kw):
            # Check if the model exists in the registry
            if model not in request.env:
                result = {'success': False, 'error': f'Model {model} is not installed'}
                response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
                return self._add_cors_headers(response)
                
            data = kw.get('data') or kw
            result = self._handle_update(model, rec_id, data)
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        # Delete
        @http.route(f'/api/hr/{route_base}/<int:rec_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
        def delete_record(self, rec_id, **kw):
            # Check if the model exists in the registry
            if model not in request.env:
                result = {'success': False, 'error': f'Model {model} is not installed'}
                response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
                return self._add_cors_headers(response)
                
            result = self._handle_delete(model, rec_id)
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        # CORS
        @http.route([
            f'/api/hr/{route_base}',
            f'/api/hr/{route_base}/<int:rec_id>'
        ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
        def options_records(self, **kw):
            return self._handle_options_request()
        # Attach to class
        setattr(self.__class__, f'list_{route_base}', list_records)
        setattr(self.__class__, f'get_{route_base}', get_record)
        setattr(self.__class__, f'create_{route_base}', create_record)
        setattr(self.__class__, f'update_{route_base}', update_record)
        setattr(self.__class__, f'delete_{route_base}', delete_record)
        setattr(self.__class__, f'options_{route_base}', options_records)

    def __init__(self):
        # Register CRUD for each model
        super().__init__()
        
        if PAYROLL_INSTALLED:
            # Core payroll models
            self._generic_crud_routes('hr.payslip.run', 'payslip_runs', ['id','name','state','date_start','date_end','credit_note'])
            self._generic_crud_routes('hr.salary.rule', 'salary_rules', ['id','name','code','sequence','category_id','active','amount_select','amount_fix','amount_percentage','amount_python_compute','parent_rule_id','company_id'])
            self._generic_crud_routes('hr.salary.rule.category', 'salary_rule_categories', ['id','name','code','parent_id','company_id'])
            self._generic_crud_routes('hr.payroll.structure', 'payroll_structures', ['id','name','code','company_id','parent_id','note'])
            self._generic_crud_routes('hr.payslip.line', 'payslip_lines', ['id','slip_id','salary_rule_id','employee_id','contract_id','rate','amount','quantity','total'])
            self._generic_crud_routes('hr.payslip.input', 'payslip_inputs', ['id','name','payslip_id','sequence','code','date_from','date_to','amount','contract_id'])
            self._generic_crud_routes('hr.payslip.worked.days', 'payslip_worked_days', ['id','name','payslip_id','sequence','code','number_of_days','number_of_hours','contract_id'])
            self._generic_crud_routes('hr.contribution.register', 'contribution_registers', ['id','name','company_id','partner_id','note'])
            self._generic_crud_routes('hr.rule.input', 'rule_inputs', ['id','name','code','input_id'])
            self._generic_crud_routes('hr.contract.advantage.template', 'contract_advantage_templates', ['id','name','code','lower_bound','upper_bound','default_value'])
            
        if PAYROLL_ACCOUNTING_INSTALLED:
            # Additional accounting related endpoints
            self._generic_crud_routes('account.journal', 'payroll_journals', ['id','name','type','company_id','default_account_id'])
            self._generic_crud_routes('account.account', 'accounts', ['id','name','code','account_type','company_id'])
            self._generic_crud_routes('account.analytic.account', 'analytic_accounts', ['id','name','code','company_id'])

    # --- Common error handler for missing modules ---
    def _missing_module_response(self, module_name):
        result = {
            'success': False,
            'error': f'This feature requires the {module_name} module which is not installed'
        }
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    # --- Payslip Batch Actions ---
    @http.route('/api/hr/payslip_runs/<int:rec_id>/close', type='http', auth='public', methods=['POST'], csrf=False)
    def close_payslip_run(self, rec_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response('hr_payroll_community')
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        batch = request.env['hr.payslip.run'].sudo().browse(rec_id)
        if not batch.exists():
            result = {'success': False, 'error': 'Payslip batch not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        batch.close_payslip_run()
        result = {'success': True, 'message': 'Payslip batch closed'}
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    @http.route('/api/hr/payslip_runs/<int:rec_id>/set_draft', type='http', auth='public', methods=['POST'], csrf=False)
    def set_draft_payslip_run(self, rec_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response('hr_payroll_community')
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        batch = request.env['hr.payslip.run'].sudo().browse(rec_id)
        if not batch.exists():
            result = {'success': False, 'error': 'Payslip batch not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        batch.action_payslip_run()
        result = {'success': True, 'message': 'Payslip batch set to draft'}
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    # --- Batch Payslip Generation Wizard ---
    @http.route('/api/hr/payslip_runs/<int:run_id>/generate_payslips', type='http', auth='public', methods=['POST'], csrf=False)
    def generate_batch_payslips(self, run_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response('hr_payroll_community')
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = {}
        
        # Get employee IDs from request data
        employee_ids = data.get('employee_ids', [])
        if not employee_ids:
            result = {'success': False, 'error': 'No employees specified'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get the payslip run
        payslip_run = request.env['hr.payslip.run'].sudo().browse(run_id)
        if not payslip_run.exists():
            result = {'success': False, 'error': 'Payslip run not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Create context for wizard
        context = {
            'active_id': run_id,
            'active_model': 'hr.payslip.run'
        }
        
        # Create the wizard and execute it
        wizard = request.env['hr.payslip.employees'].sudo().with_context(context).create({
            'employee_ids': [(6, 0, employee_ids)]
        })
        
        try:
            wizard.action_compute_sheet()
            # Get the created payslips
            payslips = request.env['hr.payslip'].sudo().search([
                ('payslip_run_id', '=', run_id),
                ('employee_id', 'in', employee_ids)
            ])
            result = {
                'success': True,
                'message': f'{len(payslips)} payslips generated',
                'payslips': [{'id': p.id, 'name': p.name, 'employee_id': p.employee_id.id} for p in payslips]
            }
        except Exception as e:
            result = {'success': False, 'error': str(e)}
        
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    # --- Contribution Register Report Wizard ---
    @http.route('/api/hr/contribution_registers/report', type='http', auth='public', methods=['POST'], csrf=False)
    def contribution_register_report(self, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response('hr_payroll_community')
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        try:
            data = json.loads(request.httprequest.data.decode('utf-8'))
        except Exception:
            data = {}
        
        # Get the register IDs from request data
        register_ids = data.get('register_ids', [])
        if not register_ids:
            result = {'success': False, 'error': 'No contribution registers specified'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        # Get date range or use defaults
        if 'relativedelta' not in globals():
            # Import failed, let's use a simple alternative
            today = datetime.now()
            date_from = data.get('date_from', f"{today.year}-{today.month:02d}-01")
            next_month = today.month + 1 if today.month < 12 else 1
            next_year = today.year + 1 if today.month == 12 else today.year
            last_day = 30  # Simplified approach
            date_to = data.get('date_to', f"{next_year}-{next_month:02d}-{last_day:02d}")
        else:
            date_from = data.get('date_from', datetime.now().strftime('%Y-%m-01'))
            date_to = data.get('date_to', (datetime.now() + relativedelta.relativedelta(months=+1, day=1, days=-1)).strftime('%Y-%m-%d'))
        
        # Create context for wizard
        context = {
            'active_ids': register_ids,
            'active_model': 'hr.contribution.register'
        }
        
        # Create the wizard
        wizard = request.env['payslip.lines.contribution.register'].sudo().with_context(context).create({
            'date_from': date_from,
            'date_to': date_to
        })
        
        # Generate report data (not the actual PDF)
        registers = request.env['hr.contribution.register'].sudo().browse(register_ids)
        payslip_lines = request.env['hr.payslip.line'].sudo().search([
            ('register_id', 'in', register_ids),
            ('slip_id.state', 'in', ['done', 'paid']),
            ('slip_id.date_from', '>=', date_from),
            ('slip_id.date_to', '<=', date_to)
        ])
        
        # Group data by register
        register_data = {}
        for register in registers:
            lines = payslip_lines.filtered(lambda l: l.register_id.id == register.id)
            register_data[register.id] = {
                'id': register.id,
                'name': register.name,
                'total': sum(lines.mapped('total')),
                'line_count': len(lines),
            }
        
        result = {
            'success': True,
            'date_from': date_from,
            'date_to': date_to,
            'registers': list(register_data.values())
        }
        
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    # --- Payslip Accounting Entries ---
    @http.route('/api/hr/payslips/<int:payslip_id>/accounting_entries', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_accounting_entries(self, payslip_id, **kw):
        if not PAYROLL_ACCOUNTING_INSTALLED:
            return self._missing_module_response('hr_payroll_account_community')
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
        
        if not hasattr(payslip, 'move_id'):
            result = {'success': False, 'error': 'Accounting not enabled for payslips'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        if not payslip.move_id:
            result = {
                'success': True,
                'has_entries': False,
                'message': 'No accounting entries found for this payslip'
            }
        else:
            move = payslip.move_id
            result = {
                'success': True,
                'has_entries': True,
                'move_id': move.id,
                'name': move.name,
                'date': move.date.strftime('%Y-%m-%d') if move.date else False,
                'journal_id': {
                    'id': move.journal_id.id,
                    'name': move.journal_id.name
                },
                'state': move.state,
                'lines': [{
                    'id': line.id,
                    'name': line.name,
                    'account_id': {
                        'id': line.account_id.id,
                        'name': line.account_id.name,
                        'code': line.account_id.code
                    },
                    'debit': line.debit,
                    'credit': line.credit,
                    'partner_id': line.partner_id.id if line.partner_id else False,
                } for line in move.line_ids]
            }
        
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
    
    # Add options handlers for new endpoints
    @http.route([
        '/api/hr/payslip_runs/<int:run_id>/generate_payslips',
        '/api/hr/contribution_registers/report',
        '/api/hr/payslips/<int:payslip_id>/accounting_entries',
        '/api/hr/payslip_runs/<int:rec_id>/close',
        '/api/hr/payslip_runs/<int:rec_id>/set_draft'
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_payroll_accounting_endpoints(self, **kw):
        """Handle OPTIONS request for payroll accounting endpoints"""
        return self._handle_options_request() 