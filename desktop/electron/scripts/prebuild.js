#!/usr/bin/env node
// Thia-Lite Electron Prebuild Script
// Copies the Python backend binary to the Electron build resources

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const projectRoot = path.resolve(__dirname, '..', '..', '..'); // /home/opc/thia-lite
const electronDir = path.resolve(__dirname, '..'); // /home/opc/thia-lite/desktop/electron
const binDir = path.join(electronDir, 'bin');

console.log('Thia-Lite Electron Prebuild');
console.log('============================');

// Create bin directory
if (!fs.existsSync(binDir)) {
  fs.mkdirSync(binDir, { recursive: true });
  console.log('✓ Created bin directory');
} else {
  console.log('✓ bin directory exists');
}

// Determine binary name based on platform
const isWin = process.platform === 'win32';
const binName = isWin ? 'thia-lite.exe' : 'thia-lite';

// Check if backend already exists in dist
const distPath = path.join(projectRoot, 'dist', binName);

if (fs.existsSync(distPath)) {
  // Copy from dist
  const targetPath = path.join(binDir, binName);
  fs.copyFileSync(distPath, targetPath);
  console.log(`✓ Copied backend from ${distPath}`);
} else {
  // Build the backend first
  console.log('Backend binary not found in dist/, building...');
  try {
    execSync('pip install -e .', { cwd: projectRoot, stdio: 'inherit' });
    console.log('✓ Built Python backend');
  } catch (e) {
    console.error('✗ Failed to build backend:', e.message);
    process.exit(1);
  }

  // Try copying again after build
  if (fs.existsSync(distPath)) {
    const targetPath = path.join(binDir, binName);
    fs.copyFileSync(distPath, targetPath);
    console.log(`✓ Copied backend from ${distPath}`);
  } else {
    console.error('✗ Backend binary still not found after build');
    console.error('  Expected at:', distPath);
    process.exit(1);
  }
}

// Make executable on Unix
if (!isWin) {
  const targetPath = path.join(binDir, binName);
  fs.chmodSync(targetPath, '755');
  console.log('✓ Made backend executable');
}

console.log('\nPrebuild complete!');
