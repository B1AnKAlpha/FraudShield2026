use std::fs;
use std::path::{Path, PathBuf};

use serde_json::json;
use sha2::{Digest, Sha256};
use walkdir::WalkDir;

fn sha256_hex(bytes: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(bytes);
    format!("{:x}", hasher.finalize())
}

fn collect_dist_manifest(dist_dir: &Path) -> serde_json::Value {
    let mut entries = Vec::new();

    if dist_dir.exists() {
        for entry in WalkDir::new(dist_dir).into_iter().filter_map(Result::ok) {
            let path = entry.path();
            if !path.is_file() {
                continue;
            }

            let bytes = fs::read(path).expect("failed to read dist file");
            let relative_path = path
                .strip_prefix(dist_dir)
                .expect("failed to strip dist prefix")
                .to_string_lossy()
                .replace('\\', "/");

            entries.push(json!({
                "path": relative_path,
                "sha256": sha256_hex(&bytes),
            }));
        }
    }

    entries.sort_by(|left, right| {
        left["path"]
            .as_str()
            .unwrap_or_default()
            .cmp(right["path"].as_str().unwrap_or_default())
    });

    json!({
        "version": 1,
        "files": entries,
    })
}

fn main() {
    let manifest_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").expect("missing manifest dir"));
    let dist_dir = manifest_dir.join("../dist");
    let security_dir = manifest_dir.join("security");
    let manifest_path = security_dir.join("integrity-manifest.json");

    fs::create_dir_all(&security_dir).expect("failed to create security directory");

    let manifest_json = collect_dist_manifest(&dist_dir);
    let manifest_bytes =
        serde_json::to_vec_pretty(&manifest_json).expect("failed to serialize integrity manifest");

    fs::write(&manifest_path, &manifest_bytes).expect("failed to write integrity manifest");

    println!("cargo:rustc-env=FRAUDSHIELD_INTEGRITY_MANIFEST_SHA256={}", sha256_hex(&manifest_bytes));
    println!("cargo:rerun-if-changed={}", manifest_path.display());
    println!("cargo:rerun-if-changed={}", dist_dir.display());

    tauri_build::build()
}
