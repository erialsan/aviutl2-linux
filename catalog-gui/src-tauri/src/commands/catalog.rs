use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::Manager;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CatalogPackage {
    pub id: String,
    pub name: String,
    #[serde(rename = "type")]
    pub pkg_type: Option<String>,
    pub author: Option<String>,
    pub summary: Option<String>,
    pub description: Option<String>,
    pub tags: Option<Vec<String>>,
    #[serde(rename = "latest-version")]
    pub latest_version: Option<String>,
    pub release_date: Option<String>,
    pub popularity: Option<i64>,
    pub trend: Option<i64>,
    pub niconi_comons_id: Option<String>,
    pub installer: Option<serde_json::Value>,
    pub version: Option<Vec<CatalogVersion>>,
    pub dependencies: Option<Vec<String>>,
    pub images: Option<Vec<serde_json::Value>>,
    pub licenses: Option<Vec<serde_json::Value>>,
    pub repo_url: Option<String>,
    pub package_page_url: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CatalogVersion {
    pub version: String,
    pub release_date: Option<String>,
    pub file: Option<Vec<CatalogVersionFile>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CatalogVersionFile {
    pub path: Option<String>,
    #[serde(rename = "XXH3_128")]
    pub xxh3_128: Option<String>,
}

// ── In-memory catalog cache (populated by load_catalog / install on demand) ──

static CATALOG: once_cell::sync::Lazy<Mutex<Option<Vec<CatalogPackage>>>> =
    once_cell::sync::Lazy::new(|| Mutex::new(None));

fn get_catalog_dir(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_config_dir()
        .map(|d| d.join("catalog"))
        .map_err(|e| format!("app_config_dir failed: {}", e))
}

/// Load catalog from on-disk cache (written by the frontend's `sync`).
pub fn load_catalog(app: &tauri::AppHandle) -> Result<Vec<CatalogPackage>, String> {
    {
        let guard = CATALOG.lock().map_err(|e| e.to_string())?;
        if let Some(ref pkgs) = *guard {
            if !pkgs.is_empty() {
                return Ok(pkgs.clone());
            }
        }
    }

    let dir = get_catalog_dir(app)?;
    let index_path = dir.join("index.json");
    if !index_path.exists() {
        return Ok(Vec::new());
    }
    let bytes = std::fs::read(&index_path).map_err(|e| e.to_string())?;
    let packages: Vec<CatalogPackage> =
        serde_json::from_slice(&bytes).map_err(|e| e.to_string())?;

    let mut catalog = CATALOG.lock().map_err(|e| e.to_string())?;
    *catalog = Some(packages.clone());

    Ok(packages)
}

// ── Installed-package persistence (used by install / remove internally) ──

fn get_installed_path(app: &tauri::AppHandle) -> Result<PathBuf, String> {
    app.path()
        .app_config_dir()
        .map(|d| d.join("installed.json"))
        .map_err(|e| format!("app_config_dir failed: {}", e))
}

fn load_installed_map(app: &tauri::AppHandle) -> Result<HashMap<String, String>, String> {
    let path = get_installed_path(app)?;
    if path.exists() {
        let bytes = std::fs::read(&path).map_err(|e| e.to_string())?;
        Ok(serde_json::from_slice(&bytes).unwrap_or_default())
    } else {
        Ok(HashMap::new())
    }
}

fn save_installed_map(app: &tauri::AppHandle, map: &HashMap<String, String>) -> Result<(), String> {
    let path = get_installed_path(app)?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let bytes = serde_json::to_vec_pretty(map).map_err(|e| e.to_string())?;
    std::fs::write(&path, &bytes).map_err(|e| e.to_string())
}

/// Called by `install_package` after successful install.
pub fn add_installed(app: &tauri::AppHandle, package_id: &str, version: &str) -> Result<(), String> {
    let mut map = load_installed_map(app)?;
    map.insert(package_id.to_string(), version.to_string());
    save_installed_map(app, &map)
}

/// Called by `remove_package` after successful removal.
pub fn remove_installed(app: &tauri::AppHandle, package_id: &str) -> Result<(), String> {
    let mut map = load_installed_map(app)?;
    map.remove(package_id);
    save_installed_map(app, &map)
}
