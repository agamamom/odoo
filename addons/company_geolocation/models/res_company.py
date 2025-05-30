from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'
    
    location_address = fields.Char(string='Location Address', help='Address selected from map', compute='_compute_location_address', store=True)
    latitude = fields.Float(string='Latitude', digits=(16, 8), default=0.0)
    longitude = fields.Float(string='Longitude', digits=(16, 8), default=0.0)
    
    @api.depends('street', 'street2', 'city', 'state_id', 'zip', 'country_id')
    def _compute_location_address(self):
        """Tính toán location_address dựa trên các trường địa chỉ"""
        for company in self:
            address_parts = []
            if company.street:
                address_parts.append(company.street)
            if company.street2:
                address_parts.append(company.street2)
            if company.city:
                address_parts.append(company.city)
            if company.state_id:
                address_parts.append(company.state_id.name)
            if company.zip:
                address_parts.append(company.zip)
            if company.country_id:
                address_parts.append(company.country_id.name)
            
            company.location_address = ', '.join(filter(None, address_parts))
            _logger.info(f"Computed location_address for company {company.id}: {company.location_address}")
    
    @api.onchange('location_address')
    def _onchange_location_address(self):
        """When location_address changes, update coordinates if possible"""
        # Logic will be handled by the widget
        pass
    
    def update_coordinates(self, latitude, longitude):
        """Update coordinates directly - called from JavaScript"""
        self.ensure_one()
        
        _logger.info(f"Direct update_coordinates call for company {self.id}: lat={latitude}, lng={longitude}")
        
        try:
            # Ensure we're dealing with float values
            lat_float = float(latitude)
            lng_float = float(longitude)
            
            # Update the record
            self.write({
                'latitude': lat_float,
                'longitude': lng_float
            })
            
            # Verify the update
            self.env.cr.commit()  # Force commit to make sure changes are saved
            
            # Re-read to verify
            self.invalidate_recordset()
            _logger.info(f"Coordinates updated and verified: lat={self.latitude}, lng={self.longitude}")
            
            return True
        except Exception as e:
            _logger.error(f"Error in update_coordinates: {e}")
            return False
    
    def write(self, vals):
        """Override write method to handle coordinates properly"""
        # Log what we're receiving
        _logger.info(f"ResCompany.write called with vals: {vals}")
        
        # Make sure latitude and longitude are properly stored as floats
        if 'latitude' in vals:
            try:
                if vals['latitude'] is not None and vals['latitude'] != '':
                    original_value = vals['latitude']
                    vals['latitude'] = float(vals['latitude'])
                    _logger.info(f"Converted latitude from {original_value} to {vals['latitude']}")
                else:
                    vals['latitude'] = 0.0
                    _logger.info("Empty latitude value set to 0.0")
            except (ValueError, TypeError) as e:
                _logger.warning(f"Error converting latitude value '{vals['latitude']}': {e}")
                vals['latitude'] = 0.0
        
        if 'longitude' in vals:
            try:
                if vals['longitude'] is not None and vals['longitude'] != '':
                    original_value = vals['longitude']
                    vals['longitude'] = float(vals['longitude'])
                    _logger.info(f"Converted longitude from {original_value} to {vals['longitude']}")
                else:
                    vals['longitude'] = 0.0
                    _logger.info("Empty longitude value set to 0.0")
            except (ValueError, TypeError) as e:
                _logger.warning(f"Error converting longitude value '{vals['longitude']}': {e}")
                vals['longitude'] = 0.0
        
        # Debug the values being saved
        self._log_coordinate_values(vals)
        
        # Call super to update the record
        result = super(ResCompany, self).write(vals)
        
        # Verify the values were actually written
        if 'latitude' in vals or 'longitude' in vals:
            for record in self:
                _logger.info(f"After write: Company ID {record.id} - lat={record.latitude}, lng={record.longitude}")
                
        return result
    
    def _log_coordinate_values(self, vals):
        """Log coordinate values for debugging"""
        if 'latitude' in vals or 'longitude' in vals:
            lat = vals.get('latitude', 'not in vals')
            lng = vals.get('longitude', 'not in vals')
            
            _logger.info(f"Writing coordinates: lat={lat}, lng={lng}")
            
            # Use Odoo's logging system
            try:
                self.env.cr.execute("""
                    INSERT INTO ir_logging(create_date, create_uid, type, dbname, name, level, message, path, line, func)
                    VALUES (NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    self.env.uid, 'server', self.env.cr.dbname, 
                    'res.company', 'INFO', 
                    f"Writing coordinates: lat={lat}, lng={lng}", 
                    'res_company.py', 50, '_log_coordinate_values'
                ))
            except Exception as e:
                _logger.error(f"Error writing to ir_logging: {e}") 