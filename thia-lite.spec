# -*- mode: python ; coding: utf-8 -*-

hidden_imports = [
    # Core
    'pyswisseph',
    'swisseph',
    'sqlite_vec',
    'sqlite_vec._sqlite_vec',

    # Pydantic (critical for config)
    'pydantic',
    'pydantic_core',
    'pydantic_core.core_schema',
    'pydantic_settings',
    'pydantic_settings.base',
    'pydantic_settings.sources',
    'annotated_types',

    # LLM/HTTP
    'httpx',
    'httpx._transports.default',
    'httpx._client',
    'nest_asyncio',
    'anyio',
    'anyio._backends._asyncio',
    'anyio.streams',

    # CLI/TUI
    'typer',
    'typer.core',
    'rich',
    'rich.markdown',
    'rich.console',
    'rich.syntax',
    'rich.progress',
    'textual',
    'textual.app',
    'textual.widgets',
    'textual.reactive',

    # MCP/WebSockets
    'websockets',
    'websockets.server',
    'websockets.client',
    'websockets.legacy',

    # Utilities
    'timezonefinder',
    'timezonefinderL',

    # TOML parsing (Python < 3.11)
    'tomli',
    'tomllib',

    # Windows-specific
    'win32api',
    'win32file',
    'pywintypes',

    # thia_lite modules
    'thia_lite.rules',
    'thia_lite.llm.rlm_engine',
    'thia_lite.llm.conversation',
    'thia_lite.llm.tool_executor',
    'thia_lite.llm.client',
    'thia_lite.llm.simple',
    'thia_lite.config',
    'thia_lite.db',
    'thia_lite.ipc_server',
    'thia_lite.mcp.server',
    'thia_lite.mcp.client',
    'thia_lite.mcp.llm_tool',

    # Engines
    'thia_lite.engines.astrology',
    'thia_lite.engines.autonomy',
    'thia_lite.engines.ported_tools',
    'thia_lite.engines.verification',
    'thia_lite.engines.chart_renderer',
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

from PyInstaller.utils.hooks import collect_all

datas = [('thia_lite/rules', 'thia_lite/rules')]
binaries = binaries

# Robust collection of thia_lite package
tmp_ret = collect_all('thia_lite')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hidden_imports += tmp_ret[2]

a = Analysis(
    ['thia_lite/__main__.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
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
    upx=False,  # Disabled - can cause crashes on Windows with certain DLLs
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
