#!/usr/bin/env node
// Thia-Lite Electron Prebuild Script
// Copies the Python backend binary to the Electron build resources

const fs = require('fs');
const path = require('path');

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
  // Backend binary not found - this is okay for Electron-only builds
  // The full release workflow builds the CLI first
  console.warn('⚠ Backend binary not found in dist/');
  console.warn('  This is expected for Electron-only builds.');
  console.warn('  The full release workflow includes the CLI backend.');
  // Don't fail - continue without the bundled binary
}

// Make executable on Unix
if (!isWin) {
  const targetPath = path.join(binDir, binName);
  fs.chmodSync(targetPath, '755');
  console.log('✓ Made backend executable');
}

console.log('\nPrebuild complete!');
