# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError, AccessError
import logging
from datetime import datetime
import hashlib
import json
import base64
import uuid

_logger = logging.getLogger(__name__)

class HrPayrollDataProtection(models.Model):
    _name = 'hr.payroll.data.protection'
    _description = 'Payroll Data Protection Settings'
    _order = 'id desc'
    
    name = fields.Char(string='Name', default=lambda self: uuid.uuid4().hex[:6].upper())
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    active = fields.Boolean(string='Active', default=True)
    protection_level = fields.Selection([
        ('none', 'No Additional Protection'),
        ('basic', 'Basic Protection'),
        ('advanced', 'Advanced Protection'),
        ('gdpr', 'GDPR Compliant'),
    ], string='Protection Level', default='basic', required=True)
    
    # Encryption settings
    encrypt_salary_data = fields.Boolean(string='Encrypt Salary Data', default=False)
    encrypt_personal_data = fields.Boolean(string='Encrypt Personal Data', default=False)
    encryption_key = fields.Char(string='Encryption Key', help="Auto-generated key for encryption")
    
    # Access control
    enable_two_factor = fields.Boolean(string='Enable Two-Factor Authentication', default=False)
    require_approval = fields.Boolean(
        string='Require Approval for Sensitive Operations', 
        default=False,
        help="If enabled, operations like bulk salary changes, or accessing historical salary data will require approval"
    )
    approval_user_ids = fields.Many2many(
        'res.users', 
        'payroll_security_approval_users_rel', 
        'security_id', 'user_id', 
        string='Users with Approval Rights'
    )
    
    # Audit logging
    enable_audit_logging = fields.Boolean(string='Enable Audit Logging', default=True)
    log_read_operations = fields.Boolean(string='Log Read Operations', default=False)
    log_write_operations = fields.Boolean(string='Log Write Operations', default=True)
    log_retention_days = fields.Integer(string='Log Retention (Days)', default=365)
    
    # Anonymization
    anonymize_exports = fields.Boolean(
        string='Anonymize Exports', 
        default=False,
        help="If enabled, exports of payroll data will have personal identifiers removed"
    )
    
    # Data retention policy
    payslip_retention_policy = fields.Selection([
        ('indefinite', 'Keep Indefinitely'),
        ('years_5', 'Keep for 5 Years'),
        ('years_10', 'Keep for 10 Years'),
        ('custom', 'Custom Period')
    ], string='Payslip Retention Policy', default='years_5')
    custom_retention_months = fields.Integer(string='Custom Retention Period (Months)', default=60)
    
    # GDPR compliance
    enable_data_subject_requests = fields.Boolean(
        string='Enable Data Subject Requests', 
        default=False,
        help="Allow employees to request their data or deletion"
    )
    data_officer_id = fields.Many2one('res.users', string='Data Protection Officer')
    
    # Access logs
    access_log_ids = fields.One2many('hr.payroll.access.log', 'protection_id', string='Access Logs')
    
    # Hash for integrity checking
    config_hash = fields.Char(string='Configuration Hash', compute='_compute_config_hash', store=True)
    
    @api.model
    def create(self, vals):
        if not vals.get('encryption_key'):
            vals['encryption_key'] = self._generate_encryption_key()
        return super(HrPayrollDataProtection, self).create(vals)
    
    @api.depends('protection_level', 'encrypt_salary_data', 'encrypt_personal_data', 
                 'enable_two_factor', 'require_approval', 'enable_audit_logging',
                 'anonymize_exports', 'payslip_retention_policy', 'custom_retention_months')
    def _compute_config_hash(self):
        """Calculate a hash of the configuration to detect tampering"""
        for record in self:
            config_dict = {
                'protection_level': record.protection_level,
                'encrypt_salary_data': record.encrypt_salary_data,
                'encrypt_personal_data': record.encrypt_personal_data,
                'enable_two_factor': record.enable_two_factor,
                'require_approval': record.require_approval,
                'enable_audit_logging': record.enable_audit_logging,
                'anonymize_exports': record.anonymize_exports,
                'payslip_retention_policy': record.payslip_retention_policy,
                'custom_retention_months': record.custom_retention_months,
            }
            config_str = json.dumps(config_dict, sort_keys=True)
            record.config_hash = hashlib.sha256(config_str.encode()).hexdigest()
    
    def _generate_encryption_key(self):
        """Generate a secure random encryption key"""
        return uuid.uuid4().hex
    
    def encrypt_data(self, data):
        """Encrypt data using the configured encryption key"""
        if not data:
            return False
        
        if not self.encrypt_salary_data and not self.encrypt_personal_data:
            return data
            
        try:
            from cryptography.fernet import Fernet
            key = base64.urlsafe_b64encode(self.encryption_key.ljust(32, '0').encode()[:32])
            f = Fernet(key)
            encrypted_data = f.encrypt(str(data).encode())
            return base64.b64encode(encrypted_data).decode()
        except ImportError:
            _logger.warning("cryptography library not installed, data not encrypted")
            return data
        except Exception as e:
            _logger.error(f"Error encrypting data: {str(e)}")
            return data
    
    def decrypt_data(self, encrypted_data):
        """Decrypt data using the configured encryption key"""
        if not encrypted_data:
            return False
            
        try:
            from cryptography.fernet import Fernet
            key = base64.urlsafe_b64encode(self.encryption_key.ljust(32, '0').encode()[:32])
            f = Fernet(key)
            decrypted_data = f.decrypt(base64.b64decode(encrypted_data))
            return decrypted_data.decode()
        except ImportError:
            _logger.warning("cryptography library not installed, returning original data")
            return encrypted_data
        except Exception as e:
            _logger.error(f"Error decrypting data: {str(e)}")
            return encrypted_data
    
    def get_active_protection(self):
        """Get active protection settings for the current company"""
        company_id = self.env.company.id
        protection = self.search([
            ('company_id', '=', company_id),
            ('active', '=', True)
        ], limit=1)
        
        if not protection:
            # Create default protection settings
            protection = self.create({
                'name': _('Default Protection'),
                'company_id': company_id,
                'protection_level': 'basic',
            })
            
        return protection
    
    def log_access(self, res_model, res_id, operation, user_id=None, details=None):
        """Log access to payroll data"""
        if not self.enable_audit_logging:
            return
            
        if operation == 'read' and not self.log_read_operations:
            return
            
        if operation == 'write' and not self.log_write_operations:
            return
            
        user_id = user_id or self.env.user.id
        
        log_vals = {
            'protection_id': self.id,
            'user_id': user_id,
            'res_model': res_model,
            'res_id': res_id,
            'operation': operation,
            'timestamp': fields.Datetime.now(),
            'details': details or '',
        }
        
        return self.env['hr.payroll.access.log'].create(log_vals)
    
    def requires_approval(self, operation, user_id=None):
        """Check if an operation requires approval"""
        if not self.require_approval:
            return False
            
        user_id = user_id or self.env.user.id
        
        # Administrators bypass approval
        if self.env.user.has_group('base.group_system'):
            return False
            
        # Check if user is in the approval group
        if user_id in self.approval_user_ids.ids:
            return False
            
        # These operations always require approval if setting is enabled
        sensitive_operations = [
            'bulk_salary_change',
            'access_historical_data',
            'export_payroll_data',
            'decrypt_sensitive_data',
        ]
        
        return operation in sensitive_operations
    
    def request_approval(self, operation, res_model=None, res_id=None, details=None):
        """Request approval for a sensitive operation"""
        if not self.require_approval:
            return {'approved': True}
            
        if not self.approval_user_ids:
            raise UserError(_("No approval users configured. Please set up users with approval rights."))
            
        # Create approval request
        request = self.env['hr.payroll.approval.request'].create({
            'protection_id': self.id,
            'requester_id': self.env.user.id,
            'operation': operation,
            'res_model': res_model,
            'res_id': res_id,
            'details': details or '',
            'state': 'pending',
            'request_date': fields.Datetime.now(),
        })
        
        # Notify approvers
        request.notify_approvers()
        
        return {
            'approved': False,
            'request_id': request.id,
            'message': _("Approval request sent. You will be notified when it's processed.")
        }
    
    def anonymize_payroll_data(self, data, for_export=True):
        """Anonymize payroll data by removing or hashing personal identifiers"""
        if not self.anonymize_exports and for_export:
            return data
            
        if isinstance(data, dict):
            result = data.copy()
            # Remove or hash personal identifiers
            personal_fields = ['name', 'identification_id', 'passport_id', 'bank_account_id', 'address_home_id', 'address_id']
            for field in personal_fields:
                if field in result:
                    # Use hash instead of removing to maintain data structure
                    if isinstance(result[field], str) and result[field]:
                        result[field] = hashlib.sha256(result[field].encode()).hexdigest()[:8]
                    else:
                        result[field] = None
            return result
        else:
            return data
    
    def is_data_retention_expired(self, create_date):
        """Check if data should be retained based on retention policy"""
        if not create_date:
            return False
            
        if self.payslip_retention_policy == 'indefinite':
            return False
            
        retention_months = {
            'years_5': 60,
            'years_10': 120,
            'custom': self.custom_retention_months,
        }.get(self.payslip_retention_policy, 60)
        
        retention_date = fields.Date.add(create_date, months=retention_months)
        return fields.Date.today() > retention_date

    def clean_expired_data(self):
        """Clean expired payroll data based on retention policy"""
        if self.payslip_retention_policy == 'indefinite':
            return {'success': True, 'message': _("No data to clean (indefinite retention policy).")}
            
        retention_months = {
            'years_5': 60,
            'years_10': 120,
            'custom': self.custom_retention_months,
        }.get(self.payslip_retention_policy, 60)
        
        cutoff_date = fields.Date.add(fields.Date.today(), months=-retention_months)
        
        # Get expired payslips
        expired_payslips = self.env['hr.payslip'].search([
            ('create_date', '<', cutoff_date),
            ('company_id', '=', self.company_id.id),
        ])
        
        # Archive expired payslips
        if expired_payslips:
            expired_payslips.write({'active': False})
            
            # Log the operation
            self.log_access(
                'hr.payslip', 
                0,  # 0 means multiple records
                'archive', 
                details=f"Archived {len(expired_payslips)} expired payslips older than {cutoff_date}"
            )
            
        # Clean expired logs
        if self.log_retention_days > 0:
            log_cutoff_date = fields.Date.add(fields.Date.today(), days=-self.log_retention_days)
            expired_logs = self.env['hr.payroll.access.log'].search([
                ('timestamp', '<', log_cutoff_date),
                ('protection_id', '=', self.id),
            ])
            
            if expired_logs:
                expired_logs.unlink()
        
        return {
            'success': True,
            'message': _("Cleaned %s expired payslips and logs.") % len(expired_payslips),
            'archived_count': len(expired_payslips),
        }


