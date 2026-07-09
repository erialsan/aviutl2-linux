#!/usr/bin/env bash
# ============================================================
# AviUtl2 カタログ GUI 起動スクリプト
#
# 初回実行時に自動ビルドします。bun + Rust が必要です。
# ビルド後は直接バイナリを実行します。
# ============================================================
set -euo pipefail

GUI_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$GUI_DIR/src-tauri/target/release/aviutl2-catalog"

if [[ -x "$BINARY" ]]; then
    exec "$BINARY"
fi

echo "[catalog-gui] 初回実行: ビルドを開始します..."

if ! command -v bun >/dev/null 2>&1; then
    echo "[catalog-gui] Error: bun が必要です。https://bun.sh" >&2
    exit 1
fi

if ! command -v cargo >/dev/null 2>&1; then
    echo "[catalog-gui] Error: Rust (cargo) が必要です。https://rustup.rs" >&2
    exit 1
fi

echo "[catalog-gui] フロントエンドをビルド中..."
cd "$GUI_DIR"
bun install --frozen-lockfile 2>/dev/null || bun install
bun run build

echo "[catalog-gui] Rust バックエンドをビルド中（初回は時間がかかります）..."
cargo build --manifest-path src-tauri/Cargo.toml --release

echo "[catalog-gui] ビルド完了。起動します..."
exec "$BINARY"
