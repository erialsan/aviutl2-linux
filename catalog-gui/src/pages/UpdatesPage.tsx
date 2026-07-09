import { useMemo } from "react";
import { type PackageItem } from "../hooks/useCatalog";
import PackageCard from "../components/PackageCard";

interface Props {
  catalog: {
    packages: PackageItem[];
    installed: Record<string, string>;
    loading: boolean;
  };
}

export default function UpdatesPage({ catalog }: Props) {
  const updates = useMemo(() => {
    const result: { pkg: PackageItem; installedVer: string }[] = [];
    for (const [id, ver] of Object.entries(catalog.installed)) {
      if (!ver) continue;
      const pkg = catalog.packages.find((p) => p.id === id);
      if (pkg && pkg.latest_version && pkg.latest_version !== ver) {
        result.push({ pkg, installedVer: ver });
      }
    }
    return result;
  }, [catalog.packages, catalog.installed]);

  if (Object.keys(catalog.installed).length === 0) {
    return (
      <div className="page">
        <h2>アップデート</h2>
        <p className="empty-state">インストール済みパッケージはありません。パッケージ一覧からインストールしてください。</p>
      </div>
    );
  }

  if (updates.length === 0) {
    return (
      <div className="page">
        <h2>アップデート</h2>
        <p className="empty-state">すべて最新です。</p>
      </div>
    );
  }

  return (
    <div className="page">
      <h2>アップデート ({updates.length})</h2>
      <div className="package-grid">
        {updates.map(({ pkg, installedVer }) => (
          <PackageCard
            key={pkg.id}
            pkg={pkg}
            installed={installedVer}
            hasUpdate
            onClick={() => {}}
          />
        ))}
      </div>
    </div>
  );
}
