# -*- coding: utf-8 -*-
from odoo import models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class D03TsReport(models.AbstractModel):
    _name = 'report.hr_insurance.d03_ts_report'
    _description = 'Báo cáo D03-TS - Thay đổi thông tin người tham gia BHXH'
    
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
            'change_type': report_data['change_type'],
            'change_records': report_data['change_records'],
            'total_records': report_data['total_records'],
            'total_new': report_data['total_new'],
            'total_end': report_data['total_end'],
            'total_update': report_data['total_update'],
        } 