# Add leave approval process for Vietnam
leave_type = fields.Selection([
    ('annual', 'Nghỉ phép năm'),
    ('sick', 'Nghỉ ốm'),
    ('maternity', 'Nghỉ thai sản'),
], string='Loại nghỉ phép', required=True)

state = fields.Selection([
    ('draft', 'Nháp'),
    ('confirm', 'Chờ phê duyệt'),
    ('refuse', 'Từ chối'),
    ('validate', 'Đã phê duyệt'),
], string='Trạng thái', default='draft')

# Add method for approval process
def action_confirm(self):
    self.write({'state': 'confirm'})

def action_validate(self):
    self.write({'state': 'validate'})

def action_refuse(self):
    self.write({'state': 'refuse'}) 