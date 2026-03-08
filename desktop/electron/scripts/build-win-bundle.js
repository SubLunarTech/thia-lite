#!/usr/bin/env node
// Thia-Lite Windows Bundle Script
// Downloads Python embeddable, installs thia-lite, creates all-in-one package

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');
const https = require('https');

const projectRoot = path.resolve(__dirname, '..', '..', '..'); // /home/opc/thia-lite
const electronDir = path.resolve(__dirname, '..'); // /home/opc/thia-lite/desktop/electron
const bundleDir = path.join(electronDir, 'bundle');

const PYTHON_VERSION = '3.11.9';
const PYTHON_EMBED_URL = `https://www.python.org/ftp/python/${PYTHON_VERSION}/python-${PYTHON_VERSION}-embed-amd64.zip`;
const PYTHON_ZIP = path.join(bundleDir, 'python.zip');
const PYTHON_DIR = path.join(bundleDir, 'python');

console.log('Thia-Lite Windows Bundle Creator');
console.log('==================================\n');

async function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    let downloadedBytes = 0;

    https.get(url, (response) => {
      if (response.statusCode !== 200) {
        reject(new Error(`Failed to download: ${response.statusCode}`));
        return;
      }

      const totalBytes = parseInt(response.headers['content-length'], 10);

      response.on('data', (chunk) => {
        downloadedBytes += chunk.length;
        if (totalBytes) {
          const percent = Math.round((downloadedBytes / totalBytes) * 100);
          process.stdout.write(`\rDownloading Python: ${percent}%`);
        }
      });

      response.pipe(file);

      file.on('finish', () => {
        file.close();
        console.log('\n✓ Download complete');
        resolve();
      });
    }).on('error', (err) => {
      fs.unlink(dest, () => { });
      reject(err);
    });
  });
}

async function extractZip(zipPath, destDir) {
  console.log('Extracting Python...');
  const decompress = require('decompress');
  await decompress(zipPath, destDir);
  console.log('✓ Python extracted');
}

function setupPythonPath(pythonDir) {
  console.log('Configuring Python...');

  // Modify python311._pth to include site-packages
  const pthFile = path.join(pythonDir, 'python311._pth');
  if (fs.existsSync(pthFile)) {
    let content = fs.readFileSync(pthFile, 'utf8');
    // Uncomment import site
    content = content.replace('# import site', 'import site');
    // Add Lib/site-packages to path
    content = content + '\nLib/site-packages\n';
    fs.writeFileSync(pthFile, content);
  }

  console.log('✓ Python configured');
}

async function installThiaLite(pythonDir, projectRoot) {
  console.log('Installing thia-lite into bundled Python...');

  const pythonExe = path.join(pythonDir, 'python.exe');
  const getPy = path.join(pythonDir, 'get-pip.py');

  // Download get-pip.py if not exists
  if (!fs.existsSync(getPy)) {
    console.log('Downloading get-pip.py...');
    await downloadFile('https://bootstrap.pypa.io/get-pip.py', getPy);
  }

  // Install pip
  console.log('Installing pip...');
  execSync(`"${pythonExe}" "${getPy}" --no-warn-script-location`, { stdio: 'inherit' });

  // Install thia-lite
  console.log('Installing thia-lite...');
  execSync(`"${pythonExe}" -m pip install --no-warn-script-location "${projectRoot}"`, {
    stdio: 'inherit',
    env: { ...process.env, PYTHONPATH: path.join(pythonDir, 'Lib', 'site-packages') }
  });

  console.log('✓ thia-lite installed');
}

async function main() {
  try {
    // Clean and create bundle directory
    if (fs.existsSync(bundleDir)) {
      fs.rmSync(bundleDir, { recursive: true, force: true });
    }
    fs.mkdirSync(bundleDir, { recursive: true });
    fs.mkdirSync(PYTHON_DIR, { recursive: true });

    // Download Python embeddable
    if (!fs.existsSync(PYTHON_ZIP)) {
      console.log(`Downloading Python ${PYTHON_VERSION}...`);
      await downloadFile(PYTHON_EMBED_URL, PYTHON_ZIP);
    } else {
      console.log('Python already downloaded');
    }

    // Extract Python
    await extractZip(PYTHON_ZIP, PYTHON_DIR);

    // Configure Python
    setupPythonPath(PYTHON_DIR);

    // Install thia-lite
    await installThiaLite(PYTHON_DIR, projectRoot);

    // Copy to resources dir for electron-builder
    const resourcesDir = path.join(electronDir, 'resources');
    if (fs.existsSync(resourcesDir)) {
      fs.rmSync(resourcesDir, { recursive: true, force: true });
    }
    fs.mkdirSync(resourcesDir, { recursive: true });

    const pythonBundleDir = path.join(resourcesDir, 'python');
    fs.cpSync(PYTHON_DIR, pythonBundleDir, { recursive: true });

    console.log('\n✓ Bundle ready at:', resourcesDir);
    console.log('\nNow run: npm run build:win');

  } catch (err) {
    console.error('\n✗ Error:', err.message);
    process.exit(1);
  }
}

main();
