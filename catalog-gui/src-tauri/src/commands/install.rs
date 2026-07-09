use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use tauri::Emitter;

use crate::commands::catalog::{load_catalog, add_installed, remove_installed};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstallStep {
    pub action: String,
    #[serde(default)]
    pub from: Option<String>,
    #[serde(default)]
    pub to: Option<String>,
    #[serde(default)]
    pub path: Option<String>,
    #[serde(default)]
    pub args: Option<Vec<String>>,
    #[serde(default)]
    pub elevate: Option<bool>,
}

#[derive(Clone, Serialize)]
pub struct InstallProgress {
    pub phase: String,
    pub percent: f64,
    pub label: String,
}

/// Resolve the AviUtl2 root directory.
/// Falls back to env var, then probes parent dirs for `launch-ge.sh` or `aviutl2.exe`.
fn resolve_aviutl_root(input: &str) -> PathBuf {
    if !input.is_empty() {
        return PathBuf::from(input);
    }
    if let Ok(env) = std::env::var("AVIUTL2_ROOT") {
        return PathBuf::from(env);
    }
    // Probe: walk up from current dir looking for launch-ge.sh or aviutl2.exe
    let mut cwd = std::env::current_dir().unwrap_or_default();
    loop {
        if cwd.join("launch-ge.sh").exists() || cwd.join("aviutl2.exe").exists() {
            return cwd;
        }
        if !cwd.pop() {
            break;
        }
    }
    std::env::current_dir().unwrap_or_default()
}

#[tauri::command]
pub async fn install_package(
    app: tauri::AppHandle,
    package_id: String,
    aviutl_root: String,
) -> Result<bool, String> {
    let pkgs = load_catalog(&app)?;
    let pkg = pkgs.iter().find(|p| p.id == package_id)
        .ok_or_else(|| format!("Package not found: {}", package_id))?;

    let installer = pkg.installer.as_ref()
        .ok_or_else(|| format!("No installer data for {}", package_id))?;

    let root = resolve_aviutl_root(&aviutl_root);
    let tmp_dir = std::env::temp_dir().join(format!("catalog-{}", package_id));
    std::fs::create_dir_all(&tmp_dir).map_err(|e| e.to_string())?;

    let download_path = download_source(installer, &tmp_dir).await?;

    let steps: Vec<InstallStep> = serde_json::from_value(
        installer.get("install").cloned().unwrap_or(serde_json::Value::Array(vec![]))
    ).map_err(|e| e.to_string())?;

    for (i, step) in steps.iter().enumerate() {
        let _ = app.emit("progress", InstallProgress {
            phase: "installing".into(),
            percent: (i as f64 / steps.len() as f64) * 100.0,
            label: format!("Step {}/{}: {}", i + 1, steps.len(), step.action),
        });

        match step.action.as_str() {
            "download" => {}
            "extract" => {
                let src = step.from.as_ref()
                    .map(|f| super::detect::resolve_macro(f, &root, &tmp_dir))
                    .unwrap_or_else(|| download_path.clone());
                let dest = step.to.as_ref()
                    .map(|t| super::detect::resolve_macro(t, &root, &tmp_dir))
                    .unwrap_or_else(|| tmp_dir.clone());
                extract_zip(&src, &dest)?;
            }
            "copy" => {
                let from = super::detect::resolve_macro(
                    step.from.as_ref().ok_or("copy: no from")?, &root, &tmp_dir
                );
                let to = super::detect::resolve_macro(
                    step.to.as_ref().ok_or("copy: no to")?, &root, &tmp_dir
                );
                copy_recursive(&from, &to)?;
            }
            "delete" => {
                if let Some(path) = &step.path {
                    let target = super::detect::resolve_macro(path, &root, &tmp_dir);
                    if target.exists() {
                        if target.is_dir() {
                            std::fs::remove_dir_all(&target).ok();
                        } else {
                            std::fs::remove_file(&target).ok();
                        }
                    }
                }
            }
            "run" => {
                let exe = super::detect::resolve_macro(
                    step.path.as_ref().ok_or("run: no path")?, &root, &tmp_dir
                );
                let args = step.args.as_ref().map(|a| {
                    a.iter().map(|arg| {
                        super::detect::resolve_macro(arg, &root, &tmp_dir)
                            .to_string_lossy().to_string()
                    }).collect::<Vec<_>>()
                }).unwrap_or_default();
                std::process::Command::new(&exe)
                    .args(&args)
                    .spawn()
                    .map_err(|e| format!("Failed to run {}: {}", exe.display(), e))?;
            }
            _ => {}
        }
    }

    std::fs::remove_dir_all(&tmp_dir).ok();

    let version = pkg.latest_version.as_deref().unwrap_or("");
    add_installed(&app, &package_id, version)?;

    Ok(true)
}

