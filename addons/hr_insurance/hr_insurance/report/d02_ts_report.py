# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class D02TsReport(models.AbstractModel):
    _name = 'report.hr_insurance.d02_ts_report'
    _description = 'Báo cáo D02-TS - Tình hình sử dụng lao động và đóng BHXH'
    
    @api.model
    def _get_report_values(self, docids, data=None):
        if not data:
            raise UserError(_("Không tìm thấy dữ liệu cho báo cáo."))
            
        # Get data from wizard
        report_data = data['form']
        
        return {
            'doc_ids': data['ids'],
            'doc_model': data['model'],
            'data': report_data,
            'company': report_data['company'],
            'date_from': report_data['date_from'],
            'date_to': report_data['date_to'],
            'insurance_type': report_data['insurance_type'],
            'insurance_records': report_data['insurance_records'],
            'total_records': report_data['total_records'],
            'total_salary_base': report_data['total_salary_base'],
            'total_employee': report_data['total_employee'],
            'total_company': report_data['total_company'],
            'total_all': report_data['total_all'],
        } 