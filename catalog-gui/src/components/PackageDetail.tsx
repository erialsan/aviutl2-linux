import { useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { message, ask } from "@tauri-apps/plugin-dialog";
import type { PackageItem } from "../hooks/useCatalog";

interface Props {
  pkg: PackageItem;
  installed: Record<string, string>;
  /** Called after successful install/update */
  onInstalled?: (id: string, version: string) => void;
  /** Called after successful removal */
  onRemoved?: (id: string) => void;
}

export default function PackageDetail({ pkg, installed, onInstalled, onRemoved }: Props) {
  const [installing, setInstalling] = useState(false);

  const isInstalled = pkg.id in installed;
  const installedVer = installed[pkg.id];
  const hasUpdate = isInstalled && pkg.latest_version && installedVer !== pkg.latest_version;

  const handleInstall = async () => {
    setInstalling(true);
    try {
      const ok = await ask(`${pkg.name} をインストールしますか？`, { title: "インストール確認" });
      if (!ok) return;
      await invoke("install_package", { packageId: pkg.id, aviutlRoot: "" });
      onInstalled?.(pkg.id, pkg.latest_version);
      await message("インストールが完了しました。");
    } catch (e) {
      await message(`インストールエラー: ${e}`);
    } finally {
      setInstalling(false);
    }
  };

  const handleRemove = async () => {
    try {
      const ok = await ask(`${pkg.name} を削除しますか？`, { title: "削除確認" });
      if (!ok) return;
      await invoke("remove_package", { packageId: pkg.id, aviutlRoot: "" });
      onRemoved?.(pkg.id);
      await message("削除しました。");
    } catch (e) {
      await message(`削除エラー: ${e}`);
    }
  };

  return (
    <div className="package-detail">
      <div className="detail-header">
        <h2>{pkg.name}</h2>
        <div className="detail-actions">
          {isInstalled ? (
            <>
              <span className="installed-badge">
                {installedVer}{hasUpdate && ` → ${pkg.latest_version}`}
              </span>
              {hasUpdate && (
                <button className="btn btn-primary" onClick={handleInstall} disabled={installing}>
                  {installing ? "更新中..." : "更新"}
                </button>
              )}
              <button className="btn btn-danger" onClick={handleRemove}>削除</button>
            </>
          ) : (
            <button className="btn btn-primary" onClick={handleInstall} disabled={installing}>
              {installing ? "インストール中..." : "インストール"}
            </button>
          )}
        </div>
      </div>

      <div className="detail-meta">
        {pkg.author && <span>作者: {pkg.author}</span>}
        <span>タイプ: {pkg.package_type}</span>
        {pkg.latest_version && <span>最新版: {pkg.latest_version}</span>}
      </div>

      {pkg.summary && <p className="detail-summary">{pkg.summary}</p>}

      {pkg.tags && pkg.tags.length > 0 && (
        <div className="detail-tags">
          {pkg.tags.map((tag) => <span key={tag} className="tag">{tag}</span>)}
        </div>
      )}
    </div>
  );
}
