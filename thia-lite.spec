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

a = Analysis(
    ['thia_lite/__main__.py'],
    pathex=[],
    binaries=[('.venv/lib64/python3.9/site-packages/sqlite_vec/vec0.so', 'sqlite_vec')],
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
