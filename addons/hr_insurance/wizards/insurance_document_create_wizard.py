# -*- coding: utf-8 -*-

from odoo import fields, models, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import timedelta


class InsuranceDocumentCreateWizard(models.TransientModel):
    _name = 'insurance.document.create.wizard'
    _description = 'Công cụ tạo tài liệu bảo hiểm từ mẫu'

    template_id = fields.Many2one('insurance.document.template', string='Mẫu tài liệu',
                                required=True, readonly=True)
    employee_ids = fields.Many2many('hr.employee', string='Nhân viên', required=True,
                                  help='Chọn nhân viên cần tạo tài liệu')
    insurance_ids = fields.Many2many('hr.insurance', string='Bảo hiểm',
                                    domain="[('employee_id', 'in', employee_ids)]",
                                    help='Chọn hợp đồng bảo hiểm cụ thể nếu cần')
    
    # Hide document relationship fields
    related_document_model = fields.Char(invisible=True)
    related_document_id = fields.Integer(invisible=True)
    related_partner = fields.Many2one('res.partner', invisible=True)
    
    date = fields.Date(string='Ngày tạo', default=fields.Date.today, required=True)
    deadline = fields.Date(string='Hạn nộp')
    document_type = fields.Selection(related='template_id.document_type', readonly=True)
    
    # Information fields specific to document types
    adjustment_type = fields.Selection([
        ('personal', 'Thông tin cá nhân'),
        ('salary', 'Lương đóng bảo hiểm'),
        ('position', 'Vị trí công việc'),
        ('other', 'Thông tin khác'),
    ], string='Loại điều chỉnh')
    
    bhyt_hospital = fields.Char(string='Bệnh viện đăng ký BHYT')
    bhxh_book_issue_place = fields.Char(string='Nơi cấp sổ BHXH')
    
    officer_id = fields.Many2one('hr.employee', string='Người phụ trách')
    notes = fields.Text(string='Ghi chú')
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        if self.template_id:
            if self.template_id.auto_set_deadline:
                self.deadline = fields.Date.today() + timedelta(days=self.template_id.days_deadline)
            
            if self.template_id.document_type == 'adjustment':
                self.adjustment_type = self.template_id.adjustment_type
                
            if self.template_id.document_type == 'bhyt_card':
                self.bhyt_hospital = self.template_id.default_bhyt_hospital
                
            if self.template_id.document_type == 'bhxh_book':
                self.bhxh_book_issue_place = self.template_id.default_bhxh_book_issue_place
                
            if self.template_id.auto_set_officer and self.template_id.default_officer_id:
                self.officer_id = self.template_id.default_officer_id
            else:
                self.officer_id = self.env.user
                
            self.notes = self.template_id.default_notes
    
    def action_create_documents(self):
        self.ensure_one()
        if not self.employee_ids:
            raise UserError(_('Vui lòng chọn ít nhất một nhân viên để tạo tài liệu.'))
        
        created_docs = self.env['social.insurance.document']
        
        for employee in self.employee_ids:
            # Find relevant insurance for the employee if not specified
            insurance_id = False
            if self.insurance_ids:
                employee_insurance = self.insurance_ids.filtered(lambda ins: ins.employee_id.id == employee.id)
                if employee_insurance:
                    insurance_id = employee_insurance[0].id
            else:
                # Try to find a matching insurance based on document type
                domain = [('employee_id', '=', employee.id), ('state', '=', 'active')]
                if self.document_type in ['registration', 'adjustment', 'termination', 'bhxh_book', 'tk1_ts', 'tk3_ts']:
                    domain.append(('insurance_type', '=', 'bhxh'))
                elif self.document_type == 'bhyt_card':
                    domain.append(('insurance_type', '=', 'bhyt'))
                elif self.document_type == 'unemployment':
                    domain.append(('insurance_type', '=', 'bhtn'))
                
                insurance = self.env['hr.insurance'].search(domain, limit=1)
                if insurance:
                    insurance_id = insurance.id
            
            # Create document values
            doc_vals = {
                'employee_id': employee.id,
                'insurance_id': insurance_id,
                'document_type': self.document_type,
                'date': self.date,
                'deadline': self.deadline,
                'officer_id': self.officer_id.id,
                'notes': self.notes,
            }
            
            # Add specific fields based on document type
            if self.document_type == 'adjustment':
                doc_vals.update({
                    'adjustment_type': self.adjustment_type,
                })
            elif self.document_type == 'bhyt_card':
                # Find existing BHYT info from employee's insurance
                employee_bhyt = self.env['hr.insurance'].search([
                    ('employee_id', '=', employee.id),
                    ('insurance_type', '=', 'bhyt'),
                    ('state', '=', 'active')
                ], limit=1)
                
                doc_vals.update({
                    'bhyt_hospital': self.bhyt_hospital,
                    'bhyt_number': employee_bhyt.policy_number if employee_bhyt else False,
                })
            elif self.document_type == 'bhxh_book':
                doc_vals.update({
                    'bhxh_book_issue_place': self.bhxh_book_issue_place,
                    'bhxh_book_number': employee.social_insurance_code,
                })
            
            # Create document
            doc = self.env['social.insurance.document'].create(doc_vals)
            created_docs += doc
            
            # Copy default attachments if any
            if self.template_id.default_attachment_ids:
                for attachment in self.template_id.default_attachment_ids:
                    attachment_copy = attachment.copy({
                        'res_model': 'social.insurance.document',
                        'res_id': doc.id,
                    })
                    doc.write({'attachment_ids': [(4, attachment_copy.id)]})
        
        # Show created documents
        action = {
            'name': _('Tài liệu đã tạo'),
            'type': 'ir.actions.act_window',
            'res_model': 'social.insurance.document',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_docs.ids)],
        }
        
        if len(created_docs) == 1:
            action.update({
                'view_mode': 'form',
                'res_id': created_docs.id,
            })
        
        return action 