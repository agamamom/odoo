# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
import numpy as np
from datetime import datetime, timedelta
import base64
import io
import math
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

try:
    # Thư viện thống kê cho phân tích dữ liệu và dự báo
    # Lưu ý: Các thư viện này nên được cài đặt trong môi trường Odoo
    from scipy import stats
    from statsmodels.tsa.arima.model import ARIMA
    import pandas as pd
    ANALYTICS_LIBS_INSTALLED = True
except ImportError:
    ANALYTICS_LIBS_INSTALLED = False


class HrPayrollAnalytics(models.Model):
    _name = 'hr.payroll.analytics'
    _description = 'Payroll Analytics and Forecast'
    _order = 'create_date desc'
    
    name = fields.Char(string='Name', required=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    date_from = fields.Date(string='Date From', required=True, default=lambda self: fields.Date.today() - relativedelta(months=12))
    date_to = fields.Date(string='Date To', required=True, default=lambda self: fields.Date.today())
    forecast_months = fields.Integer(string='Forecast Months', default=3)
    department_id = fields.Many2one('hr.department', string='Department')
    job_id = fields.Many2one('hr.job', string='Job Position')
    category_id = fields.Many2one('hr.employee.category', string='Employee Tag')
    include_fixed = fields.Boolean(string='Include Fixed Salary', default=True)
    include_variable = fields.Boolean(string='Include Variable Salary', default=True)
    include_allowances = fields.Boolean(string='Include Allowances', default=True)
    include_deductions = fields.Boolean(string='Include Deductions', default=True)
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('analyzing', 'Analyzing'),
        ('done', 'Done'),
        ('failed', 'Failed')
    ], string='Status', default='draft')
    
    # Kết quả phân tích
    line_ids = fields.One2many('hr.payroll.analytics.line', 'analytics_id', string='Analysis Lines')
    forecast_ids = fields.One2many('hr.payroll.analytics.forecast', 'analytics_id', string='Forecast Lines')
    
    total_past_payroll = fields.Float(string='Total Past Payroll', compute='_compute_totals', store=True)
    total_forecast_payroll = fields.Float(string='Total Forecast Payroll', compute='_compute_totals', store=True)
    avg_monthly_payroll = fields.Float(string='Average Monthly Payroll', compute='_compute_totals', store=True)
    
    anomaly_count = fields.Integer(string='Anomalies Detected', compute='_compute_totals', store=True)
    trend_direction = fields.Selection([
        ('increasing', 'Increasing'),
        ('decreasing', 'Decreasing'),
        ('stable', 'Stable'),
        ('fluctuating', 'Fluctuating')
    ], string='Trend', compute='_compute_totals', store=True)
    
    chart_data = fields.Text(string='Chart Data', compute='_compute_chart_data')
    report_file = fields.Binary(string='Report File')
    report_filename = fields.Char(string='Report Filename')
    
    notes = fields.Text(string='Notes')
    
    @api.depends('line_ids', 'forecast_ids')
    def _compute_totals(self):
        for record in self:
            # Tính tổng lương quá khứ
            record.total_past_payroll = sum(record.line_ids.mapped('total_amount'))
            
            # Tính tổng lương dự báo
            record.total_forecast_payroll = sum(record.forecast_ids.mapped('forecast_amount'))
            
            # Tính trung bình lương hàng tháng
            record.avg_monthly_payroll = record.total_past_payroll / len(record.line_ids) if record.line_ids else 0
            
            # Tính số lượng dị thường
            record.anomaly_count = len(record.line_ids.filtered(lambda l: l.is_anomaly))
            
            # Xác định hướng xu hướng
            if record.line_ids:
                amounts = record.line_ids.mapped('total_amount')
                if len(amounts) >= 2:
                    slope, _, _, _, _ = stats.linregress(range(len(amounts)), amounts) if ANALYTICS_LIBS_INSTALLED else (0, 0, 0, 0, 0)
                    
                    # Mức độ dao động
                    std_dev = np.std(amounts) if ANALYTICS_LIBS_INSTALLED else 0
                    mean = np.mean(amounts) if ANALYTICS_LIBS_INSTALLED else 0
                    
                    if std_dev / mean > 0.1:  # Độ dao động lớn
                        record.trend_direction = 'fluctuating'
                    elif abs(slope) < 0.01 * mean:  # Ổn định
                        record.trend_direction = 'stable'
                    elif slope > 0:  # Tăng
                        record.trend_direction = 'increasing'
                    else:  # Giảm
                        record.trend_direction = 'decreasing'
                else:
                    record.trend_direction = 'stable'
            else:
                record.trend_direction = 'stable'
    
    def _compute_chart_data(self):
        for record in self:
            data = {
                'labels': [],
                'datasets': [
                    {
                        'label': _('Actual Payroll'),
                        'data': [],
                        'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                        'borderColor': 'rgba(75, 192, 192, 1)',
                    },
                    {
                        'label': _('Forecast Payroll'),
                        'data': [],
                        'backgroundColor': 'rgba(255, 159, 64, 0.2)',
                        'borderColor': 'rgba(255, 159, 64, 1)',
                    }
                ]
            }
            
            # Dữ liệu quá khứ
            for line in record.line_ids:
                data['labels'].append(line.date.strftime('%m/%Y'))
                data['datasets'][0]['data'].append(line.total_amount)
                data['datasets'][1]['data'].append(None)  # Không có dự báo cho quá khứ
            
            # Dữ liệu dự báo
            for i, line in enumerate(record.forecast_ids):
                # Nếu là tháng dự báo đầu tiên, nối với dữ liệu thực tế
                if i == 0 and record.line_ids:
                    continue  # Bỏ qua tháng đầu tiên vì có thể trùng
                    
                data['labels'].append(line.date.strftime('%m/%Y'))
                data['datasets'][0]['data'].append(None)  # Không có dữ liệu thực tế
                data['datasets'][1]['data'].append(line.forecast_amount)
            
            record.chart_data = str(data)
    
    def action_analyze(self):
        self.ensure_one()
        if not ANALYTICS_LIBS_INSTALLED and not self.env.context.get('no_lib_warning'):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Missing Dependencies'),
                    'message': _('Required libraries (scipy, statsmodels, pandas) are not installed. Analytics will use simplified calculations.'),
                    'sticky': False,
                    'type': 'warning',
                }
            }
        
        # Xoá các dòng phân tích cũ
        self.line_ids.unlink()
        self.forecast_ids.unlink()
        
        # Cập nhật trạng thái
        self.write({'state': 'analyzing'})
        
        try:
            # Gọi hàm phân tích lương theo tháng
            self._analyze_monthly_payroll()
            
            # Gọi hàm dự báo lương
            self._forecast_payroll()
            
            # Phát hiện dị thường
            self._detect_anomalies()
            
            # Cập nhật trạng thái
            self.write({'state': 'done'})
            
            # Tạo báo cáo
            self._generate_report()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Analysis Complete'),
                    'message': _('Payroll analysis and forecast completed successfully.'),
                    'sticky': False,
                    'type': 'success',
                }
            }
        except Exception as e:
            _logger.error(f"Error during payroll analysis: {str(e)}")
            self.write({
                'state': 'failed',
                'notes': str(e)
            })
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Analysis Failed'),
                    'message': str(e),
                    'sticky': False,
                    'type': 'danger',
                }
            }
    
    def _analyze_monthly_payroll(self):
        """Phân tích dữ liệu lương theo tháng"""
        # Xây dựng domain để lọc phiếu lương
        domain = [
            ('date_from', '>=', self.date_from),
            ('date_to', '<=', self.date_to),
            ('state', '=', 'done')
        ]
        
        if self.department_id:
            domain.append(('employee_id.department_id', '=', self.department_id.id))
        if self.job_id:
            domain.append(('employee_id.job_id', '=', self.job_id.id))
        if self.category_id:
            domain.append(('employee_id.category_ids', 'in', [self.category_id.id]))
        
        # Lấy tất cả phiếu lương thỏa mãn điều kiện
        payslips = self.env['hr.payslip'].search(domain)
        
        if not payslips:
            raise UserError(_("No payslips found for the selected criteria and date range."))
        
        # Phân nhóm theo tháng
        payslips_by_month = {}
        for slip in payslips:
            month_key = slip.date_from.strftime('%Y-%m-01')
            if month_key not in payslips_by_month:
                payslips_by_month[month_key] = []
            payslips_by_month[month_key].append(slip)
        
        # Tạo các dòng phân tích theo tháng
        analytics_lines = []
        for month_key, month_payslips in payslips_by_month.items():
            month_date = fields.Date.from_string(month_key)
            
            # Tính tổng lương cố định và biến đổi
            fixed_amount = 0
            variable_amount = 0
            allowances_amount = 0
            deductions_amount = 0
            
            # Lấy các loại lương từ các phiếu lương
            for slip in month_payslips:
                for line in slip.line_ids:
                    rule = line.salary_rule_id
                    # Phân loại theo rule
                    if rule.category_id.code in ('BASIC', 'ALW') and self.include_fixed:
                        if not rule.variable_salary:
                            fixed_amount += line.total
                    if rule.variable_salary and self.include_variable:
                        variable_amount += line.total
                    if rule.category_id.code == 'ALW' and self.include_allowances:
                        allowances_amount += line.total
                    if rule.category_id.code in ('DED', 'COMP') and self.include_deductions:
                        deductions_amount += line.total
            
            # Tạo dữ liệu cho dòng phân tích
            analytics_line_vals = {
                'analytics_id': self.id,
                'date': month_date,
                'payslip_count': len(month_payslips),
                'employee_count': len(set(slip.employee_id.id for slip in month_payslips)),
                'fixed_amount': fixed_amount,
                'variable_amount': variable_amount,
                'allowances_amount': allowances_amount,
                'deductions_amount': deductions_amount,
                'total_amount': fixed_amount + variable_amount + allowances_amount - abs(deductions_amount),
            }
            analytics_lines.append(analytics_line_vals)
        
        # Tạo các dòng phân tích
        for line in sorted(analytics_lines, key=lambda l: l['date']):
            self.env['hr.payroll.analytics.line'].create(line)
    
    def _forecast_payroll(self):
        """Dự báo lương cho các tháng tiếp theo"""
        if not self.line_ids:
            return
        
        # Sắp xếp dòng phân tích theo thời gian
        lines = self.line_ids.sorted(lambda l: l.date)
        
        # Lấy dữ liệu quá khứ
        dates = [line.date for line in lines]
        amounts = [line.total_amount for line in lines]
        
        if ANALYTICS_LIBS_INSTALLED and len(amounts) >= 3:
            # Sử dụng ARIMA cho dự báo
            try:
                # Tạo chuỗi thời gian
                time_series = pd.Series(amounts, index=pd.DatetimeIndex(dates, freq='MS'))
                
                # Tạo mô hình ARIMA (p,d,q) = (1,1,1) cho dự báo đơn giản
                model = ARIMA(time_series, order=(1, 1, 1))
                model_fit = model.fit()
                
                # Dự báo
                last_date = dates[-1]
                for i in range(1, self.forecast_months + 1):
                    forecast_date = last_date + relativedelta(months=i)
                    forecast_result = model_fit.forecast(steps=i)
                    forecast_amount = forecast_result[-1]
                    
                    # Đảm bảo số dương
                    forecast_amount = max(0, forecast_amount)
                    
                    self.env['hr.payroll.analytics.forecast'].create({
                        'analytics_id': self.id,
                        'date': forecast_date,
                        'forecast_amount': forecast_amount,
                        'confidence_low': max(0, forecast_amount * 0.9),  # Đơn giản hóa khoảng tin cậy 90%
                        'confidence_high': forecast_amount * 1.1,
                    })
            except Exception as e:
                _logger.error(f"ARIMA forecasting error: {str(e)}")
                # Nếu ARIMA thất bại, sử dụng dự báo đơn giản
                self._simple_forecast()
        else:
            # Sử dụng dự báo đơn giản nếu không có đủ dữ liệu hoặc thư viện
            self._simple_forecast()
    
    def _simple_forecast(self):
        """Dự báo đơn giản dựa trên trung bình và xu hướng"""
        if not self.line_ids:
            return
            
        lines = self.line_ids.sorted(lambda l: l.date)
        
        # Tính trung bình và xu hướng
        amounts = [line.total_amount for line in lines]
        avg_amount = sum(amounts) / len(amounts)
        
        # Tính xu hướng đơn giản (% thay đổi trung bình)
        trend = 0
        if len(amounts) >= 2:
            changes = [(amounts[i] - amounts[i-1]) / amounts[i-1] for i in range(1, len(amounts))]
            trend = sum(changes) / len(changes)
        
        # Dự báo các tháng tiếp theo
        last_date = lines[-1].date
        last_amount = amounts[-1]
        
        for i in range(1, self.forecast_months + 1):
            forecast_date = last_date + relativedelta(months=i)
            # Dự báo với xu hướng
            forecast_amount = last_amount * (1 + trend) ** i
            
            # Đảm bảo số dương và hợp lý
            forecast_amount = max(0, forecast_amount)
            if abs(forecast_amount - avg_amount) > avg_amount:  # Kiểm tra giá trị vượt quá hợp lý
                forecast_amount = avg_amount * (1 + trend * i * 0.5)  # Điều chỉnh xu hướng
            
            # Thêm biến động ngẫu nhiên nhỏ để thực tế hơn
            random_factor = 1 + (np.random.random() * 0.1 - 0.05) if ANALYTICS_LIBS_INSTALLED else 1
            forecast_amount *= random_factor
            
            self.env['hr.payroll.analytics.forecast'].create({
                'analytics_id': self.id,
                'date': forecast_date,
                'forecast_amount': forecast_amount,
                'confidence_low': forecast_amount * 0.85,  # Khoảng tin cậy 85%
                'confidence_high': forecast_amount * 1.15,
            })
    
    def _detect_anomalies(self):
        """Phát hiện dị thường trong dữ liệu lương"""
        if not self.line_ids or len(self.line_ids) < 3:
            return
            
        lines = self.line_ids.sorted(lambda l: l.date)
        amounts = [line.total_amount for line in lines]
        
        if ANALYTICS_LIBS_INSTALLED:
            # Sử dụng Z-score để phát hiện dị thường
            mean = np.mean(amounts)
            std = np.std(amounts)
            
            if std == 0:  # Tránh chia cho 0
                return
                
            z_scores = [(x - mean) / std for x in amounts]
            
            # Cập nhật là dị thường nếu z-score vượt ngưỡng 2
            for i, line in enumerate(lines):
                line.write({
                    'is_anomaly': abs(z_scores[i]) > 2,
                    'z_score': z_scores[i]
                })
        else:
            # Phương pháp IQR đơn giản nếu không có thư viện
            sorted_amounts = sorted(amounts)
            q1, q3 = sorted_amounts[len(sorted_amounts) // 4], sorted_amounts[3 * len(sorted_amounts) // 4]
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            for i, line in enumerate(lines):
                line.write({
                    'is_anomaly': amounts[i] < lower_bound or amounts[i] > upper_bound
                })
    
    def _generate_report(self):
        """Tạo báo cáo phân tích lương"""
        if not self.line_ids:
            return
            
        # Tạo dữ liệu cho báo cáo Excel
        if not ANALYTICS_LIBS_INSTALLED:
            return
            
        # Tạo file Excel
        output = io.BytesIO()
        workbook = pd.ExcelWriter(output, engine='xlsxwriter')
        
        # Dữ liệu phân tích
        analysis_data = []
        for line in self.line_ids:
            analysis_data.append({
                'Date': line.date,
                'Total Amount': line.total_amount,
                'Fixed Salary': line.fixed_amount,
                'Variable Salary': line.variable_amount,
                'Allowances': line.allowances_amount,
                'Deductions': line.deductions_amount,
                'Employee Count': line.employee_count,
                'Payslip Count': line.payslip_count,
                'Is Anomaly': 'Yes' if line.is_anomaly else 'No',
            })
            
        if analysis_data:
            df_analysis = pd.DataFrame(analysis_data)
            df_analysis.to_excel(workbook, sheet_name='Payroll Analysis', index=False)
        
        # Dữ liệu dự báo
        forecast_data = []
        for line in self.forecast_ids:
            forecast_data.append({
                'Date': line.date,
                'Forecast Amount': line.forecast_amount,
                'Lower Bound': line.confidence_low,
                'Upper Bound': line.confidence_high,
            })
            
        if forecast_data:
            df_forecast = pd.DataFrame(forecast_data)
            df_forecast.to_excel(workbook, sheet_name='Payroll Forecast', index=False)
        
        # Dữ liệu tổng hợp
        summary_data = [{
            'Total Past Payroll': self.total_past_payroll,
            'Total Forecast Payroll': self.total_forecast_payroll,
            'Average Monthly Payroll': self.avg_monthly_payroll,
            'Anomalies Detected': self.anomaly_count,
            'Trend Direction': dict(self._fields['trend_direction'].selection).get(self.trend_direction),
        }]
        
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(workbook, sheet_name='Summary', index=False)
        
        # Lưu workbook
        workbook.save()
        
        # Lưu file Excel
        report_data = output.getvalue()
        self.write({
            'report_file': base64.b64encode(report_data),
            'report_filename': f'payroll_analysis_{fields.Date.today()}.xlsx'
        })
    
    def action_view_chart(self):
        """Hiển thị biểu đồ phân tích lương"""
        self.ensure_one()
        return {
            'name': _('Payroll Analytics Chart'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.payroll.analytics',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'current',
            'context': {'form_view_ref': 'hr_payroll_community.hr_payroll_analytics_chart_view_form'},
        }
    
    def action_download_report(self):
        """Tải xuống báo cáo phân tích"""
        self.ensure_one()
        
        if not self.report_file:
            self._generate_report()
            
        if not self.report_file:
            raise UserError(_("No report available. Please run the analysis first."))
            
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=hr.payroll.analytics&id={self.id}&field=report_file&filename={self.report_filename}&download=true',
            'target': 'self',
        }
    
    def action_reset(self):
        """Đặt lại phân tích về trạng thái nháp"""
        self.write({
            'state': 'draft',
            'line_ids': [(5, 0, 0)],  # Xoá tất cả các dòng
            'forecast_ids': [(5, 0, 0)],  # Xoá tất cả dự báo
            'report_file': False,
            'report_filename': False,
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


class HrPayrollAnalyticsLine(models.Model):
    _name = 'hr.payroll.analytics.line'
    _description = 'Payroll Analytics Line'
    _order = 'date'
    
    analytics_id = fields.Many2one('hr.payroll.analytics', string='Analytics', required=True, ondelete='cascade')
    date = fields.Date(string='Month', required=True)
    payslip_count = fields.Integer(string='Payslip Count')
    employee_count = fields.Integer(string='Employee Count')
    fixed_amount = fields.Float(string='Fixed Salary')
    variable_amount = fields.Float(string='Variable Salary')
    allowances_amount = fields.Float(string='Allowances')
    deductions_amount = fields.Float(string='Deductions')
    total_amount = fields.Float(string='Total Amount')
    is_anomaly = fields.Boolean(string='Is Anomaly', default=False)
    z_score = fields.Float(string='Z-Score', default=0)


class HrPayrollAnalyticsForecast(models.Model):
    _name = 'hr.payroll.analytics.forecast'
    _description = 'Payroll Analytics Forecast'
    _order = 'date'
    
    analytics_id = fields.Many2one('hr.payroll.analytics', string='Analytics', required=True, ondelete='cascade')
    date = fields.Date(string='Month', required=True)
    forecast_amount = fields.Float(string='Forecast Amount')
    confidence_low = fields.Float(string='Lower Bound')
    confidence_high = fields.Float(string='Upper Bound')


class HrSalaryRule(models.Model):
    _inherit = 'hr.salary.rule'
    
    variable_salary = fields.Boolean(string='Variable Salary', default=False,
                                   help='Check this if the salary rule represents a variable component that changes monthly')
    analytics_category = fields.Selection([
        ('fixed', 'Fixed Salary'),
        ('variable', 'Variable Salary'),
        ('allowance', 'Allowance'),
        ('deduction', 'Deduction'),
        ('other', 'Other')
    ], string='Analytics Category', default='fixed',
       help='Category used in payroll analytics') 