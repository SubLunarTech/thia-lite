# -*- mode: python ; coding: utf-8 -*-

hidden_imports = [
    'pyswisseph',
    'swisseph',
    'sqlite_vec',
    'sqlite_vec._sqlite_vec',
    'thia_lite.rules',
    'thia_lite.llm.rlm_engine',
    'thia_lite.llm.conversation',
    'thia_lite.llm.tool_executor',
]

import os
import sys # Added for sys.version
# import sqlite_vec # Removed as it's not used in the new binary discovery

def find_file(name, path):
    for root, dirs, files in os.walk(path):
        for file in files:
            if name in file:
                return os.path.join(root, file)
    return None

# Find sqlite-vec binary
venv_path = os.environ.get('VIRTUAL_ENV', os.path.join(os.getcwd(), '.venv'))
site_packages = os.path.join(venv_path, 'lib', 'python' + sys.version[:3], 'site-packages')
if not os.path.exists(site_packages):
    site_packages = os.path.join(venv_path, 'Lib', 'site-packages') # Windows

sqlite_vec_bin = find_file('sqlite_vec', site_packages)
if not sqlite_vec_bin:
    sqlite_vec_bin = find_file('sqlite_vec', '.')

# Find swisseph binary
swisseph_bin = find_file('swisseph', site_packages)
if not swisseph_bin:
    swisseph_bin = find_file('swisseph', '.')

binaries = []
if sqlite_vec_bin:
    binaries.append((sqlite_vec_bin, '.'))
if swisseph_bin:
    binaries.append((swisseph_bin, '.'))

print(f"Bundling binaries: {binaries}")

a = Analysis(
    ['thia_lite/__main__.py'],
    pathex=[],
    binaries=binaries, # Changed from added_binaries to binaries
    datas=[('thia_lite/rules', 'thia_lite/rules')],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='thia-lite',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
