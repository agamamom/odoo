import uuid
from odoo import fields, models, api


class ResUsers(models.Model):
    """Add API key functionality to Users model if not already present"""
    _inherit = 'res.users'

    # Define api_key field only if it doesn't already exist in the module
    api_key = fields.Char(
        string="Legacy API Key", 
        readonly=True,
        help="API key for use with the HR REST API. The key will be generated on demand.",
        copy=False
    )

    def generate_api_key(self):
        """Generate a new API key for the user"""
        for user in self:
            user.api_key = str(uuid.uuid4())
        return True

    def reset_api_key(self):
        """Reset the API key by clearing it"""
        for user in self:
            user.api_key = False
        return True 