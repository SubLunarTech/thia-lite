#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

def check_tauri_config():
    print("Checking Tauri configuration...")
    conf_path = Path("desktop/src-tauri/tauri.conf.json")
    if not conf_path.exists():
        print("❌ tauri.conf.json not found!")
        return False
    
    with open(conf_path) as f:
        conf = json.load(f)
    
    # Check icons
    icon_dir = Path("desktop/src-tauri/icons")
    for icon_rel_path in conf["tauri"]["bundle"]["icon"]:
        icon_path = (conf_path.parent / icon_rel_path).resolve()
        if not icon_path.exists():
            print(f"❌ Missing icon: {icon_rel_path} (expected at {icon_path})")
            return False
    
    # Check distDir
    # distDir is relative to the tauri.conf.json file
    dist_dir = (conf_path.parent / conf["build"]["distDir"]).resolve()
    if not dist_dir.exists():
        print(f"❌ distDir not found: {dist_dir}")
        return False
    
    print("✅ Tauri configuration looks good.")
    return True

def check_package_versions():
    print("Checking package versions...")
    init_path = Path("thia_lite/__init__.py")
    if not init_path.exists():
        return False
    
    # Extract version from __init__.py
    version = None
    with open(init_path) as f:
        for line in f:
            if "__version__" in line:
                version = line.split("=")[1].strip().strip('"').strip("'")
                break
    
    if not version:
        print("❌ Version not found in thia_lite/__init__.py")
        return False
    
    # Check Cargo.toml
    cargo_path = Path("desktop/src-tauri/Cargo.toml")
    if cargo_path.exists():
        with open(cargo_path) as f:
            content = f.read()
            if f'version = "{version}"' not in content:
                print(f"⚠️ Warning: Cargo.toml version does not match {version}")
    
    print(f"✅ Version consistent: {version}")
    return True

if __name__ == "__main__":
    success = True
    success &= check_tauri_config()
    success &= check_package_versions()
    
    if success:
        print("\n🚀 Pre-flight check PASSED.")
        sys.exit(0)
    else:
        print("\n❌ Pre-flight check FAILED.")
        sys.exit(1)
