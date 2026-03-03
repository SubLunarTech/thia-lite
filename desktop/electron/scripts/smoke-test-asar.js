const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

/**
 * Thia-Lite ASAR Smoke Test
 * Verifies that critical "invisible" dependencies are actually bundled in the production ASAR
 */

const CRITICAL_FILES = [
    'node_modules/call-bind-apply-helpers/index.js',
    'node_modules/call-bind/index.js',
    'node_modules/get-intrinsic/index.js',
    'node_modules/decompress/index.js'
];

function run() {
    const asarPath = path.join(__dirname, '../dist/linux-unpacked/resources/app.asar');

    if (!fs.existsSync(asarPath)) {
        console.error(`❌ ASAR not found at ${asarPath}. Run "npm run build" first.`);
        process.exit(1);
    }

    console.log(`🔍 Auditing ASAR: ${asarPath}`);

    try {
        const list = execSync(`npx asar list ${asarPath}`).toString();
        const missing = [];

        for (const file of CRITICAL_FILES) {
            if (!list.includes(file)) {
                missing.push(file);
            }
        }

        if (missing.length > 0) {
            console.error('❌ SMOKE TEST FAILED: The following critical files are missing from the bundle:');
            missing.forEach(f => console.error(`   - ${f}`));
            process.exit(1);
        }

        console.log('✅ SMOKE TEST PASSED: All critical dependencies are present in the bundle.');
    } catch (err) {
        console.error('❌ Error during ASAR audit:', err.message);
        process.exit(1);
    }
}

run();
