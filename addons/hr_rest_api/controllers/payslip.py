from odoo import http
from odoo.http import request, Response
from odoo.addons.hr_rest_api.controllers.main import HrRestApiController
from odoo.tools.safe_eval import safe_eval
import json

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
        '/api/hr/payslips/<int:payslip_id>/report',
        '/api/hr/payslips/<int:payslip_id>/integration',
    ], type='http', auth='public', methods=['OPTIONS'], csrf=False)
    def options_payslips(self, **kw):
        return self._handle_options_request()

    # --- Payslip CRUD ---
    @http.route('/api/hr/payslips', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslips(self, **kw):
        """List payslips (with filters)"""
        fields = [
            'id', 'name', 'number', 'employee_id', 'date_from', 'date_to', 'state',
            'company_id', 'payslip_run_id', 'contract_id', 'struct_id', 'credit_note',
        ]
        domain = safe_eval(kw.get('domain', '[]')) if 'domain' in kw else []
        limit = int(kw.get('limit', 100))
        offset = int(kw.get('offset', 0))
        order = kw.get('order', 'id desc')
        result = self._handle_request('hr.payslip', fields, domain, limit, offset, order)
        return request.make_response(json.dumps(result), [('Content-Type', 'application/json')])

    @http.route('/api/hr/payslips/<int:payslip_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip(self, payslip_id, **kw):
        """Get a single payslip by ID"""
        result = self._handle_request('hr.payslip', ['*'], [('id', '=', payslip_id)], 1)
        return request.make_response(json.dumps(result), [('Content-Type', 'application/json')])

    @http.route('/api/hr/payslips', type='json', auth='public', methods=['POST'], csrf=False)
    def create_payslip(self, **kw):
        """Create a payslip for a single employee"""
        data = kw.get('data') or kw
        result = self._handle_create('hr.payslip', data)
        return result

    @http.route('/api/hr/payslips/batch', type='json', auth='public', methods=['POST'], csrf=False)
    def create_payslips_batch(self, **kw):
        """Batch create payslips for multiple employees"""
        datas = kw.get('datas') or kw.get('data') or []
        created = []
        errors = []
        for data in datas:
            res = self._handle_create('hr.payslip', data)
            if res.get('success'):
                created.append(res['id'])
            else:
                errors.append(res)
        return {'success': not errors, 'created': created, 'errors': errors}

    @http.route('/api/hr/payslips/<int:payslip_id>', type='json', auth='public', methods=['PUT'], csrf=False)
    def update_payslip(self, payslip_id, **kw):
        data = kw.get('data') or kw
        result = self._handle_update('hr.payslip', payslip_id, data)
        return result

    @http.route('/api/hr/payslips/<int:payslip_id>', type='http', auth='public', methods=['DELETE'], csrf=False)
    def delete_payslip(self, payslip_id, **kw):
        result = self._handle_delete('hr.payslip', payslip_id)
        return request.make_response(json.dumps(result), [('Content-Type', 'application/json')])

    # --- Payslip Computation ---
    @http.route('/api/hr/payslips/<int:payslip_id>/compute', type='json', auth='public', methods=['POST'], csrf=False)
    def compute_payslip(self, payslip_id, **kw):
        is_valid, user = self._validate_api_key()
        if not is_valid:
            return user
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            return {'success': False, 'error': 'Payslip not found'}
        payslip.action_compute_sheet()
        return {'success': True, 'message': 'Payslip computed'}

    # --- Payslip Validation ---
    @http.route('/api/hr/payslips/<int:payslip_id>/set_draft', type='json', auth='public', methods=['POST'], csrf=False)
    def set_payslip_draft(self, payslip_id, **kw):
        is_valid, user = self._validate_api_key()
        if not is_valid:
            return user
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            return {'success': False, 'error': 'Payslip not found'}
        payslip.action_payslip_draft()
        return {'success': True, 'message': 'Payslip set to draft'}

    @http.route('/api/hr/payslips/<int:payslip_id>/confirm', type='json', auth='public', methods=['POST'], csrf=False)
    def confirm_payslip(self, payslip_id, **kw):
        is_valid, user = self._validate_api_key()
        if not is_valid:
            return user
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            return {'success': False, 'error': 'Payslip not found'}
        payslip.action_payslip_done()
        return {'success': True, 'message': 'Payslip confirmed'}

    @http.route('/api/hr/payslips/<int:payslip_id>/cancel', type='json', auth='public', methods=['POST'], csrf=False)
    def cancel_payslip(self, payslip_id, **kw):
        is_valid, user = self._validate_api_key()
        if not is_valid:
            return user
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            return {'success': False, 'error': 'Payslip not found'}
        payslip.action_payslip_cancel()
        return {'success': True, 'message': 'Payslip cancelled'}

    @http.route('/api/hr/payslips/<int:payslip_id>/refund', type='json', auth='public', methods=['POST'], csrf=False)
    def refund_payslip(self, payslip_id, **kw):
        is_valid, user = self._validate_api_key()
        if not is_valid:
            return user
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            return {'success': False, 'error': 'Payslip not found'}
        payslip.action_refund_sheet()
        return {'success': True, 'message': 'Payslip refunded'}

    # --- Payslip Lines ---
    @http.route('/api/hr/payslips/<int:payslip_id>/lines', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_lines(self, payslip_id, **kw):
        is_valid, user = self._validate_api_key()
        if not is_valid:
            return request.make_response(json.dumps(user), [('Content-Type', 'application/json')])
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            return request.make_response(json.dumps({'success': False, 'error': 'Payslip not found'}), [('Content-Type', 'application/json')])
        lines = payslip.line_ids.read(['id', 'name', 'code', 'category_id', 'amount', 'total', 'rate', 'quantity', 'sequence'])
        return request.make_response(json.dumps({'success': True, 'lines': lines}), [('Content-Type', 'application/json')])

    # --- Integration Info ---
    @http.route('/api/hr/payslips/<int:payslip_id>/integration', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_integration(self, payslip_id, **kw):
        is_valid, user = self._validate_api_key()
        if not is_valid:
            return request.make_response(json.dumps(user), [('Content-Type', 'application/json')])
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            return request.make_response(json.dumps({'success': False, 'error': 'Payslip not found'}), [('Content-Type', 'application/json')])
        # Collect related info
        contract = payslip.contract_id.read(['id', 'name', 'date_start', 'date_end']) if payslip.contract_id else None
        time_off = payslip.worked_days_line_ids.read(['id', 'name', 'number_of_days', 'number_of_hours'])
        loans = request.env['hr.loan.line'].sudo().search([('payslip_id', '=', payslip.id)]).read(['id', 'loan_id', 'amount', 'date'])
        advances = request.env['salary.advance'].sudo().search([('employee_id', '=', payslip.employee_id.id), ('state', '=', 'approved')]).read(['id', 'amount', 'date', 'state'])
        accounting = payslip.company_id.read(['id', 'name']) if payslip.company_id else None
        return request.make_response(json.dumps({
            'success': True,
            'contract': contract,
            'time_off': time_off,
            'loans': loans,
            'advances': advances,
            'accounting': accounting,
        }), [('Content-Type', 'application/json')])

    # --- Payslip Reporting ---
    @http.route('/api/hr/payslips/<int:payslip_id>/report', type='http', auth='public', methods=['GET'], csrf=False)
    def get_payslip_report(self, payslip_id, **kw):
        is_valid, user = self._validate_api_key()
        if not is_valid:
            return request.make_response(json.dumps(user), [('Content-Type', 'application/json')])
        payslip = request.env['hr.payslip'].sudo().browse(payslip_id)
        if not payslip.exists():
            return request.make_response(json.dumps({'success': False, 'error': 'Payslip not found'}), [('Content-Type', 'application/json')])
        # Render payslip PDF report
        pdf = request.env.ref('hr_payroll_community.action_report_payslip').sudo()._render_qweb_pdf([payslip.id])[0]
        headers = [
            ('Content-Type', 'application/pdf'),
            ('Content-Disposition', 'attachment; filename="payslip_%d.pdf"' % payslip.id)
        ]
        return request.make_response(pdf, headers) 