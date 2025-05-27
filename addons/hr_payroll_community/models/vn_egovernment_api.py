# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import requests
import json
import logging
import base64
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class VNEgovernmentAPI(models.Model):
    _name = 'vn.egovernment.api'
    _description = 'Vietnam E-Government API Integration'
    _order = 'create_date desc'

    name = fields.Char(string='Name', required=True)
    api_type = fields.Selection([
        ('bhxh', 'BHXH API'),
        ('thue', 'Tax Authority API'),
        ('vneid', 'VNeID API'),
        ('other', 'Other')
    ], string='API Type', required=True)
    base_url = fields.Char(string='Base URL', required=True)
    api_key = fields.Char(string='API Key')
    api_secret = fields.Char(string='API Secret')
    token = fields.Char(string='Current Token')
    token_expiry = fields.Datetime(string='Token Expiry')
    is_active = fields.Boolean(string='Active', default=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    debug_mode = fields.Boolean(string='Debug Mode', default=False)
    last_sync_date = fields.Datetime(string='Last Synchronization')
    note = fields.Text(string='Notes')
    
    # Các endpoints phổ biến
    endpoint_ids = fields.One2many('vn.egovernment.api.endpoint', 'api_id', string='Endpoints')
    
    # Lịch sử gọi API
    log_ids = fields.One2many('vn.egovernment.api.log', 'api_id', string='API Logs')
    
    def _get_auth_headers(self):
        """Lấy headers xác thực cho API call"""
        self.ensure_one()
        if not self.token or self.token_expiry < fields.Datetime.now():
            self._refresh_token()
        
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
    
    def _refresh_token(self):
        """Làm mới token xác thực"""
        self.ensure_one()
        
        if self.api_type == 'bhxh':
            # Logic lấy token BHXH API
            url = f"{self.base_url}/auth/token"
            payload = {
                'client_id': self.api_key,
                'client_secret': self.api_secret,
                'grant_type': 'client_credentials'
            }
            
            try:
                response = requests.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    self.write({
                        'token': data.get('access_token'),
                        'token_expiry': fields.Datetime.now() + timedelta(seconds=data.get('expires_in', 3600))
                    })
                else:
                    _logger.error(f"Failed to refresh token: {response.text}")
                    raise UserError(_("Failed to authenticate with BHXH API. Please check credentials."))
            except Exception as e:
                _logger.error(f"Exception while refreshing token: {str(e)}")
                raise UserError(_("Connection error: %s") % str(e))
        
        elif self.api_type == 'thue':
            # Logic lấy token Tax Authority API
            url = f"{self.base_url}/api/auth"
            payload = {
                'username': self.api_key,
                'password': self.api_secret
            }
            
            try:
                response = requests.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    self.write({
                        'token': data.get('token'),
                        'token_expiry': fields.Datetime.now() + timedelta(hours=24)
                    })
                else:
                    _logger.error(f"Failed to refresh tax authority token: {response.text}")
                    raise UserError(_("Failed to authenticate with Tax Authority API. Please check credentials."))
            except Exception as e:
                _logger.error(f"Exception while refreshing tax token: {str(e)}")
                raise UserError(_("Connection error: %s") % str(e))
        
        # Các loại API khác có thể được thêm vào tương tự
    
    def call_api(self, endpoint, method='GET', payload=None, params=None, files=None):
        """Gọi API với endpoint cụ thể"""
        self.ensure_one()
        
        if not endpoint:
            raise UserError(_("API endpoint is required"))
            
        url = f"{self.base_url}/{endpoint}"
        headers = self._get_auth_headers()
        
        try:
            # Log request
            log_vals = {
                'api_id': self.id,
                'endpoint': endpoint,
                'request_method': method,
                'request_data': json.dumps(payload) if payload else '',
                'request_time': fields.Datetime.now(),
            }
            
            # Thực hiện request
            if method == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method == 'POST':
                if files:
                    # Nếu có files, không sử dụng json payload
                    headers.pop('Content-Type', None)
                    response = requests.post(url, headers=headers, data=payload, files=files)
                else:
                    response = requests.post(url, headers=headers, json=payload)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=payload)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            else:
                raise UserError(_("Method %s not supported") % method)
            
            # Cập nhật log
            log_vals.update({
                'response_code': response.status_code,
                'response_data': response.text,
                'response_time': fields.Datetime.now(),
                'success': 200 <= response.status_code < 300,
            })
            
            self.env['vn.egovernment.api.log'].create(log_vals)
            
            # Cập nhật thời gian đồng bộ
            self.write({'last_sync_date': fields.Datetime.now()})
            
            # Kiểm tra response
            if not (200 <= response.status_code < 300):
                error_msg = _("API call failed with status code %s: %s") % (response.status_code, response.text)
                _logger.error(error_msg)
                if not self.debug_mode:
                    raise UserError(error_msg)
                    
            return response
            
        except requests.exceptions.RequestException as e:
            error_msg = _("API connection error: %s") % str(e)
            _logger.error(error_msg)
            # Log lỗi
            if 'log_vals' in locals():
                log_vals.update({
                    'response_code': 0,
                    'response_data': str(e),
                    'response_time': fields.Datetime.now(),
                    'success': False,
                })
                self.env['vn.egovernment.api.log'].create(log_vals)
            
            if not self.debug_mode:
                raise UserError(error_msg)
            return None
    
    def test_connection(self):
        """Kiểm tra kết nối API"""
        self.ensure_one()
        
        try:
            if self.api_type == 'bhxh':
                self._refresh_token()
                message = _("Successfully connected to BHXH API")
            elif self.api_type == 'thue':
                self._refresh_token()
                message = _("Successfully connected to Tax Authority API")
            else:
                self._refresh_token()
                message = _("Successfully connected to API")
                
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test'),
                    'message': message,
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Test'),
                    'message': str(e),
                    'sticky': False,
                    'type': 'danger',
                }
            }