class HrPayrollAccessLog(models.Model):
    _name = 'hr.payroll.access.log'
    _description = 'Payroll Data Access Log'
    _order = 'timestamp desc'
    
    protection_id = fields.Many2one('hr.payroll.data.protection', string='Protection Config', ondelete='cascade')
    user_id = fields.Many2one('res.users', string='User', required=True)
    res_model = fields.Char(string='Model', required=True)
    res_id = fields.Integer(string='Record ID', default=0)
    operation = fields.Selection([
        ('read', 'Read'),
        ('write', 'Write/Modify'),
        ('create', 'Create'),
        ('unlink', 'Delete'),
        ('export', 'Export'),
        ('archive', 'Archive'),
        ('decrypt', 'Decrypt'),
        ('approve', 'Approve'),
        ('reject', 'Reject'),
    ], string='Operation', required=True)
    timestamp = fields.Datetime(string='Timestamp', required=True)
    ip_address = fields.Char(string='IP Address', compute='_compute_ip_address', store=True)
    details = fields.Text(string='Details')
    
    def _compute_ip_address(self):
        """Get IP address from request if available"""
        for record in self:
            try:
                record.ip_address = self.env['ir.http'].get_request_ip()
            except:
                record.ip_address = False


class HrPayrollApprovalRequest(models.Model):
    _name = 'hr.payroll.approval.request'
    _description = 'Payroll Operation Approval Request'
    _order = 'request_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(string='Request Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    protection_id = fields.Many2one('hr.payroll.data.protection', string='Protection Config', ondelete='cascade')
    requester_id = fields.Many2one('res.users', string='Requester', required=True)
    approver_id = fields.Many2one('res.users', string='Approver')
    operation = fields.Selection([
        ('bulk_salary_change', 'Bulk Salary Change'),
        ('access_historical_data', 'Access Historical Data'),
        ('export_payroll_data', 'Export Payroll Data'),
        ('decrypt_sensitive_data', 'Decrypt Sensitive Data'),
        ('other', 'Other Operation'),
    ], string='Operation', required=True)
    res_model = fields.Char(string='Model')
    res_id = fields.Integer(string='Record ID')
    details = fields.Text(string='Details')
    request_date = fields.Datetime(string='Request Date', required=True)
    approval_date = fields.Datetime(string='Approval Date')
    rejection_reason = fields.Text(string='Rejection Reason')
    state = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='pending', required=True, tracking=True)
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.payroll.approval.request') or _('New')
        return super(HrPayrollApprovalRequest, self).create(vals)
    
    def notify_approvers(self):
        """Notify all users with approval rights about the request"""
        approvers = self.protection_id.approval_user_ids
        if not approvers:
            return
            
        # Create a message
        msg = _("""
        <p>A new payroll approval request has been submitted:</p>
        <ul>
            <li><strong>Reference:</strong> %s</li>
            <li><strong>Requester:</strong> %s</li>
            <li><strong>Operation:</strong> %s</li>
            <li><strong>Details:</strong> %s</li>
        </ul>
        <p>Please review and take action.</p>
        """) % (
            self.name, 
            self.requester_id.name, 
            dict(self._fields['operation'].selection).get(self.operation), 
            self.details or ''
        )
        
        # Post the message
        self.message_post(
            body=msg,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=approvers.mapped('partner_id').ids
        )
        
        # Create activities for approvers
        for approver in approvers:
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'note': _('Please review this payroll approval request.'),
                'res_id': self.id,
                'res_model_id': self.env['ir.model']._get('hr.payroll.approval.request').id,
                'user_id': approver.id,
                'summary': _('Payroll Approval Request: %s') % self.name,
                'date_deadline': fields.Date.context_today(self),
            })
    
    def action_approve(self):
        """Approve the request"""
        # Check if user has approval rights
        if self.env.user.id not in self.protection_id.approval_user_ids.ids:
            raise AccessError(_("You don't have rights to approve payroll requests."))
            
        self.write({
            'state': 'approved',
            'approver_id': self.env.user.id,
            'approval_date': fields.Datetime.now()
        })
        
        # Log the approval
        self.protection_id.log_access(
            'hr.payroll.approval.request',
            self.id,
            'approve',
            details=f"Approved request {self.name} for operation {self.operation}"
        )
        
        # Notify the requester
        self.message_post(
            body=_("Your request has been approved by %s.") % self.env.user.name,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.requester_id.partner_id.id]
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_reject(self):
        """Reject the request"""
        # Check if user has approval rights
        if self.env.user.id not in self.protection_id.approval_user_ids.ids:
            raise AccessError(_("You don't have rights to reject payroll requests."))
            
        return {
            'name': _('Reject Approval Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.approval.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id}
        }
    
    def action_cancel(self):
        """Cancel the request"""
        # Only requester or admin can cancel
        if self.env.user.id != self.requester_id.id and not self.env.user.has_group('base.group_system'):
            raise AccessError(_("Only the requester or an administrator can cancel the request."))
            
        self.write({
            'state': 'cancelled',
        })
        
        # Log the cancellation
        self.protection_id.log_access(
            'hr.payroll.approval.request',
            self.id,
            'reject',
            details=f"Cancelled request {self.name} for operation {self.operation}"
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}


class HrPayrollApprovalRejectWizard(models.TransientModel):
    _name = 'hr.payroll.approval.reject.wizard'
    _description = 'Reject Payroll Approval Request'
    
    request_id = fields.Many2one('hr.payroll.approval.request', string='Approval Request', required=True)
    rejection_reason = fields.Text(string='Rejection Reason', required=True)
    
    def action_confirm_reject(self):
        """Confirm the rejection with reason"""
        self.request_id.write({
            'state': 'rejected',
            'approver_id': self.env.user.id,
            'approval_date': fields.Datetime.now(),
            'rejection_reason': self.rejection_reason
        })
        
        # Log the rejection
        self.request_id.protection_id.log_access(
            'hr.payroll.approval.request',
            self.request_id.id,
            'reject',
            details=f"Rejected request {self.request_id.name} for operation {self.request_id.operation}: {self.rejection_reason}"
        )
        
        # Notify the requester
        self.request_id.message_post(
            body=_("Your request has been rejected by %s. Reason: %s") % (self.env.user.name, self.rejection_reason),
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
            partner_ids=[self.request_id.requester_id.partner_id.id]
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'} 