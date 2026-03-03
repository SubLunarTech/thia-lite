//! Thia-Lite Desktop — Tauri Backend
//! Launches the Python MCP backend as a sidecar and serves the web UI.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command;

fn main() {
    // Start the Python backend server
    let _backend = Command::new("python3")
        .args(["-m", "thia_lite", "serve", "--mode", "http", "--port", "8443"])
        .spawn()
        .ok();

    tauri::Builder::default()
        .setup(|_app| {
            println!("Thia-Lite Desktop started");
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Thia-Lite Desktop");
}
