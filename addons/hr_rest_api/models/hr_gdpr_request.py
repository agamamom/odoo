from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)

class HrPayrollDataProtection(models.Model):
    _name = 'hr.payroll.data.protection'
    _description = 'Payroll Data Protection Settings'
    _inherit = ['mail.thread']
    
    name = fields.Char(string='Name', required=True, default=lambda self: self.company_id.name + ' Data Protection')
    company_id = fields.Many2one('res.company', string='Company', required=True, default=lambda self: self.env.company)
    active = fields.Boolean(string='Active', default=True)
    
    # Data Protection Officer
    data_officer_id = fields.Many2one('res.users', string='Data Protection Officer', 
                                     tracking=True, required=True)
    
    # GDPR Settings
    enable_data_subject_requests = fields.Boolean(string='Enable Data Subject Requests', default=True,
                                                 help='Allow employees to submit GDPR-related requests')
    data_retention_period = fields.Integer(string='Data Retention Period (months)', default=24,
                                         help='Period after which personal data should be anonymized')
    auto_anonymize = fields.Boolean(string='Auto-Anonymize Old Data', default=False,
                                   help='Automatically anonymize data after retention period')

class HrGdprRequest(models.Model):
    _name = 'hr.gdpr.request'
    _description = 'GDPR Data Subject Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'
    
    name = fields.Char(string='Reference', required=True, copy=False, 
                      readonly=True, default=lambda self: _('New'))
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, 
                                 tracking=True, ondelete='cascade')
    company_id = fields.Many2one('res.company', string='Company', 
                                related='employee_id.company_id', store=True)
    request_type = fields.Selection([
        ('access', 'Access to Personal Data'),
        ('correction', 'Correction of Personal Data'),
        ('deletion', 'Deletion of Personal Data'),
        ('restriction', 'Restriction of Processing'),
        ('portability', 'Data Portability'),
        ('objection', 'Objection to Processing'),
    ], string='Request Type', required=True, tracking=True)
    
    request_date = fields.Date(string='Request Date', required=True, 
                              default=fields.Date.context_today)
    completion_date = fields.Date(string='Completion Date')
    
    field_to_correct = fields.Char(string='Field to Correct')
    current_value = fields.Text(string='Current Value')
    requested_value = fields.Text(string='Requested Value')
    
    state = fields.Selection([
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    ], string='Status', default='pending', required=True, tracking=True)
    
    assigned_to_id = fields.Many2one('res.users', string='Assigned To')
    data_officer_id = fields.Many2one('res.users', string='Data Protection Officer',
                                     related='protection_id.data_officer_id')
    protection_id = fields.Many2one('hr.payroll.data.protection', string='Data Protection Settings',
                                   compute='_compute_protection_id', store=True)
    
    note = fields.Text(string='Notes')
    rejection_reason = fields.Text(string='Rejection Reason')
    
    # For deletion requests
    anonymization_date = fields.Date(string='Anonymization Date')
    
    # For tracking
    response_file = fields.Binary(string='Response File')
    response_filename = fields.Char(string='Response Filename')
    
    @api.depends('company_id')
    def _compute_protection_id(self):
        for request in self:
            protection = self.env['hr.payroll.data.protection'].sudo().search([
                ('company_id', '=', request.company_id.id),
                ('active', '=', True)
            ], limit=1)
            request.protection_id = protection.id if protection else False
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('hr.gdpr.request') or _('New')
        return super(HrGdprRequest, self).create(vals)
    
    def action_assign_to_me(self):
        """Assign the GDPR request to the current user"""
        for request in self:
            request.write({
                'assigned_to_id': self.env.user.id,
                'state': 'in_progress'
            })
    
    def action_complete(self):
        """Mark the GDPR request as completed"""
        for request in self:
            if request.state != 'in_progress':
                raise UserError(_("Only in-progress requests can be marked as completed"))
            
            request.write({
                'state': 'completed',
                'completion_date': fields.Date.today()
            })
            
            # Notify employee
            if request.employee_id.user_id:
                request.message_subscribe(partner_ids=[request.employee_id.user_id.partner_id.id])
                request.message_post(
                    body=_("Your %s request has been completed.") % request.request_type,
                    partner_ids=[request.employee_id.user_id.partner_id.id]
                )
    
    def action_reject(self):
        """Open wizard to reject the GDPR request"""
        self.ensure_one()
        if self.state not in ['pending', 'in_progress']:
            raise UserError(_("Only pending or in-progress requests can be rejected"))
        
        return {
            'name': _('Reject GDPR Request'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.gdpr.request.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id}
        }
    
    def write(self, vals):
        # Log activity when request state changes
        if 'state' in vals and vals['state'] != self.state:
            old_state = dict(self._fields['state'].selection).get(self.state)
            new_state = dict(self._fields['state'].selection).get(vals['state'])
            self.message_post(
                body=_("Request status changed from %s to %s") % (old_state, new_state)
            )
            
        return super(HrGdprRequest, self).write(vals)


class HrGdprRequestRejectWizard(models.TransientModel):
    _name = 'hr.gdpr.request.reject.wizard'
    _description = 'Wizard to Reject GDPR Request'
    
    request_id = fields.Many2one('hr.gdpr.request', string='GDPR Request', required=True)
    rejection_reason = fields.Text(string='Rejection Reason', required=True)
    
    def action_confirm(self):
        """Confirm rejection of the GDPR request"""
        self.ensure_one()
        
        self.request_id.write({
            'state': 'rejected',
            'rejection_reason': self.rejection_reason
        })
        
        # Notify employee
        if self.request_id.employee_id.user_id:
            self.request_id.message_subscribe(partner_ids=[self.request_id.employee_id.user_id.partner_id.id])
            self.request_id.message_post(
                body=_("Your %s request has been rejected: %s") % (
                    self.request_id.request_type, self.rejection_reason
                ),
                partner_ids=[self.request_id.employee_id.user_id.partner_id.id]
            )
        
        return {'type': 'ir.actions.act_window_close'} 