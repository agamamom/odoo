/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { CharField, charField } from "@web/views/fields/char/char_field";
import { useRef, useState, onMounted, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { browser } from "@web/core/browser/browser";
import { session } from "@web/session";

/**
 * GeoLocationMap class extends CharField to provide a map with geolocation features.
 */
export class GeoLocationMap extends CharField {
    /**
     * Sets up the component by initializing services, references, and state.
     */
    setup() {
        super.setup();
        this.orm = useService('orm');
        this.notification = useService('notification');
        this.mapContainerRef = useRef('mapContainer');
        this.state = useState({
            latitude: 51.505,
            longitude: -0.09,
            address: '',
            currentMarker: null,
            map: null,
            lastFormAddress: '', // Store last address to prevent duplicate lookups
            isAddressProcessing: false // Flag to prevent multiple simultaneous geocoding
        });
        
        onMounted(() => {
            this._initializeMap();
            // Wait for map to fully initialize before trying to update from address
            setTimeout(() => {
                this._setupAddressListeners();
                // Chỉ tự động cập nhật từ địa chỉ khi chưa có tọa độ
                const hasValidCoordinates = this._hasValidCoordinates();
                if (!hasValidCoordinates) {
                    this._updateFromCompanyAddress();
                }
            }, 500);
        });
    }
    
    /**
     * Kiểm tra xem đã có tọa độ hợp lệ hay chưa
     */
    _hasValidCoordinates() {
        if (!this.props.record || !this.props.record.data) return false;
        
        const recordData = this.props.record.data;
        if (!recordData.latitude || !recordData.longitude) return false;
        
        const lat = parseFloat(recordData.latitude);
        const lng = parseFloat(recordData.longitude);
        
        // Kiểm tra tọa độ có hợp lệ và khác 0
        return !isNaN(lat) && !isNaN(lng) && 
               lat !== 0 && lng !== 0 && 
               lat >= -90 && lat <= 90 && 
               lng >= -180 && lng <= 180;
    }
    
    /**
     * Handler for update from address button click
     */
    async _updateFromAddressButton() {
        console.log("Update from address button clicked");
        
        // Hiển thị thông báo đang xử lý
        this.notification.add(_t("Cập nhật bản đồ từ địa chỉ..."), {
            type: 'info',
            sticky: false,
            title: 'Đang xử lý'
        });
        
        try {
            // Thử lấy địa chỉ trực tiếp từ record data
            const recordData = this.props.record.data;
            if (!recordData) {
                this.notification.add(_t("Không tìm thấy dữ liệu địa chỉ"), {
                    type: 'warning',
                    sticky: false
                });
                return false;
            }
            
            // Lấy địa chỉ từ trường street (ưu tiên nhất)
            let addressComponents = [];
            
            // Ưu tiên địa chỉ chính (street)
            if (recordData.street) {
                addressComponents.push(recordData.street);
            }
            
            // Thêm city, state, country nếu có (thay vì street2)
            if (recordData.city) {
                addressComponents.push(recordData.city);
            }
            
            if (recordData.state_id && recordData.state_id[1]) {
                addressComponents.push(recordData.state_id[1]);
            }
            
            if (recordData.country_id && recordData.country_id[1]) {
                addressComponents.push(recordData.country_id[1]);
            }
            
            // Thêm street2 sau cùng nếu vẫn cần thêm thông tin
            if (addressComponents.length < 2 && recordData.street2) {
                addressComponents.push(recordData.street2);
            }
            
            // Nếu không có đủ thông tin, thử cách cũ
            if (addressComponents.length < 1) {
                addressComponents = await this._getAddressComponentsFromForm();
            }
            
            // Kiểm tra có địa chỉ (không tính "Việt Nam")
            const hasRealAddress = addressComponents.some(comp => 
                comp.toLowerCase() !== 'việt nam' && 
                comp.toLowerCase() !== 'vietnam'
            );
            
            if (!hasRealAddress) {
                this.notification.add(_t("Vui lòng nhập địa chỉ trước khi cập nhật bản đồ"), {
                    type: 'warning',
                    sticky: false
                });
                return false;
            }
            
            console.log("Address components:", addressComponents);
            
            // Tạo địa chỉ đầy đủ
            const fullAddress = addressComponents.join(', ');
            console.log("Full address for geocoding:", fullAddress);
            
            // Hiển thị địa chỉ đang được sử dụng
            this.notification.add(_t("Đang tìm vị trí cho: ") + fullAddress, {
                type: 'info',
                sticky: false
            });
            
            // Thực hiện geocoding
            const coordinates = await this._getLatLngFromAddress(fullAddress);
            
            if (coordinates) {
                // Cập nhật bản đồ
                this.state.latitude = coordinates.lat;
                this.state.longitude = coordinates.lng;
                
                if (this.state.map) {
                    this.state.map.setView([coordinates.lat, coordinates.lng], 15);
                    this._updateMarker(coordinates.lat, coordinates.lng);
                    
                    // Lưu tọa độ vào record
                    await this._saveCoordinates(coordinates.lat, coordinates.lng);
                    
                    this.notification.add(_t("Đã cập nhật bản đồ theo địa chỉ: ") + fullAddress, {
                        type: 'success',
                        sticky: false
                    });
                    
                    return true;
                }
            } else {
                this.notification.add(_t("Không thể tìm thấy vị trí cho địa chỉ: ") + fullAddress, {
                    type: 'warning',
                    sticky: false
                });
            }
        } catch (error) {
            console.error("Error updating from address button:", error);
            this.notification.add(_t("Không thể cập nhật bản đồ từ địa chỉ"), {
                type: 'danger',
                sticky: false
            });
        }
        
        return false;
    }
    
    /**
     * Handler for update from coordinates button click
     */
    async _updateFromCoordinatesButton() {
        console.log("Update from coordinates button clicked");
        
        try {
            // Lấy giá trị tọa độ từ record
            const recordData = this.props.record.data;
            if (!recordData) {
                this.notification.add(_t("Không tìm thấy dữ liệu tọa độ"), {
                    type: 'warning',
                    sticky: false
                });
                return false;
            }
            
            const latitude = parseFloat(recordData.latitude);
            const longitude = parseFloat(recordData.longitude);
            
            // Kiểm tra giá trị tọa độ hợp lệ
            if (isNaN(latitude) || isNaN(longitude)) {
                this.notification.add(_t("Vui lòng nhập tọa độ hợp lệ"), {
                    type: 'warning',
                    sticky: false
                });
                return false;
            }
            
            // Kiểm tra giá trị tọa độ nằm trong khoảng hợp lệ
            if (latitude < -90 || latitude > 90 || longitude < -180 || longitude > 180) {
                this.notification.add(_t("Tọa độ không hợp lệ: vĩ độ phải từ -90 đến 90, kinh độ phải từ -180 đến 180"), {
                    type: 'warning',
                    sticky: false
                });
                return false;
            }
            
            // Thông báo đang xử lý
            this.notification.add(_t("Đang cập nhật bản đồ từ tọa độ..."), {
                type: 'info',
                sticky: false,
                title: 'Đang xử lý'
            });
            
            // Cập nhật bản đồ
            this.state.latitude = latitude;
            this.state.longitude = longitude;
            
            if (this.state.map) {
                this.state.map.setView([latitude, longitude], 15);
                this._updateMarker(latitude, longitude);
                
                // Cập nhật địa chỉ từ tọa độ (reverse geocoding)
                const address = await this._getAddressFromLatLng(latitude, longitude);
                if (address) {
                    // Cập nhật giá trị location_address
                    this.props.update(address);
                }
                
                this.notification.add(_t("Đã cập nhật bản đồ theo tọa độ: ") + latitude + ", " + longitude, {
                    type: 'success',
                    sticky: false
                });
                
                return true;
            }
        } catch (error) {
            console.error("Error updating from coordinates button:", error);
            this.notification.add(_t("Không thể cập nhật bản đồ từ tọa độ"), {
                type: 'danger',
                sticky: false
            });
        }
        
        return false;
    }
    
    /**
     * Get address components from form fields directly
     */
    async _getAddressComponentsFromForm() {
        try {
            const form = this.mapContainerRef.el.closest('form');
            if (!form) {
                console.log("Form element not found");
                return [];
            }
            
            console.log("Form found:", form);
            const components = [];
            
            // Lấy giá trị trực tiếp từ record data thay vì DOM
            const recordData = this.props.record.data;
            console.log("Record data:", recordData);
            
            if (recordData.street) {
                components.push(recordData.street);
                console.log("Added street:", recordData.street);
            }
            
            if (recordData.street2) {
                components.push(recordData.street2);
                console.log("Added street2:", recordData.street2);
            }
            
            if (recordData.city) {
                components.push(recordData.city);
                console.log("Added city:", recordData.city);
            }
            
            // Lấy giá trị state và country từ many2one fields
            if (recordData.state_id && recordData.state_id[1]) {
                components.push(recordData.state_id[1]);
                console.log("Added state:", recordData.state_id[1]);
            }
            
            if (recordData.country_id && recordData.country_id[1]) {
                components.push(recordData.country_id[1]);
                console.log("Added country:", recordData.country_id[1]);
            }
            
            // Backup: thử lấy địa chỉ từ các trường trong DOM
            if (components.length === 0) {
                console.log("No address found in record data, trying DOM");
                
                // Tìm tất cả các input có giá trị
                const allInputs = form.querySelectorAll('input, select');
                console.log("Found inputs:", allInputs.length);
                
                allInputs.forEach(input => {
                    const name = input.getAttribute('name');
                    const value = input.value;
                    if (name && value && ['street', 'street2', 'city'].includes(name)) {
                        console.log(`Found input ${name} with value: ${value}`);
                        if (value.trim()) components.push(value.trim());
                    }
                });
                
                // Thử lấy giá trị từ các trường many2one
                const many2oneFields = form.querySelectorAll('.o_field_many2one input');
                many2oneFields.forEach(field => {
                    if (field.value && field.value.trim()) {
                        console.log(`Found many2one value: ${field.value}`);
                        components.push(field.value.trim());
                    }
                });
            }
            
            // Nếu vẫn không có gì, thử dùng text của label gần nhất
            if (components.length === 0) {
                // Lấy thẻ chứa địa chỉ
                const addressRows = form.querySelectorAll('tr, .o_form_label:contains("Address")');
                addressRows.forEach(row => {
                    const textContent = row.textContent.trim();
                    if (textContent && textContent.length > 3) {
                        console.log("Found address text:", textContent);
                        components.push(textContent);
                    }
                });
            }
            
            // Nếu vẫn không có gì, thử lấy text chứa địa chỉ
            if (components.length === 0) {
                // Tìm tất cả text nodes có thể chứa địa chỉ
                const addressLabels = Array.from(form.querySelectorAll('label, span, div')).filter(el => 
                    el.textContent.includes('Street') || 
                    el.textContent.includes('Address') ||
                    el.textContent.includes('City') ||
                    el.textContent.includes('State') ||
                    el.textContent.includes('Country')
                );
                
                console.log("Address labels:", addressLabels.length);
                
                // Lấy các phần tử kế bên (siblings) của các label này
                addressLabels.forEach(label => {
                    const next = label.nextElementSibling;
                    if (next && next.textContent.trim()) {
                        console.log(`Found address text near ${label.textContent}: ${next.textContent.trim()}`);
                        components.push(next.textContent.trim());
                    }
                });
            }
            
            // Nếu vẫn chưa tìm thấy, sử dụng giá trị từ trường location_address
            if (components.length === 0 && recordData.location_address) {
                console.log("Using location_address as fallback:", recordData.location_address);
                components.push(recordData.location_address);
            }
            
            // If no specific country was found, add Vietnam by default
            if (!components.some(c => 
                c.toLowerCase().includes('vietnam') || 
                c.toLowerCase().includes('việt nam'))) {
                components.push('Việt Nam');
                console.log("Added default country: Việt Nam");
            }
            
            console.log("Final address components:", components);
            return components.filter(c => c); // Filter out empty values
        } catch (error) {
            console.error("Error getting address components from form:", error);
            return [];
        }
    }
    
    /**
     * Update map from current company address fields
     * @param {boolean} force Force update even if the address hasn't changed
     */
    async _updateFromCompanyAddress(force = false) {
        try {
            if (!this.props.record || !this.props.record.data) return;
            
            const data = this.props.record.data;
            
            // Nếu đã có tọa độ hợp lệ và không phải là force update, thì không cần cập nhật từ địa chỉ
            if (!force && this._hasValidCoordinates()) {
                console.log("Skipping auto-update from address: valid coordinates already exist");
                return false;
            }
            
            const addressParts = [];
            
            // Build address string from company data
            if (data.street) addressParts.push(data.street);
            if (data.street2) addressParts.push(data.street2);
            if (data.city) addressParts.push(data.city);
            if (data.state_id && data.state_id[1]) addressParts.push(data.state_id[1]);
            if (data.zip) addressParts.push(data.zip);
            if (data.country_id && data.country_id[1]) addressParts.push(data.country_id[1]);
            
            const fullAddress = addressParts.join(', ');
            console.log("Current company address:", fullAddress);
            
            if (fullAddress && fullAddress.length > 5) {
                await this._geocodeAndUpdateMap(fullAddress, force);
                return true;
            }
            return false;
        } catch (error) {
            console.error("Error updating from company address:", error);
            return false;
        }
    }
    
    /**
     * Geocode address and update map
     * @param {string} address Address to geocode
     * @param {boolean} force Force update even if the address hasn't changed
     */
    async _geocodeAndUpdateMap(address, force = false) {
        // Prevent duplicate or simultaneous geocoding
        if (this.state.isAddressProcessing || (!force && address === this.state.lastFormAddress)) {
            return false;
        }
        
        this.state.isAddressProcessing = true;
        this.state.lastFormAddress = address;
        
        console.log(`Geocoding address: ${address}`);
        
        try {
            const coordinates = await this._getLatLngFromAddress(address);
            
            if (coordinates) {
                const { lat, lng } = coordinates;
                console.log(`Address geocoded to: ${lat}, ${lng}`);
                
                // Update state
                this.state.latitude = lat;
                this.state.longitude = lng;
                
                // Update map and marker
                if (this.state.map) {
                    this.state.map.setView([lat, lng], 13);
                    this._updateMarker(lat, lng);
                    
                    // Update form fields
                    await this._saveCoordinates(lat, lng);
                    return true;
                }
            } else {
                console.warn(`Could not geocode address: ${address}`);
                this.notification.add(_t("Không thể tìm thấy vị trí cho địa chỉ này"), {
                    type: 'warning',
                    sticky: false
                });
                return false;
            }
        } catch (error) {
            console.error("Error geocoding address:", error);
            return false;
        } finally {
            this.state.isAddressProcessing = false;
        }
    }
    
    /**
     * Setup listeners for address field changes
     */
    _setupAddressListeners() {
        try {
            // Find address fields in the form
            const addressFields = [
                'street', 'street2', 'city', 'zip', 'state_id', 'country_id'
            ];
            
            // Listen for changes in address fields
            const form = this.mapContainerRef.el.closest('form');
            if (!form) return;
            
            console.log("Setting up address field listeners");
            
            // Chỉ lắng nghe sự kiện thay đổi để cập nhật lastFormAddress
            // nhưng không tự động cập nhật tọa độ
            addressFields.forEach(field => {
                const input = form.querySelector(`[name="${field}"]`);
                if (input) {
                    console.log(`Found address field: ${field}`);
                    input.addEventListener('change', () => {
                        console.log(`Address field changed: ${field}`);
                        // Chỉ cập nhật địa chỉ hiện tại, không cập nhật tọa độ
                        setTimeout(() => {
                            this._updateCurrentAddress();
                        }, 300);
                    });
                    
                    // Also listen for blur events
                    input.addEventListener('blur', () => {
                        setTimeout(() => {
                            this._updateCurrentAddress();
                        }, 300);
                    });
                }
            });
        } catch (error) {
            console.error("Error setting up address listeners:", error);
        }
    }
    
    /**
     * Chỉ cập nhật địa chỉ hiện tại mà không cập nhật tọa độ
     */
    _updateCurrentAddress() {
        try {
            if (!this.props.record || !this.props.record.data) return;
            
            const data = this.props.record.data;
            const addressParts = [];
            
            // Build address from form fields
            if (data.street) addressParts.push(data.street);
            if (data.street2) addressParts.push(data.street2);
            if (data.city) addressParts.push(data.city);
            if (data.state_id && data.state_id[1]) addressParts.push(data.state_id[1]);
            if (data.zip) addressParts.push(data.zip);
            if (data.country_id && data.country_id[1]) addressParts.push(data.country_id[1]);
            
            const fullAddress = addressParts.join(', ');
            console.log(`Updated form address: ${fullAddress}`);
            
            // Chỉ lưu địa chỉ hiện tại mà không cập nhật tọa độ
            this.state.lastFormAddress = fullAddress;
        } catch (error) {
            console.error("Error updating current address:", error);
        }
    }
    
    /**
     * Get address from form fields and update map
     * (Không dùng phương thức này nữa vì không cần tự động cập nhật)
     */
    _getAddressFromForm() {
        try {
            if (!this.props.record || !this.props.record.data) return;
            
            const data = this.props.record.data;
            const addressParts = [];
            
            // Build address from form fields
            if (data.street) addressParts.push(data.street);
            if (data.street2) addressParts.push(data.street2);
            if (data.city) addressParts.push(data.city);
            if (data.state_id && data.state_id[1]) addressParts.push(data.state_id[1]);
            if (data.zip) addressParts.push(data.zip);
            if (data.country_id && data.country_id[1]) addressParts.push(data.country_id[1]);
            
            const fullAddress = addressParts.join(', ');
            console.log(`Form address: ${fullAddress}`);
            
            // Chỉ lưu địa chỉ hiện tại mà không cập nhật bản đồ
            this.state.lastFormAddress = fullAddress;
            
            // Không còn tự động cập nhật bản đồ tại đây
            // if (fullAddress && fullAddress.length > 5) {
            //     this._geocodeAndUpdateMap(fullAddress);
            // }
        } catch (error) {
            console.error("Error getting address from form:", error);
        }
    }
    
    /**
     * Initializes the Leaflet map and sets up event handlers.
     */
    async _initializeMap() {
        console.log("Initializing map...");
        const mapContainer = this.mapContainerRef.el;
        if (!mapContainer) {
            console.error('Map container not found.');
            return;
        }
        
        try {
            // Check if we have coordinates in the record
            if (this.props.record && this.props.record.data) {
                const recordData = this.props.record.data;
                console.log("Record data:", recordData);
                
                if (recordData.latitude && recordData.longitude) {
                    const lat = parseFloat(recordData.latitude);
                    const lng = parseFloat(recordData.longitude);
                    
                    // Only use if they are valid non-zero values
                    if (lat !== 0 && lng !== 0 && !isNaN(lat) && !isNaN(lng)) {
                        this.state.latitude = lat;
                        this.state.longitude = lng;
                        console.log(`Using coordinates from record: ${lat}, ${lng}`);
                    }
                }
            }

            // Initialize the map with the coordinates (either default or from record)
            const map = L.map(mapContainer, {
                zoomControl: true, 
                zoom: 13  // Increased zoom level
            }).setView([this.state.latitude, this.state.longitude], 13);
            
            this.state.map = map;
            
            // Add tile layer
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { 
                maxZoom: 19 
            }).addTo(map);
            
            // Add initial marker after map is fully loaded
            map.whenReady(() => {
                // Add marker only when map is ready to avoid animation issues
                this.state.currentMarker = L.marker([this.state.latitude, this.state.longitude])
                    .addTo(map);
                    
                // Wait a brief moment to ensure map is stable before opening popup
                setTimeout(() => {
                    if (this.state.currentMarker) {
                        this.state.currentMarker.bindPopup('Selected Location').openPopup();
                    }
                }, 100);
            });
                
            // Simple click handler - for debugging
            console.log("Setting up map click handler");
            map.on('click', (event) => {
                console.log("Map clicked at:", event.latlng);
                this._handleMapClick(event);
            });
            
            // Make map redraw when visible (fixes initial render issues)
            setTimeout(() => {
                if (this.state.map) {
                    this.state.map.invalidateSize();
                }
            }, 500);
            
        } catch (error) {
            console.error("Error initializing map:", error);
        }
    }
    
    /**
     * Handle map click events
     */
    async _handleMapClick(event) {
        try {
            const { lat, lng } = event.latlng;
            console.log(`Clicked at ${lat}, ${lng}`);
            
            // 1. Update state
            this.state.latitude = lat;
            this.state.longitude = lng;
            
            // 2. Get address for the location (nhưng không cập nhật vào trường location_address)
            const address = await this._getAddressFromLatLng(lat, lng);
            console.log("Got address:", address);
            
            // 3. Xóa street2 để tránh xung đột địa chỉ
            try {
                if (this.props.record && this.props.record.data && this.props.record.data.street2) {
                    // Xóa street2 để tránh xung đột
                    await this.props.record.update({
                        'street2': ''
                    });
                    console.log("Cleared street2 to avoid address conflict");
                }
            } catch (err) {
                console.log("Could not clear street2:", err);
            }
            
            // 4. Không cập nhật location_address vì nó sẽ được tính toán tự động
            // Trường location_address đã được định nghĩa là computed field
            
            // 5. Update map marker
            this._updateMarker(lat, lng);
            
            // 6. Update coordinates in database
            this._saveCoordinates(lat, lng);
            
            // 7. Hiển thị thông báo
            this.notification.add(_t("Đã cập nhật vị trí thành công. Tọa độ: ") + lat.toFixed(6) + ", " + lng.toFixed(6), {
                type: 'success',
                sticky: false
            });
            
        } catch (error) {
            console.error("Error handling map click:", error);
        }
    }
    
    /**
     * Update marker on map
     */
    _updateMarker(lat, lng) {
        try {
            if (!this.state.map) return;
            
            // Remove existing marker
            if (this.state.currentMarker) {
                this.state.map.removeLayer(this.state.currentMarker);
            }
            
            // Add new marker
            this.state.currentMarker = L.marker([lat, lng])
                .addTo(this.state.map);
                
            // Only bind and open popup when the map is not in an animated state
            // This fixes the "_latLngToNewLayerPoint" error during zoom animations
            if (!this.state.map._animatingZoom) {
                this.state.currentMarker.bindPopup('Selected Location').openPopup();
            } else {
                // If map is animating, wait for the animation to finish before showing popup
                this.state.map.once('zoomend', () => {
                    if (this.state.currentMarker) {
                        this.state.currentMarker.bindPopup('Selected Location').openPopup();
                    }
                });
            }
                
            console.log("Marker updated");
        } catch (error) {
            console.error("Error updating marker:", error);
        }
    }
    
    /**
     * Save coordinates to database
     */
    async _saveCoordinates(lat, lng) {
        try {
            const record = this.props.record;
            if (!record) {
                console.warn("No record available");
                return;
            }
            
            console.log("Updating record:", record);
            
            // 1. Update form model - using silent mode to prevent reload
            await record.update({
                'latitude': lat,
                'longitude': lng
            }, { silent: true });
            
            // 2. Update UI elements
            const latField = document.querySelector('input[name="latitude"]');
            const lngField = document.querySelector('input[name="longitude"]');
            
            if (latField) latField.value = lat;
            if (lngField) lngField.value = lng;
            
            // 3. Update database if we have record ID
            if (record.resId) {
                console.log(`Updating company ${record.resId} coordinates to ${lat}, ${lng}`);
                
                try {
                    // Try direct database update to avoid form reload
                    await this.orm.call(
                        'res.company',
                        'update_coordinates',
                        [[record.resId], lat, lng]
                    );
                } catch (err) {
                    console.error("Error with direct update, falling back to write:", err);
                    // Fallback to standard write
                    await this.orm.write('res.company', [record.resId], {
                        latitude: lat,
                        longitude: lng
                    });
                }
            }
        } catch (error) {
            console.error("Error saving coordinates:", error);
            this.notification.add(_t("Error updating coordinates"), {
                type: 'danger',
            });
        }
    }
    
    /**
     * Get address from coordinates using Nominatim API
     */
    async _getAddressFromLatLng(latitude, longitude) {
        try {
            const response = await fetch(
                `https://nominatim.openstreetmap.org/reverse?lat=${latitude}&lon=${longitude}&format=json`,
                { headers: { 'Accept-Language': 'en' } }
            );
            
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            
            const data = await response.json();
            console.log("Nominatim response:", data);
            
            if (data.display_name) {
                return data.display_name;
            }
            
            // Fallback to building address from components
            const addressParts = [];
            if (data.address) {
                const addr = data.address;
                const parts = [
                    addr.road, 
                    addr.suburb, 
                    addr.city || addr.town || addr.village,
                    addr.county,
                    addr.state,
                    addr.country
                ];
                
                for (const part of parts) {
                    if (part) addressParts.push(part);
                }
            }
            
            return addressParts.join(', ');
        } catch (error) {
            console.error('Error fetching address:', error);
            return null;
        }
    }
    
    /**
     * Get coordinates from address using Nominatim API
     */
    async _getLatLngFromAddress(address) {
        try {
            console.log("Original address for geocoding:", address);
            
            // Xử lý đặc biệt cho địa chỉ Việt Nam
            let searchAddress = address;
            
            // Đảm bảo có "Việt Nam" hoặc "Vietnam" trong địa chỉ
            if (!address.toLowerCase().includes('vietnam') && 
                !address.toLowerCase().includes('việt nam')) {
                searchAddress += ', Việt Nam';
            }
            
            // Xóa các ký tự đặc biệt có thể gây lỗi
            searchAddress = searchAddress.replace(/['"\\]/g, '');
            
            // Thêm tên thành phố lớn nếu địa chỉ quá ngắn
            if (searchAddress.split(',').length < 3 && !searchAddress.toLowerCase().includes('hà nội') && 
                !searchAddress.toLowerCase().includes('ho chi minh') && !searchAddress.toLowerCase().includes('hồ chí minh')) {
                
                // Kiểm tra nếu địa chỉ có chứa các từ khóa của Hà Nội
                if (searchAddress.toLowerCase().includes('cầu giấy') || 
                    searchAddress.toLowerCase().includes('đống đa') || 
                    searchAddress.toLowerCase().includes('hoàn kiếm') ||
                    searchAddress.toLowerCase().includes('ba đình') ||
                    searchAddress.toLowerCase().includes('hai bà trưng')) {
                    searchAddress += ', Hà Nội';
                }
                // Kiểm tra nếu địa chỉ có chứa các từ khóa của TP HCM
                else if (searchAddress.toLowerCase().includes('quận 1') || 
                        searchAddress.toLowerCase().includes('quận 2') ||
                        searchAddress.toLowerCase().includes('quận 3') ||
                        searchAddress.toLowerCase().includes('quận 7') ||
                        searchAddress.toLowerCase().includes('thủ đức') ||
                        searchAddress.toLowerCase().includes('bình thạnh')) {
                    searchAddress += ', Hồ Chí Minh';
                }
            }
            
            console.log("Modified address for geocoding:", searchAddress);
            const encodedAddress = encodeURIComponent(searchAddress);
            
            // Thử phương pháp 1: Sử dụng Nominatim với cờ quốc gia
            const response = await fetch(
                `https://nominatim.openstreetmap.org/search?format=json&q=${encodedAddress}&limit=1&countrycodes=vn`,
                { 
                    headers: { 
                        'Accept-Language': 'vi,en',
                        'User-Agent': 'Odoo Geolocation Widget'
                    } 
                }
            );
            
            if (!response.ok) {
                throw new Error(`HTTP error: ${response.status}`);
            }
            
            const data = await response.json();
            console.log("Geocoding response:", data);
            
            if (data.length > 0) {
                const result = {
                    lat: parseFloat(data[0].lat),
                    lng: parseFloat(data[0].lon)
                };
                console.log("Found coordinates:", result);
                return result;
            }
            
            // Phương pháp 2: Nếu không tìm thấy, thử lại với phần quan trọng nhất của địa chỉ
            const addressParts = searchAddress.split(',').map(part => part.trim());
            if (addressParts.length > 2) {
                // Thử với phần địa chỉ đầu tiên + thành phố/quốc gia
                const simplifiedAddress = `${addressParts[0]}, ${addressParts[addressParts.length-2]}, ${addressParts[addressParts.length-1]}`;
                console.log(`Trying simplified address: ${simplifiedAddress}`);
                
                const secondResponse = await fetch(
                    `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(simplifiedAddress)}&limit=1&countrycodes=vn`,
                    { 
                        headers: { 
                            'Accept-Language': 'vi,en',
                            'User-Agent': 'Odoo Geolocation Widget'
                        } 
                    }
                );
                
                if (secondResponse.ok) {
                    const secondData = await secondResponse.json();
                    console.log("Second geocoding response:", secondData);
                    
                    if (secondData.length > 0) {
                        const result = {
                            lat: parseFloat(secondData[0].lat),
                            lng: parseFloat(secondData[0].lon)
                        };
                        console.log("Found coordinates with method 2:", result);
                        return result;
                    }
                }
            }
            
            // Phương pháp 3: Thử với thành phố và quốc gia
            if (addressParts.length >= 2) {
                // Lấy 2 phần cuối (thường là thành phố và quốc gia)
                const cityCountry = `${addressParts[addressParts.length-2]}, ${addressParts[addressParts.length-1]}`;
                console.log(`Trying city and country only: ${cityCountry}`);
                
                const thirdResponse = await fetch(
                    `https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(cityCountry)}&limit=1&countrycodes=vn`,
                    { 
                        headers: { 
                            'Accept-Language': 'vi,en',
                            'User-Agent': 'Odoo Geolocation Widget'
                        } 
                    }
                );
                
                if (thirdResponse.ok) {
                    const thirdData = await thirdResponse.json();
                    console.log("Third geocoding response:", thirdData);
                    
                    if (thirdData.length > 0) {
                        const result = {
                            lat: parseFloat(thirdData[0].lat),
                            lng: parseFloat(thirdData[0].lon)
                        };
                        console.log("Found coordinates with method 3:", result);
                        return result;
                    }
                }
            }
            
            // Phương pháp 4: Hardcoded fallbacks cho các thành phố lớn của Việt Nam
            const lowerAddress = searchAddress.toLowerCase();
            if (lowerAddress.includes('hà nội') || lowerAddress.includes('ha noi')) {
                console.log("Using fallback coordinates for Hanoi");
                return { lat: 21.0285, lng: 105.8542 };
            }
            if (lowerAddress.includes('hồ chí minh') || lowerAddress.includes('ho chi minh') || 
                lowerAddress.includes('sài gòn') || lowerAddress.includes('sai gon') || 
                lowerAddress.includes('tphcm')) {
                console.log("Using fallback coordinates for Ho Chi Minh City");
                return { lat: 10.8231, lng: 106.6297 };
            }
            if (lowerAddress.includes('đà nẵng') || lowerAddress.includes('da nang')) {
                console.log("Using fallback coordinates for Da Nang");
                return { lat: 16.0544, lng: 108.2022 };
            }
            
            console.warn("Could not geocode address:", address);
            return null;
        } catch (error) {
            console.error('Error geocoding address:', error);
            return null;
        }
    }
    
    /**
     * Opens Google Maps with the current location
     */
    async _OpenMapview() {
        const { longitude, latitude } = this.state;
        if (latitude && longitude) {
            window.open(`https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`, '_blank');
        }
    }
}

// Set template
GeoLocationMap.template = 'geolocation_map_widget.GeoLocation';

// Register the field
export const geoLocationMap = {
    ...charField,
    component: GeoLocationMap,
    displayName: _t("GeoLocation Map Viewer"),
};

registry.category("fields").add("geolocation_map", geoLocationMap);