class VNEgovernmentAPIEndpoint(models.Model):
    _name = 'vn.egovernment.api.endpoint'
    _description = 'Vietnam E-Government API Endpoint'
    
    name = fields.Char(string='Name', required=True)
    api_id = fields.Many2one('vn.egovernment.api', string='API', required=True, ondelete='cascade')
    endpoint = fields.Char(string='Endpoint', required=True, help='Relative path, e.g. "api/v1/employees"')
    method = fields.Selection([
        ('GET', 'GET'),
        ('POST', 'POST'),
        ('PUT', 'PUT'),
        ('DELETE', 'DELETE')
    ], string='HTTP Method', default='GET', required=True)
    description = fields.Text(string='Description')
    sample_payload = fields.Text(string='Sample Payload')
    sample_response = fields.Text(string='Sample Response')
    is_oauth = fields.Boolean(string='Requires OAuth', default=False)
    
    def call_endpoint(self, payload=None, params=None, files=None):
        """Gọi endpoint này với payload tùy chỉnh"""
        self.ensure_one()
        return self.api_id.call_api(self.endpoint, method=self.method, payload=payload, params=params, files=files)


class VNEgovernmentAPILog(models.Model):
    _name = 'vn.egovernment.api.log'
    _description = 'Vietnam E-Government API Log'
    _order = 'request_time desc'
    
    api_id = fields.Many2one('vn.egovernment.api', string='API', required=True, ondelete='cascade')
    endpoint = fields.Char(string='Endpoint', required=True)
    request_method = fields.Char(string='Request Method', required=True)
    request_data = fields.Text(string='Request Data')
    request_time = fields.Datetime(string='Request Time', required=True)
    response_code = fields.Integer(string='Response Code')
    response_data = fields.Text(string='Response Data')
    response_time = fields.Datetime(string='Response Time')
    duration = fields.Float(string='Duration (s)', compute='_compute_duration', store=True)
    success = fields.Boolean(string='Success', default=False)
    
    @api.depends('request_time', 'response_time')
    def _compute_duration(self):
        for log in self:
            if log.request_time and log.response_time:
                delta = log.response_time - log.request_time
                log.duration = delta.total_seconds()
            else:
                log.duration = 0.0 