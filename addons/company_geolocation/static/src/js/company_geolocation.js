/** @odoo-module **/

import { registry } from "@web/core/registry";
import { GeoLocationMap } from "geolocation_map_widget/static/src/js/geolocation_map";
import { patch } from "@web/core/utils/patch";

// Extend the GeoLocationMap class to add company-specific functionality if needed
patch(GeoLocationMap.prototype, {
    // For now, we don't need to override any functionality as the main widget handles all we need
}); 