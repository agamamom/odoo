/** @odoo-module **/

// Simple module that adds a style tag to fix the sidebar behavior
// This avoids problems with patching components
(function() {
    // Create a style element
    const style = document.createElement('style');
    style.type = 'text/css';
    
    // Add our CSS rules to prevent sidebar auto-opening
    style.textContent = `
        /* Force sidebar to be hidden by default on mobile */
        @media (max-width: 767.98px) {
            .o_app_menu_sidebar {
                transform: translateX(-100%) !important;
            }
            
            /* Only show when explicitly triggered by user action */
            .o_app_menu_sidebar.o-app-menu-sidebar-enter-active,
            .o_app_menu_sidebar.o-app-menu-sidebar-enter-to {
                transform: translateX(0) !important;
            }
        }
    `;
    
    // Add the style element to the document head when DOM is ready
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
        document.head.appendChild(style);
    } else {
        document.addEventListener('DOMContentLoaded', () => {
            document.head.appendChild(style);
        });
    }
})(); 