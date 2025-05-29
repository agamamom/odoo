from odoo import models, fields

class ResGroupsUsersRel(models.Model):
    _name = 'res.groups.users.rel'
    _description = 'User Group Relations'
    _table = 'res_groups_users_rel'  # Map to the existing table
    _auto = False  # Prevent Odoo from creating a new table

    gid = fields.Many2one('res.groups', string='Group', required=True, ondelete='cascade')
    uid = fields.Many2one('res.users', string='User', required=True, ondelete='cascade')

    _sql_constraints = [
        ('group_user_rel_unique', 'unique(group_id, user_id)', 'The combination of group and user must be unique.')
    ]