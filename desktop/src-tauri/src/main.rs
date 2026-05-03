#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tauri::{AppHandle, Manager};

const MANIFEST_HASH: &str = env!("FRAUDSHIELD_INTEGRITY_MANIFEST_SHA256");

#[derive(Deserialize)]
struct IntegrityManifest {
    files: Vec<IntegrityEntry>,
}

#[derive(Deserialize)]
struct IntegrityEntry {
    path: String,
    sha256: String,
}

#[derive(Serialize)]
struct LoginSecurityCheckResult {
    machine_code: String,
    integrity_checked: bool,
    integrity_message: String,
}

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

fn sha256_file(path: &Path) -> Result<String, String> {
    let bytes = fs::read(path).map_err(|error| format!("读取文件失败 {}: {error}", path.display()))?;
    Ok(sha256_hex(&bytes))
}

fn parse_machine_guid(output: &str) -> Option<String> {
    output
        .lines()
        .find(|line| line.contains("MachineGuid"))
        .and_then(|line| line.split_whitespace().last())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

fn get_machine_seed() -> Result<String, String> {
    #[cfg(target_os = "windows")]
    {
        let output = Command::new("reg")
            .args([
                "query",
                r"HKLM\SOFTWARE\Microsoft\Cryptography",
                "/v",
                "MachineGuid",
            ])
            .output()
            .map_err(|error| format!("读取机器码失败: {error}"))?;

        let stdout = String::from_utf8_lossy(&output.stdout);
        if let Some(machine_guid) = parse_machine_guid(&stdout) {
            return Ok(machine_guid);
        }

        Err("无法获取系统 MachineGuid".to_string())
    }

    #[cfg(not(target_os = "windows"))]
    {
        let hostname = std::env::var("HOSTNAME").unwrap_or_else(|_| "unknown-host".to_string());
        Ok(hostname)
    }
}

fn get_machine_code() -> Result<String, String> {
    let seed = get_machine_seed()?;
    Ok(sha256_hex(seed.trim().as_bytes()))
}

fn list_process_snapshot() -> Result<String, String> {
    #[cfg(target_os = "windows")]
    {
        let output = Command::new("tasklist")
            .args(["/fo", "csv", "/nh"])
            .output()
            .map_err(|error| format!("读取进程列表失败: {error}"))?;
        return Ok(String::from_utf8_lossy(&output.stdout).to_string());
    }

    #[cfg(not(target_os = "windows"))]
    {
        let output = Command::new("ps")
            .args(["-A", "-o", "comm="])
            .output()
            .map_err(|error| format!("读取进程列表失败: {error}"))?;
        Ok(String::from_utf8_lossy(&output.stdout).to_string())
    }
}

fn detect_packet_sniffer() -> Result<Option<String>, String> {
    let snapshot = list_process_snapshot()?.to_lowercase();
    let candidates = [
        "wireshark",
        "fiddler",
        "charles",
        "mitmproxy",
        "tcpdump",
        "burpsuite",
        "burp",
    ];

    Ok(candidates
        .iter()
        .find(|name| snapshot.contains(**name))
        .map(|name| (*name).to_string()))
}

fn manifest_path(app: &AppHandle) -> Result<PathBuf, String> {
    if cfg!(debug_assertions) {
        return Ok(PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("security/integrity-manifest.json"));
    }

    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|error| format!("读取资源目录失败: {error}"))?;
    Ok(resource_dir.join("security").join("integrity-manifest.json"))
}

fn resolve_runtime_asset_path(app: &AppHandle, relative_path: &str) -> Result<PathBuf, String> {
    if cfg!(debug_assertions) {
        return Ok(PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("../dist")
            .join(relative_path));
    }

    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|error| format!("读取资源目录失败: {error}"))?;
    let exe_dir = std::env::current_exe()
        .map_err(|error| format!("读取程序路径失败: {error}"))?
        .parent()
        .map(Path::to_path_buf)
        .ok_or_else(|| "无法定位程序目录".to_string())?;

    let candidates: Vec<PathBuf> = vec![
        resource_dir.join(relative_path),
        exe_dir.join(relative_path),
        exe_dir.join("resources").join(relative_path),
    ];

    candidates
        .into_iter()
        .find(|path: &PathBuf| path.exists())
        .ok_or_else(|| format!("缺少运行时资源 {relative_path}"))
}

fn check_file_integrity(app: &AppHandle) -> Result<String, String> {
    if cfg!(debug_assertions) {
        return Ok("开发模式已跳过文件完整性检查".to_string());
    }

    let path = manifest_path(app)?;
    let manifest_bytes =
        fs::read(&path).map_err(|error| format!("读取完整性清单失败 {}: {error}", path.display()))?;
    let actual_manifest_hash = sha256_hex(&manifest_bytes);
    if actual_manifest_hash != MANIFEST_HASH {
        return Err("完整性清单签名不匹配，疑似被篡改".to_string());
    }

    let manifest: IntegrityManifest =
        serde_json::from_slice(&manifest_bytes).map_err(|error| format!("解析完整性清单失败: {error}"))?;
    if manifest.files.is_empty() {
        return Err("完整性清单为空，无法执行校验".to_string());
    }

    for entry in &manifest.files {
        let runtime_path = resolve_runtime_asset_path(app, &entry.path)?;
        let actual_hash = sha256_file(&runtime_path)?;
        if actual_hash != entry.sha256 {
            return Err(format!("关键文件校验失败: {}", entry.path));
        }
    }

    Ok(format!("已校验 {} 个关键文件", manifest.files.len()))
}

#[tauri::command]
fn run_login_security_checks(app: AppHandle) -> Result<LoginSecurityCheckResult, String> {
    if let Some(process_name) = detect_packet_sniffer()? {
        return Err(format!("检测到抓包工具 {process_name}，请关闭后重试"));
    }

    let integrity_message = check_file_integrity(&app)?;
    let machine_code = get_machine_code()?;

    Ok(LoginSecurityCheckResult {
        machine_code,
        integrity_checked: !cfg!(debug_assertions),
        integrity_message,
    })
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![run_login_security_checks])
        .run(tauri::generate_context!())
        .expect("failed to run tauri application");
}
