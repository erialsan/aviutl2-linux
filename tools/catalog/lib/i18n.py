"""
Internationalization support for catalog CLI.

Uses simple gettext-like JSON dictionaries.
Supports: ja (default), en, ko, zh-CN, zh-TW
"""

import json
import os
from pathlib import Path
from typing import Optional

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"

# Translations: messages with {0}, {1}, ... positional placeholders
TRANSLATIONS: dict[str, dict[str, str]] = {}

_current_locale: str = "ja"

# Default Japanese translations (fallback)
JA_STRINGS: dict[str, str] = {
    # sync
    "sync.start": "カタログインデックスをダウンロードしています...",
    "sync.done": "カタログを同期しました（{0} ロケール）",
    "sync.error": "同期エラー: {0}",
    # list
    "list.empty": "パッケージがありません。'catalog-cli.py sync' を実行してください。",
    "list.empty_filtered": "条件に一致するパッケージがありません。",
    "list.count": "合計 {0} パッケージ",
    # search
    "search.none": "'{0}' に一致するパッケージはありません。",
    "search.results": "'{0}' の検索結果: {1} 件",
    # info
    "info.not_found": "パッケージ '{0}' が見つかりません。",
    # install
    "install.start": "{0} をインストールしています...",
    "install.not_found": "パッケージ '{0}' が見つかりません。",
    "install.no_install_data": "パッケージ '{0}' にインストールデータがありません。",
    "install.no_aviutl_root": "AviUtl2 のインストール先が見つかりません。AVIUTL2_ROOT を設定してください。",
    "install.done": "{0} のインストールが完了しました。",
    "install.failed": "{0} のインストールに失敗しました。",
    "install.error": "インストールエラー: {0}",
    # update
    "update.none_installed": "インストール済みパッケージはありません。",
    "update.up_to_date": "すべて最新です。",
    "update.not_available": "{0} に利用可能な更新はありません。",
    "update.progress": "{0}: {1} → {2}",
    "update.skipped": "{0}: インストールデータがないためスキップ",
    "update.summary": "更新完了: {0}、失敗: {1}",
    # remove
    "remove.start": "{0} を削除しています...",
    "remove.done": "{0} を削除しました。",
    "remove.failed": "{0} の削除に失敗しました。",
    "remove.error": "削除エラー: {0}",
    # detect
    "detect.start": "インストール済みパッケージを検出しています...",
    "detect.done": "検出完了: {0} パッケージ",
    "detect.error": "検出エラー: {0}",
    # niconi
    "niconi.none": "エクスポートするニコニ・コモンズIDはありません。",
    "niconi.done": "ニコニ・コモンズIDをエクスポートしました。",
    "niconi.error": "エクスポートエラー: {0}",
    # diagnose
    "diagnose.header": "=== システム診断 ===",
    # download
    "download.start": "{0} をダウンロードしています...",
    "download.progress": "ダウンロード: {0}/{1} ({2}%)",
    "download.done": "ダウンロード完了: {0}",
    "download.error": "ダウンロードエラー: {0}",
    # extract
    "extract.zip": "ZIP を展開しています: {0} → {1}",
    "extract.seven": "7z を展開しています: {0} → {1}",
    "extract.done": "展開完了: {0}",
    # detector
    "detector.hashing": "ファイルをハッシュ中: {0}",
}


def load_locale(locale: str) -> dict[str, str]:
    """Load translations for a locale from file. Falls back to Japanese."""
    locale_file = LOCALES_DIR / locale / "messages.json"
    if locale_file.exists():
        try:
            return json.loads(locale_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    # Fallback: return empty, use JA_STRINGS
    return {}


def set_locale(locale: str) -> None:
    """Set the active locale."""
    global _current_locale
    _current_locale = locale
    if locale != "ja":
        TRANSLATIONS[locale] = load_locale(locale)


def get_locale() -> str:
    return _current_locale


def msg(key: str, *args) -> str:
    """Get a translated message, formatting positional placeholders {0}, {1}, etc."""
    # Try current locale, then Japanese fallback
    translations = TRANSLATIONS.get(_current_locale, {})
    template = translations.get(key) or JA_STRINGS.get(key, key)

    if args:
        return template.format(*args)
    return template
