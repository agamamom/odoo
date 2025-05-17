# Add Vietnamese labor law constraints
MAX_DAILY_HOURS = 8
MAX_WEEKLY_HOURS = 48

# Add break time logic
break_time_required = fields.Boolean(string='Yêu cầu nghỉ giữa ca', default=False)
break_duration = fields.Float(string='Thời gian nghỉ (giờ)', default=0.5) 