async fn download_source(installer: &serde_json::Value, tmp_dir: &Path) -> Result<PathBuf, String> {
    let source = &installer["source"];
    if let Some(url) = source.get("direct").and_then(|v| v.as_str()) {
        return download_url(url, tmp_dir).await;
    }
    if let Some(gh) = source.get("github") {
        let owner = gh["owner"].as_str().ok_or("no owner")?;
        let repo = gh["repo"].as_str().ok_or("no repo")?;
        let pattern = gh["pattern"].as_str().unwrap_or(".*");
        return download_github_release(owner, repo, pattern, tmp_dir).await;
    }
    if let Some(gd) = source.get("googleDrive").or_else(|| source.get("google_drive")) {
        let id = gd["id"].as_str().ok_or("no gdrive id")?;
        return download_google_drive(id, tmp_dir).await;
    }
    if let Some(url) = source.get("booth").and_then(|v| v.as_str()) {
        return download_url(url, tmp_dir).await;
    }
    Err("No supported download source".to_string())
}

async fn download_url(url: &str, dest_dir: &Path) -> Result<PathBuf, String> {
    let client = reqwest::Client::builder()
        .user_agent("aviutl2-catalog/0.1.0")
        .build().map_err(|e| e.to_string())?;
    let resp = client.get(url).send().await.map_err(|e| e.to_string())?;
    let filename = url.split('/').last().unwrap_or("download");
    let dest = dest_dir.join(filename);
    let bytes = resp.bytes().await.map_err(|e| e.to_string())?;
    std::fs::write(&dest, &bytes).map_err(|e| e.to_string())?;
    Ok(dest)
}

async fn download_github_release(owner: &str, repo: &str, pattern: &str, dest_dir: &Path) -> Result<PathBuf, String> {
    let api = format!("https://api.github.com/repos/{}/{}/releases/latest", owner, repo);
    let client = reqwest::Client::builder()
        .user_agent("aviutl2-catalog/0.1.0")
        .build().map_err(|e| e.to_string())?;
    let resp = client.get(&api).send().await.map_err(|e| e.to_string())?;
    let release: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
    let assets = release["assets"].as_array().ok_or("no assets")?;
    let re = regex::Regex::new(pattern).map_err(|e| e.to_string())?;
    for asset in assets {
        let name = asset["name"].as_str().unwrap_or("");
        if re.is_match(name) {
            let url = asset["browser_download_url"].as_str().ok_or("no url")?;
            return download_url(url, dest_dir).await;
        }
    }
    Err(format!("No asset matching '{}' in {}/{}", pattern, owner, repo))
}

async fn download_google_drive(file_id: &str, dest_dir: &Path) -> Result<PathBuf, String> {
    let url = format!("https://drive.google.com/uc?export=download&id={}", file_id);
    download_url(&url, dest_dir).await
}

fn extract_zip(zip_path: &Path, dest_dir: &Path) -> Result<usize, String> {
    std::fs::create_dir_all(dest_dir).map_err(|e| e.to_string())?;
    let file = std::fs::File::open(zip_path).map_err(|e| e.to_string())?;
    let mut archive = zip::ZipArchive::new(file).map_err(|e| e.to_string())?;
    let count = archive.len();
    archive.extract(dest_dir).map_err(|e| e.to_string())?;
    Ok(count)
}

fn copy_recursive(src: &Path, dst: &Path) -> Result<(), String> {
    if src.is_file() {
        if let Some(parent) = dst.parent() {
            std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
        }
        std::fs::copy(src, dst).map_err(|e| e.to_string())?;
        return Ok(());
    }
    if src.is_dir() {
        for entry in walkdir::WalkDir::new(src).into_iter().filter_map(|e| e.ok()) {
            if entry.file_type().is_file() {
                let rel = entry.path().strip_prefix(src).map_err(|e| e.to_string())?;
                let target = dst.join(rel);
                if let Some(parent) = target.parent() {
                    std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
                }
                std::fs::copy(entry.path(), &target).map_err(|e| e.to_string())?;
            }
        }
    }
    Ok(())
}

#[tauri::command]
pub async fn remove_package(
    app: tauri::AppHandle,
    package_id: String,
    aviutl_root: String,
) -> Result<bool, String> {
    let pkgs = load_catalog(&app)?;
    let pkg = pkgs.iter().find(|p| p.id == package_id);

    if let Some(pkg) = pkg {
        if let Some(installer) = &pkg.installer {
            let steps: Vec<InstallStep> = serde_json::from_value(
                installer.get("uninstall").cloned().unwrap_or(serde_json::Value::Array(vec![]))
            ).map_err(|e| e.to_string())?;
            let root = resolve_aviutl_root(&aviutl_root);
            let tmp_dir = std::env::temp_dir().join(format!("catalog-{}", package_id));
            for step in &steps {
                match step.action.as_str() {
                    "delete" => {
                        if let Some(path) = &step.path {
                            let target = super::detect::resolve_macro(path, &root, &tmp_dir);
                            if target.exists() {
                                if target.is_dir() { std::fs::remove_dir_all(&target).ok(); }
                                else { std::fs::remove_file(&target).ok(); }
                            }
                        }
                    }
                    "run" => {
                        if let Some(path) = &step.path {
                            let exe = super::detect::resolve_macro(path, &root, &tmp_dir);
                            std::process::Command::new(&exe).spawn().ok();
                        }
                    }
                    _ => {}
                }
            }
        }
    }

    remove_installed(&app, &package_id)?;
    Ok(true)
}
