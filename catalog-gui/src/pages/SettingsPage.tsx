import { useState } from "react";
import { message } from "@tauri-apps/plugin-dialog";

interface Props {
  catalog: {
    systemInfo: any;
    detect: (root: string) => Promise<void>;
    sync: () => Promise<number>;
    loadSystemInfo: () => void;
  };
}

export default function SettingsPage({ catalog }: Props) {
  const [detecting, setDetecting] = useState(false);

  const handleDetect = async () => {
    const root = catalog.systemInfo?.aviutl_root;
    if (!root) {
      await message("AviUtl2 のルートパスが見つかりません。");
      return;
    }
    setDetecting(true);
    try {
      await catalog.detect(root);
      await message("検出が完了しました。");
    } catch (e) {
      await message(`エラー: ${e}`);
    } finally {
      setDetecting(false);
    }
  };

  const info = catalog.systemInfo;
  return (
    <div className="page">
      <h2>設定</h2>

      <section className="settings-section">
        <h3>AviUtl2 パス</h3>
        <div className="setting-row">
          <span className="setting-label">ルート</span>
          <code className="setting-value">{info?.aviutl_root || "(未設定)"}</code>
        </div>
        <div className="setting-row">
          <span className="setting-label">Wine Prefix</span>
          <code className="setting-value">{info?.wine_prefix || "(未検出)"}</code>
        </div>
      </section>

      <section className="settings-section">
        <h3>インストール検出</h3>
        <p>インストール済みパッケージをファイルハッシュから自動検出します。</p>
        <button className="btn btn-primary" onClick={handleDetect} disabled={detecting}>
          {detecting ? "検出中..." : "検出を実行"}
        </button>
      </section>

      <section className="settings-section">
        <h3>システム情報</h3>
        <div className="setting-row">
          <span className="setting-label">OS</span>
          <span>{info?.os} {info?.kernel}</span>
        </div>
        <div className="setting-row">
          <span className="setting-label">インストール済み</span>
          <span>{info?.installed_count ?? 0} パッケージ</span>
        </div>
        <div className="setting-row">
          <span className="setting-label">カタログ</span>
          <code className="setting-value">{info?.catalog_dir}</code>
        </div>
      </section>
    </div>
  );
}
