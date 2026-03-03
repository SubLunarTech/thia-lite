# -*- mode: python ; coding: utf-8 -*-

hidden_imports = [
    'pyswisseph',
    'swisseph',
    'sqlite_vec',
    'sqlite_vec._sqlite_vec',
    'nest_asyncio',
    'pydantic',
    'pydantic_settings',
    'textual',
    'websockets',
    'timezonefinder',
]

import os
import sqlite_vec

# Find sqlite_vec binary dynamically
sqlite_vec_dir = os.path.dirname(sqlite_vec.__file__)
sqlite_vec_bin = None
for f in os.listdir(sqlite_vec_dir):
    if f.startswith('vec0') and (f.endswith('.so') or f.endswith('.dll') or f.endswith('.dylib')):
        sqlite_vec_bin = os.path.join(sqlite_vec_dir, f)
        break

added_binaries = []
if sqlite_vec_bin:
    added_binaries.append((sqlite_vec_bin, 'sqlite_vec'))

a = Analysis(
    ['thia_lite/__main__.py'],
    pathex=[],
    binaries=added_binaries,
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
