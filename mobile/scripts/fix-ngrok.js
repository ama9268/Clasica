#!/usr/bin/env node
const https = require('https');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

if (process.platform !== 'win32') {
  process.exit(0);
}

const TARGET_BIN = path.join(
  __dirname, '..', 'node_modules', '@expo', 'ngrok-bin-win32-x64', 'ngrok.exe'
);

// Skip if already v3+
if (fs.existsSync(TARGET_BIN)) {
  try {
    const out = execSync(`"${TARGET_BIN}" --version`).toString();
    const match = out.match(/ngrok version (\d+)/);
    if (match && parseInt(match[1]) >= 3) {
      console.log(`ngrok already up to date: ${out.trim()}`);
      process.exit(0);
    }
  } catch (_) {}
}

const NGROK_URL =
  'https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-windows-amd64.zip';
const TMP_ZIP = path.join(os.tmpdir(), 'ngrok-v3.zip');
const TMP_DIR = path.join(os.tmpdir(), 'ngrok-v3-extracted');

function download(url, dest) {
  return new Promise((resolve, reject) => {
    function get(u) {
      https.get(u, (res) => {
        if (res.statusCode === 301 || res.statusCode === 302) {
          return get(res.headers.location);
        }
        const file = fs.createWriteStream(dest);
        res.pipe(file);
        file.on('finish', () => { file.close(); resolve(); });
        file.on('error', reject);
      }).on('error', reject);
    }
    get(url);
  });
}

async function main() {
  console.log('Actualizando ngrok a v3+...');
  try {
    await download(NGROK_URL, TMP_ZIP);
    execSync(
      `powershell -Command "Expand-Archive -Path '${TMP_ZIP}' -DestinationPath '${TMP_DIR}' -Force"`
    );
    fs.copyFileSync(path.join(TMP_DIR, 'ngrok.exe'), TARGET_BIN);
    fs.unlinkSync(TMP_ZIP);
    fs.rmSync(TMP_DIR, { recursive: true, force: true });
    console.log('ngrok v3+ instalado correctamente.');
  } catch (err) {
    console.warn('Aviso: no se pudo actualizar ngrok:', err.message);
    console.warn('Reemplaza manualmente node_modules/@expo/ngrok-bin-win32-x64/ngrok.exe con ngrok v3+.');
  }
}

main();
