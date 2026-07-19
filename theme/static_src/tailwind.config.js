/**
 * This is a minimal config.
 *
 * If you need the full config, get it from here:
 * https://unpkg.com/browse/tailwindcss@latest/stubs/defaultConfig.stub.js
 */

const { default: daisyui } = require('daisyui');

module.exports = {
    content: [
        /**
         * HTML. Paths to Django template files that will contain Tailwind CSS classes.
         */

        /* Templates within theme app (<tailwind_app_name>/templates), e.g. base.html. */
        '../templates/**/*.html',

        /*
         * Main templates directory of the project (BASE_DIR/templates).
         */
        '../../templates/**/*.html',

        /* * KHUSUS: Mengarahkan langsung ke folder app cv_sorter kamu 
         * Ini memastikan Tailwind membaca file di folder ini.
         */
        '../../cv_sorter/templates/**/*.html',

        /*
         * Templates in other django apps (Generic pattern)
         */
        '../../**/templates/**/*.html',
    ],
    theme: {
        extend: {},
    },
    plugins: [
        /**
         * PENTING: Saya menonaktifkan (comment) @tailwindcss/forms
         * karena plugin ini sering BENTROK dengan DaisyUI.
         * Jika ini aktif, input field kamu akan terlihat polos/rusak.
         */
        // require('@tailwindcss/forms'), 
        
        require('@tailwindcss/typography'),
        require('@tailwindcss/aspect-ratio'),
        require('daisyui'),
    ],
    daisyui: {
        themes: ["light", "dark", "cupcake"],
    },
}