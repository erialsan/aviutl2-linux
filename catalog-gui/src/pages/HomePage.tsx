import { useState, useMemo } from "react";
import PackageCard from "../components/PackageCard";
import PackageDetail from "../components/PackageDetail";
import type { PackageItem } from "../hooks/useCatalog";

interface Props {
  catalog: {
    packages: PackageItem[];
    installed: Record<string, string>;
    loading: boolean;
  };
  onSelectPackage: (id: string | null) => void;
  selectedPkg: string | null;
  onBack: () => void;
  onInstalled?: (id: string, version: string) => void;
  onRemoved?: (id: string) => void;
}

const TYPE_ORDER: Record<string, number> = {
  core: 0, inputPlugin: 1, outputPlugin: 2, generalPlugin: 3,
  filterPlugin: 4, script: 5, mod: 6, custom: 7,
};

const TYPE_LABELS: Record<string, string> = {
  core: "本体", inputPlugin: "入力プラグイン", outputPlugin: "出力プラグイン",
  generalPlugin: "拡張プラグイン", filterPlugin: "フィルタプラグイン",
  script: "スクリプト", mod: "MOD", custom: "カスタム",
};

export default function HomePage({ catalog, onSelectPackage, selectedPkg, onBack, onInstalled, onRemoved }: Props) {
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  // ── Filtering (always computed for hook consistency) ──
  const filtered = useMemo(() => {
    let pkgs = catalog.packages;
    if (query) {
      const q = query.toLowerCase();
      pkgs = pkgs.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.author.toLowerCase().includes(q) ||
          p.summary.toLowerCase().includes(q) ||
          p.tags.some((t) => t.toLowerCase().includes(q))
      );
    }
    if (typeFilter !== "all") {
      pkgs = pkgs.filter((p) => p.package_type === typeFilter);
    }
    return pkgs;
  }, [catalog.packages, query, typeFilter]);

  const types = useMemo(() => {
    const set = new Set(catalog.packages.map((p) => p.package_type));
    return Array.from(set).sort((a, b) => (TYPE_ORDER[a] ?? 99) - (TYPE_ORDER[b] ?? 99));
  }, [catalog.packages]);

  // ── Detail view ──
  if (selectedPkg) {
    const pkg = catalog.packages.find((p) => p.id === selectedPkg);
    if (!pkg) {
      return (
        <div className="page">
          <button className="back-btn" onClick={onBack}>← 戻る</button>
          <div className="detail-status"><p>パッケージが見つかりません</p></div>
        </div>
      );
    }
    return (
      <div className="page">
        <button className="back-btn" onClick={onBack}>← 戻る</button>
        <PackageDetail pkg={pkg} installed={catalog.installed} onInstalled={onInstalled} onRemoved={onRemoved} />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="toolbar">
        <input
          className="search-input"
          type="text"
          placeholder="パッケージを検索..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
          <option value="all">すべて</option>
          {types.map((t) => (
            <option key={t} value={t}>{TYPE_LABELS[t] || t}</option>
          ))}
        </select>
      </div>
      <div className="package-count">{filtered.length} パッケージ</div>
      <div className="package-grid">
        {filtered.length === 0 && (
          <div className="detail-status" style={{ gridColumn: "1 / -1" }}>
            <p>条件に一致するパッケージがありません</p>
            <p className="status-hint">「同期」ボタンでカタログを更新してください</p>
          </div>
        )}
        {filtered.map((pkg) => (
          <PackageCard
            key={pkg.id}
            pkg={pkg}
            installed={catalog.installed[pkg.id] || null}
            onClick={() => onSelectPackage(pkg.id)}
          />
        ))}
      </div>
    </div>
  );
}
