from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class GeolocationController(http.Controller):
    
    @http.route('/company_geolocation/update_coordinates', type='json', auth='user')
    def update_coordinates(self, company_id, latitude, longitude):
        """
        Update company coordinates directly via AJAX call
        """
        try:
            # Validate inputs
            company_id = int(company_id)
            latitude = float(latitude)
            longitude = float(longitude)
            
            # Log the received values
            _logger.info(f"Updating coordinates for company {company_id}: lat={latitude}, lng={longitude}")
            
            # Get the company record
            company = request.env['res.company'].browse(company_id)
            if not company.exists():
                return {'success': False, 'error': f'Company not found: {company_id}'}
            
            # Update the coordinates
            company.write({
                'latitude': latitude,
                'longitude': longitude
            })
            
            # Check if the values were updated correctly
            company.invalidate_recordset()
            updated_lat = company.latitude
            updated_lng = company.longitude
            
            _logger.info(f"Updated values: lat={updated_lat}, lng={updated_lng}")
            
            return {
                'success': True,
                'latitude': updated_lat,
                'longitude': updated_lng
            }
            
        except Exception as e:
            _logger.error(f"Error updating coordinates: {str(e)}")
            return {'success': False, 'error': str(e)} 