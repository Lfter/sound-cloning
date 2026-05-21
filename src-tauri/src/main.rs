#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    // Tauri hosts the Vite-built React app and handles native window lifecycle.
    tauri::Builder::default()
        .run(tauri::generate_context!())
        .expect("error while running Voice Patch Studio");
}
