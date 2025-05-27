# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class VietnamMinimumWage(models.Model):
    _name = 'vietnam.minimum.wage'
    _description = 'Lương tối thiểu vùng Việt Nam'
    _order = 'effective_date desc, region_code'
    
    name = fields.Char(string='Tên', required=True)
    amount = fields.Float(string='Số tiền', required=True, help='Lương tối thiểu vùng (VND)')
    effective_date = fields.Date(string='Ngày hiệu lực', required=True)
    region_code = fields.Selection([
        ('1', 'Vùng I'),
        ('2', 'Vùng II'),
        ('3', 'Vùng III'),
        ('4', 'Vùng IV')
    ], string='Mã vùng', required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Ghi chú')
    
    @api.constrains('region_code', 'effective_date')
    def _check_unique_region_date(self):
        for wage in self:
            existing = self.search([
                ('region_code', '=', wage.region_code),
                ('effective_date', '=', wage.effective_date),
                ('id', '!=', wage.id)
            ])
            if existing:
                raise ValidationError(_('Một mức lương tối thiểu vùng với cùng vùng và ngày hiệu lực đã tồn tại.'))
    
    @api.model
    def get_amount_by_region(self, region_code, date=None):
        """Lấy mức lương tối thiểu theo vùng và ngày có hiệu lực gần nhất"""
        if not date:
            date = fields.Date.today()
            
        wage = self.search([
            ('region_code', '=', region_code),
            ('effective_date', '<=', date),
            ('active', '=', True)
        ], limit=1, order='effective_date desc')
        
        if not wage:
            # Nếu không tìm thấy, trả về mức lương tối thiểu mặc định của vùng I
            default_amount = {
                '1': 4680000,
                '2': 4160000,
                '3': 3640000,
                '4': 3250000,
            }
            return default_amount.get(region_code, 4680000)
            
        return wage.amount


class VietnamBasicWage(models.Model):
    _name = 'vietnam.basic.wage'
    _description = 'Lương cơ sở Việt Nam'
    _order = 'effective_date desc'
    
    name = fields.Char(string='Tên', required=True)
    amount = fields.Float(string='Số tiền', required=True, help='Lương cơ sở (VND)')
    effective_date = fields.Date(string='Ngày hiệu lực', required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Ghi chú')
    
    @api.constrains('effective_date')
    def _check_unique_date(self):
        for wage in self:
            existing = self.search([
                ('effective_date', '=', wage.effective_date),
                ('id', '!=', wage.id)
            ])
            if existing:
                raise ValidationError(_('Một mức lương cơ sở với cùng ngày hiệu lực đã tồn tại.'))
    
    @api.model
    def get_current_basic_wage(self, date=None):
        """Lấy mức lương cơ sở có hiệu lực gần nhất"""
        if not date:
            date = fields.Date.today()
            
        wage = self.search([
            ('effective_date', '<=', date),
            ('active', '=', True)
        ], limit=1, order='effective_date desc')
        
        if not wage:
            # Nếu không tìm thấy, trả về mức lương cơ sở hiện tại (1.8tr)
            return 1800000
            
        return wage.amount


class VietnamTaxBracket(models.Model):
    _name = 'vietnam.tax.bracket'
    _description = 'Bậc thuế thu nhập cá nhân Việt Nam'
    _order = 'min_amount'
    
    name = fields.Char(string='Tên', required=True)
    min_amount = fields.Float(string='Giới hạn dưới', required=True)
    max_amount = fields.Float(string='Giới hạn trên', required=True)
    rate = fields.Float(string='Thuế suất (%)', required=True)
    effective_date = fields.Date(string='Ngày hiệu lực', required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Ghi chú')
    
    @api.constrains('min_amount', 'max_amount')
    def _check_amount(self):
        for bracket in self:
            if bracket.min_amount >= bracket.max_amount:
                raise ValidationError(_('Giới hạn dưới phải nhỏ hơn giới hạn trên.'))
    
    @api.model
    def get_tax_brackets(self, date=None):
        """Lấy các bậc thuế hiệu lực"""
        if not date:
            date = fields.Date.today()
            
        # Lấy ngày hiệu lực gần nhất
        latest_date = self.search([
            ('effective_date', '<=', date),
            ('active', '=', True)
        ], limit=1, order='effective_date desc').mapped('effective_date')
        
        if not latest_date:
            return []
            
        # Lấy tất cả các bậc thuế cùng ngày hiệu lực
        brackets = self.search([
            ('effective_date', '=', latest_date),
            ('active', '=', True)
        ], order='min_amount')
        
        return brackets
    
    @api.model
    def calculate_tax(self, taxable_income, date=None):
        """Tính thuế TNCN theo bậc thuế lũy tiến từng phần"""
        brackets = self.get_tax_brackets(date)
        
        if not brackets:
            # Nếu không có bậc thuế, áp dụng thuế 10%
            return taxable_income * 0.1
            
        total_tax = 0.0
        remaining_income = taxable_income
        
        for bracket in brackets:
            if remaining_income <= 0:
                break
                
            if bracket.min_amount <= remaining_income:
                # Tính thuế cho phần thu nhập trong bậc hiện tại
                bracket_income = min(remaining_income, bracket.max_amount) - bracket.min_amount
                if bracket_income > 0:
                    total_tax += bracket_income * (bracket.rate / 100.0)
                    remaining_income -= bracket_income
        
        return total_tax


class VietnamTaxDeduction(models.Model):
    _name = 'vietnam.tax.deduction'
    _description = 'Mức giảm trừ thuế TNCN Việt Nam'
    _order = 'effective_date desc'
    
    name = fields.Char(string='Tên', required=True)
    amount = fields.Float(string='Số tiền', required=True, help='Số tiền giảm trừ (VND)')
    deduction_type = fields.Selection([
        ('personal', 'Giảm trừ bản thân'),
        ('dependent', 'Giảm trừ người phụ thuộc'),
        ('insurance', 'Bảo hiểm'),
        ('charity', 'Từ thiện'),
        ('other', 'Khác')
    ], string='Loại giảm trừ', required=True)
    effective_date = fields.Date(string='Ngày hiệu lực', required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Ghi chú')
    
    @api.constrains('deduction_type', 'effective_date')
    def _check_unique_type_date(self):
        for deduction in self:
            existing = self.search([
                ('deduction_type', '=', deduction.deduction_type),
                ('effective_date', '=', deduction.effective_date),
                ('id', '!=', deduction.id)
            ])
            if existing:
                raise ValidationError(_('Một mức giảm trừ với cùng loại và ngày hiệu lực đã tồn tại.'))
    
    @api.model
    def get_deduction_amount(self, deduction_type, date=None):
        """Lấy mức giảm trừ thuế theo loại và ngày có hiệu lực gần nhất"""
        if not date:
            date = fields.Date.today()
            
        deduction = self.search([
            ('deduction_type', '=', deduction_type),
            ('effective_date', '<=', date),
            ('active', '=', True)
        ], limit=1, order='effective_date desc')
        
        if not deduction:
            # Mức giảm trừ mặc định
            default_amount = {
                'personal': 11000000,  # 11 triệu/tháng
                'dependent': 4400000,  # 4.4 triệu/người/tháng
                'insurance': 0,
                'charity': 0,
                'other': 0
            }
            return default_amount.get(deduction_type, 0)
            
        return deduction.amount


class VietnamInsuranceRate(models.Model):
    _name = 'vietnam.insurance.rate'
    _description = 'Tỷ lệ bảo hiểm xã hội Việt Nam'
    _order = 'effective_date desc'
    
    name = fields.Char(string='Tên', required=True)
    rate = fields.Float(string='Tỷ lệ (%)', required=True)
    insurance_type = fields.Selection([
        ('si', 'BHXH'),
        ('hi', 'BHYT'),
        ('ui', 'BHTN'),
        ('other', 'Khác')
    ], string='Loại bảo hiểm', required=True)
    party_type = fields.Selection([
        ('employee', 'Người lao động'),
        ('employer', 'Người sử dụng lao động')
    ], string='Bên đóng', required=True)
    effective_date = fields.Date(string='Ngày hiệu lực', required=True)
    active = fields.Boolean(default=True)
    note = fields.Text(string='Ghi chú')
    
    @api.constrains('insurance_type', 'party_type', 'effective_date')
    def _check_unique_type_party_date(self):
        for rate in self:
            existing = self.search([
                ('insurance_type', '=', rate.insurance_type),
                ('party_type', '=', rate.party_type),
                ('effective_date', '=', rate.effective_date),
                ('id', '!=', rate.id)
            ])
            if existing:
                raise ValidationError(_('Một tỷ lệ bảo hiểm với cùng loại, bên đóng và ngày hiệu lực đã tồn tại.'))
    
    @api.model
    def get_insurance_rate(self, insurance_type, party_type, date=None):
        """Lấy tỷ lệ bảo hiểm theo loại, bên đóng và ngày có hiệu lực gần nhất"""
        if not date:
            date = fields.Date.today()
            
        rate = self.search([
            ('insurance_type', '=', insurance_type),
            ('party_type', '=', party_type),
            ('effective_date', '<=', date),
            ('active', '=', True)
        ], limit=1, order='effective_date desc')
        
        if not rate:
            # Tỷ lệ mặc định
            default_rates = {
                ('si', 'employee'): 8.0,
                ('si', 'employer'): 17.5,
                ('hi', 'employee'): 1.5,
                ('hi', 'employer'): 3.0,
                ('ui', 'employee'): 1.0,
                ('ui', 'employer'): 1.0,
                ('other', 'employee'): 0.0,
                ('other', 'employer'): 0.0,
            }
            return default_rates.get((insurance_type, party_type), 0.0)
            
        return rate.rate 