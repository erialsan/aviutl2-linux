mod commands;

use tauri::Manager;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let result = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_process::init())
        .invoke_handler(tauri::generate_handler![
            commands::detect::detect_installed,
            commands::detect::calc_hash,
            commands::install::install_package,
            commands::install::remove_package,
            commands::system::get_system_info,
        ])
        .setup(|app| {
            if let Ok(dir) = app.path().app_config_dir() {
                let _ = std::fs::create_dir_all(dir.join("catalog"));
            }
            Ok(())
        })
        .run(tauri::generate_context!());

    if let Err(e) = result {
        eprintln!("[catalog] Error: {}", e);
    }
}
