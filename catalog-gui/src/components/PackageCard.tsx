import { type PackageItem } from "../hooks/useCatalog";

interface Props {
  pkg: PackageItem;
  installed: string | null;
  hasUpdate?: boolean;
  onClick: () => void;
}

const TYPE_COLORS: Record<string, string> = {
  core: "#4CAF50",
  inputPlugin: "#2196F3",
  outputPlugin: "#FF9800",
  generalPlugin: "#9C27B0",
  filterPlugin: "#E91E63",
  script: "#00BCD4",
  mod: "#FF5722",
  custom: "#607D8B",
};

export default function PackageCard({ pkg, installed, hasUpdate, onClick }: Props) {
  const color = TYPE_COLORS[pkg.package_type] || "#607D8B";
  const statusLabel = installed
    ? hasUpdate
      ? `${installed} → ${pkg.latest_version}`
      : `v${installed}`
    : null;

  return (
    <div className="package-card" onClick={onClick}>
      <div className="package-type-badge" style={{ backgroundColor: color }}>
        {pkg.package_type.slice(0, 2)}
      </div>
      <div className="package-card-body">
        <h3 className="package-name">{pkg.name}</h3>
        <div className="package-meta">
          <span className="package-author">{pkg.author}</span>
          {statusLabel && (
            <span className={`package-version ${hasUpdate ? "has-update" : ""}`}>
              {statusLabel}
            </span>
          )}
        </div>
        <p className="package-summary">{pkg.summary}</p>
        {pkg.tags.length > 0 && (
          <div className="package-tags">
            {pkg.tags.slice(0, 3).map((tag) => (
              <span key={tag} className="tag">{tag}</span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
