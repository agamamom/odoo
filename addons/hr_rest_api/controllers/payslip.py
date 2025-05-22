from odoo import http
from odoo.http import request, Response
from odoo.addons.hr_rest_api.controllers.main import HrRestApiController
from odoo.tools.safe_eval import safe_eval
import json
import logging

_logger = logging.getLogger(__name__)

# Check if required modules are installed
PAYROLL_INSTALLED = False
try:
    from odoo.addons.hr_payroll_community.models.hr_payslip import HrPayslip
    PAYROLL_INSTALLED = True
except ImportError:
    _logger.info("hr_payroll_community module not installed, payslip features will be disabled")

class HrPayslipRestApiController(HrRestApiController):
    # --- CORS preflight ---
    @http.route([
        '/api/hr/payslips',
        '/api/hr/payslips/<int:payslip_id>',
        '/api/hr/payslips/batch',
        '/api/hr/payslips/<int:payslip_id>/compute',
        '/api/hr/payslips/<int:payslip_id>/set_draft',
        '/api/hr/payslips/<int:payslip_id>/confirm',
        '/api/hr/payslips/<int:payslip_id>/cancel',
        '/api/hr/payslips/<int:payslip_id>/refund',
        '/api/hr/payslips/<int:payslip_id>/lines',
        '/api/hr/payslips/<int:payslip_id>/worked_days',
        '/api/hr/payslips/<int:payslip_id>/inputs',
        '/api/hr/payslips/<int:payslip_id>/pdf',
        '/api/hr/payslips/<int:payslip_id>/report',
        '/api/hr/payslips/report/<int:report_id>'
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_payslip_endpoints(self, **kw):
        """Handle OPTIONS request for payslip endpoints"""
        return self._handle_options_request()
        
    # --- Common error handler for missing modules ---
    def _missing_module_response(self, module_name='hr_payroll_community'):
        result = {
            'success': False,
            'error': f'This feature requires the {module_name} module which is not installed'
        }
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)

    # --- Payslip CRUD Operations ---
    @http.route('/api/hr/payslips', type='http', auth='public', methods=['GET'], csrf=False)
    def list_payslips(self, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        domain = []
        # Apply filters if provided
        employee_id = kw.get('employee_id')
        if employee_id:
            domain.append(('employee_id', '=', int(employee_id)))
            
        date_from = kw.get('date_from')
        if date_from:
            domain.append(('date_from', '>=', date_from))
            
        date_to = kw.get('date_to')
        if date_to:
            domain.append(('date_to', '<=', date_to))
            
        state = kw.get('state')
        if state:
            domain.append(('state', '=', state))
            
        # Pagination
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        
        # Get and return payslips
        payslips = request.env['hr.payslip'].sudo().search(domain, limit=limit, offset=offset)
        result = {
            'count': len(payslips),
            'total': request.env['hr.payslip'].sudo().search_count(domain),
            'payslips': [{
                'id': payslip.id,
                'name': payslip.name,
                'employee_id': payslip.employee_id.id,
                'employee_name': payslip.employee_id.name,
                'date_from': payslip.date_from.strftime('%Y-%m-%d') if payslip.date_from else False,
                'date_to': payslip.date_to.strftime('%Y-%m-%d') if payslip.date_to else False,
                'state': payslip.state,
                'number': payslip.number,
                'company_id': payslip.company_id.id
            } for payslip in payslips]
        }
        
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    @http.route('/api/hr/payslips/<int:payslip_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip(self, payslip_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        result = {
            'success': True,
            'payslip': {
                'id': payslip.id,
                'name': payslip.name,
                'employee_id': payslip.employee_id.id,
                'employee_name': payslip.employee_id.name,
                'date_from': payslip.date_from.strftime('%Y-%m-%d') if payslip.date_from else False,
                'date_to': payslip.date_to.strftime('%Y-%m-%d') if payslip.date_to else False,
                'state': payslip.state,
                'number': payslip.number,
                'company_id': payslip.company_id.id,
                'contract_id': payslip.contract_id.id if payslip.contract_id else False,
                'struct_id': payslip.struct_id.id if payslip.struct_id else False
            }
        }
        
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    @http.route('/api/hr/payslips', type='json', auth='public', methods=['POST'], csrf=False)
    def create_payslip(self, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            return user
            
        # Extract data from request
        data = kw.get('data', {})
        
        # Required fields
        employee_id = data.get('employee_id')
        if not employee_id:
            return {'success': False, 'error': 'Employee ID is required'}
            
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        if not date_from or not date_to:
            return {'success': False, 'error': 'Date range is required'}
            
        # Optional fields with defaults
        name = data.get('name')
        contract_id = data.get('contract_id')
        struct_id = data.get('struct_id')
        
        # Create payslip
        try:
            # If contract not specified, get active contract
            if not contract_id:
                employee = request.env['hr.employee'].sudo().browse(employee_id)
                contracts = employee.contract_ids.filtered(lambda c: c.state not in ['draft', 'cancel'])
                if contracts:
                    contract_id = contracts[0].id
            
            vals = {
                'employee_id': employee_id,
                'date_from': date_from,
                'date_to': date_to,
                'contract_id': contract_id,
                'struct_id': struct_id,
            }
            
            if name:
                vals['name'] = name
                
            payslip = request.env['hr.payslip'].sudo().create(vals)
            
            # Auto-compute if requested
            if data.get('auto_compute', False):
                payslip.compute_sheet()
                
            return {
                'success': True,
                'id': payslip.id,
                'name': payslip.name,
                'employee_id': payslip.employee_id.id,
                'employee_name': payslip.employee_id.name,
                'date_from': payslip.date_from.strftime('%Y-%m-%d') if payslip.date_from else False,
                'date_to': payslip.date_to.strftime('%Y-%m-%d') if payslip.date_to else False,
                'state': payslip.state
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    @http.route('/api/hr/payslips/batch', type='json', auth='public', methods=['POST'], csrf=False)
    def create_batch_payslips(self, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            return user
            
        # Extract data from request
        data = kw.get('data', {})
        
        # Required fields
        employee_ids = data.get('employee_ids', [])
        if not employee_ids:
            return {'success': False, 'error': 'Employee IDs are required'}
            
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        if not date_from or not date_to:
            return {'success': False, 'error': 'Date range is required'}
            
        # Optional fields
        struct_id = data.get('struct_id')
        
        # Create payslips
        try:
            payslips = []
            for employee_id in employee_ids:
                # Get employee
                employee = request.env['hr.employee'].sudo().browse(employee_id)
                if not employee.exists():
                    continue
                    
                # Get contract
                contract = False
                contracts = employee.contract_ids.filtered(lambda c: c.state not in ['draft', 'cancel'])
                if contracts:
                    contract = contracts[0]
                
                # Create payslip
                vals = {
                    'employee_id': employee_id,
                    'date_from': date_from,
                    'date_to': date_to,
                    'contract_id': contract.id if contract else False,
                    'struct_id': struct_id,
                }
                
                payslip = request.env['hr.payslip'].sudo().create(vals)
                
                # Auto-compute if requested
                if data.get('auto_compute', False):
                    payslip.compute_sheet()
                    
                payslips.append({
                    'id': payslip.id,
                    'name': payslip.name,
                    'employee_id': payslip.employee_id.id,
                    'employee_name': payslip.employee_id.name,
                    'date_from': payslip.date_from.strftime('%Y-%m-%d') if payslip.date_from else False,
                    'date_to': payslip.date_to.strftime('%Y-%m-%d') if payslip.date_to else False,
                    'state': payslip.state
                })
                
            return {
                'success': True,
                'count': len(payslips),
                'payslips': payslips
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    # --- Payslip Computation ---
    @http.route('/api/hr/payslips/<int:payslip_id>/compute', type='http', auth='public', methods=['POST'], csrf=False)
    def compute_payslip(self, payslip_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        try:
            payslip.compute_sheet()
            
            # Get lines data
            lines_data = [{
                'id': line.id,
                'name': line.name,
                'code': line.code,
                'category_id': line.category_id.id,
                'category_name': line.category_id.name,
                'amount': line.amount,
                'quantity': line.quantity,
                'rate': line.rate,
                'total': line.total
            } for line in payslip.line_ids]
            
            result = {
                'success': True,
                'message': 'Payslip computed successfully',
                'payslip_id': payslip.id,
                'state': payslip.state,
                'line_count': len(payslip.line_ids),
                'lines': lines_data
            }
        except Exception as e:
            result = {'success': False, 'error': str(e)}
            
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    # --- Payslip State Changes ---
    @http.route('/api/hr/payslips/<int:payslip_id>/confirm', type='http', auth='public', methods=['POST'], csrf=False)
    def confirm_payslip(self, payslip_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        try:
            # First compute if not already computed
            if not payslip.line_ids:
                payslip.compute_sheet()
                
            # Then confirm
            payslip.action_payslip_done()
            
            result = {
                'success': True,
                'message': 'Payslip confirmed successfully',
                'payslip_id': payslip.id,
                'state': payslip.state
            }
        except Exception as e:
            result = {'success': False, 'error': str(e)}
            
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    @http.route('/api/hr/payslips/<int:payslip_id>/cancel', type='http', auth='public', methods=['POST'], csrf=False)
    def cancel_payslip(self, payslip_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        try:
            payslip.action_payslip_cancel()
            
            result = {
                'success': True,
                'message': 'Payslip cancelled successfully',
                'payslip_id': payslip.id,
                'state': payslip.state
            }
        except Exception as e:
            result = {'success': False, 'error': str(e)}
            
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    @http.route('/api/hr/payslips/<int:payslip_id>/refund', type='http', auth='public', methods=['POST'], csrf=False)
    def refund_payslip(self, payslip_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        try:
            refund_payslip = payslip.refund_sheet()
            
            result = {
                'success': True,
                'message': 'Payslip refund created successfully',
                'original_payslip_id': payslip.id,
                'refund_payslip_id': refund_payslip[0].id,
                'refund_name': refund_payslip[0].name,
                'refund_state': refund_payslip[0].state
            }
        except Exception as e:
            result = {'success': False, 'error': str(e)}
            
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    # --- Payslip Components ---
    @http.route('/api/hr/payslips/<int:payslip_id>/lines', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_lines(self, payslip_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        # Get lines data grouped by category
        categories = {}
        for line in payslip.line_ids:
            category_id = line.category_id.id
            if category_id not in categories:
                categories[category_id] = {
                    'id': category_id,
                    'name': line.category_id.name,
                    'code': line.category_id.code,
                    'lines': [],
                    'total': 0
                }
                
            categories[category_id]['lines'].append({
                'id': line.id,
                'name': line.name,
                'code': line.code,
                'amount': line.amount,
                'quantity': line.quantity,
                'rate': line.rate,
                'total': line.total
            })
            
            categories[category_id]['total'] += line.total
            
        result = {
            'success': True,
            'payslip_id': payslip.id,
            'state': payslip.state,
            'line_count': len(payslip.line_ids),
            'categories': list(categories.values())
        }
            
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    @http.route('/api/hr/payslips/<int:payslip_id>/worked_days', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_worked_days(self, payslip_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        # Get worked days data
        worked_days = [{
            'id': wd.id,
            'name': wd.name,
            'code': wd.code,
            'number_of_days': wd.number_of_days,
            'number_of_hours': wd.number_of_hours,
            'contract_id': wd.contract_id.id if wd.contract_id else False
        } for wd in payslip.worked_days_line_ids]
            
        result = {
            'success': True,
            'payslip_id': payslip.id,
            'state': payslip.state,
            'worked_days_count': len(payslip.worked_days_line_ids),
            'worked_days': worked_days
        }
            
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    @http.route('/api/hr/payslips/<int:payslip_id>/inputs', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_inputs(self, payslip_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        # Get input data
        inputs = [{
            'id': input_line.id,
            'name': input_line.name,
            'code': input_line.code,
            'amount': input_line.amount,
            'contract_id': input_line.contract_id.id if input_line.contract_id else False
        } for input_line in payslip.input_line_ids]
            
        result = {
            'success': True,
            'payslip_id': payslip.id,
            'state': payslip.state,
            'inputs_count': len(payslip.input_line_ids),
            'inputs': inputs
        }
            
        response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
        return self._add_cors_headers(response)
        
    # --- Payslip Reports ---
    @http.route('/api/hr/payslips/<int:payslip_id>/pdf', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_pdf(self, payslip_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        # Get PDF report
        pdf = request.env.ref('hr_payroll_community.action_report_payslip').sudo().render_qweb_pdf([payslip_id])[0]
        
        response = request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename=payslip_{payslip.name}.pdf;')
            ]
        )
        return self._add_cors_headers(response)
        
    @http.route('/api/hr/payslips/<int:payslip_id>/report', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_details_report(self, payslip_id, **kw):
        if not PAYROLL_INSTALLED:
            return self._missing_module_response()
            
        is_valid, user = self._validate_api_key()
        if not is_valid:
            response = request.make_response(json.dumps(user), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            result = {'success': False, 'error': 'Payslip not found'}
            response = request.make_response(json.dumps(result), headers=[('Content-Type', 'application/json')])
            return self._add_cors_headers(response)
            
        # Get detailed report
        pdf = request.env.ref('hr_payroll_community.action_report_payslip_details').sudo().render_qweb_pdf([payslip_id])[0]
        
        response = request.make_response(
            pdf,
            headers=[
                ('Content-Type', 'application/pdf'),
                ('Content-Disposition', f'attachment; filename=payslip_details_{payslip.name}.pdf;')
            ]
        )
        return self._add_cors_headers(response) 