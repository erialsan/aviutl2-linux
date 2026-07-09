use serde::Serialize;
use std::path::PathBuf;
use tauri::Manager;
#[derive(Serialize)]
pub struct SystemInfo {
    pub os: String,
    pub kernel: String,
    pub aviutl_root: Option<String>,
    pub aviutl_exe_exists: bool,
    pub wine_prefix: Option<String>,
    pub wine_prefix_exists: bool,
    pub catalog_dir: String,
    pub installed_count: usize,
}

#[tauri::command]
pub fn get_system_info(app: tauri::AppHandle) -> SystemInfo {
    let os = std::env::consts::OS.to_string();
    let kernel = std::fs::read_to_string("/proc/version")
        .unwrap_or_else(|_| "Linux".to_string())
        .trim()
        .to_string();

    let aviutl_root = detect_aviutl_root();
    let aviutl_exe_exists = aviutl_root
        .as_ref()
        .map(|r| r.join("aviutl2.exe").exists())
        .unwrap_or(false);

    let wine_prefix = detect_wine_prefix();
    let wine_prefix_exists = wine_prefix.as_ref().map(|p| p.exists()).unwrap_or(false);

    let catalog_dir = app.path().app_config_dir()
        .map(|d| d.join("catalog").to_string_lossy().to_string())
        .unwrap_or_else(|_| "?".to_string());

    let installed_count = app.path().app_config_dir()
        .map(|d| d.join("installed.json"))
        .ok()
        .and_then(|p| std::fs::read_to_string(p).ok())
        .and_then(|s| serde_json::from_str::<serde_json::Value>(&s).ok())
        .and_then(|v| v.as_object().map(|o| o.len()))
        .unwrap_or(0);

    SystemInfo {
        os,
        kernel,
        aviutl_root: aviutl_root.map(|p| p.to_string_lossy().to_string()),
        aviutl_exe_exists,
        wine_prefix: wine_prefix.map(|p| p.to_string_lossy().to_string()),
        wine_prefix_exists,
        catalog_dir,
        installed_count,
    }
}

fn detect_aviutl_root() -> Option<PathBuf> {
    if let Ok(env) = std::env::var("AVIUTL2_ROOT") {
        let p = PathBuf::from(&env);
        if p.exists() { return Some(p); }
    }
    if let Ok(exe) = std::env::current_exe() {
        for ancestor in exe.ancestors() {
            if ancestor.join("launch-ge.sh").exists() || ancestor.join("aviutl2.exe").exists() {
                return Some(ancestor.to_path_buf());
            }
        }
    }
    if let Some(prefix) = detect_wine_prefix() {
        for c in &[
            prefix.join("drive_c/Program Files/AviUtl2"),
            prefix.join("drive_c/ProgramData/aviutl2"),
        ] {
            if c.exists() && c.join("aviutl2.exe").exists() {
                return Some(c.clone());
            }
        }
    }
    None
}

fn detect_wine_prefix() -> Option<PathBuf> {
    if let Ok(env) = std::env::var("WINEPREFIX") {
        return Some(PathBuf::from(&env));
    }
    if let Ok(exe) = std::env::current_exe() {
        for ancestor in exe.ancestors() {
            let pfx = ancestor.join("pfx-ge").join("pfx");
            if pfx.exists() { return Some(pfx); }
        }
    }
    None
}
