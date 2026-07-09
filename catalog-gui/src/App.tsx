import { useState, useEffect } from "react";
import { useCatalog } from "./hooks/useCatalog";
import HomePage from "./pages/HomePage";
import UpdatesPage from "./pages/UpdatesPage";
import SettingsPage from "./pages/SettingsPage";

type Page = "home" | "updates" | "settings";

function App() {
  const [page, setPage] = useState<Page>("home");
  const [selectedPkg, setSelectedPkg] = useState<string | null>(null);
  const catalog = useCatalog();

  useEffect(() => {
    if (catalog.packages.length === 0 && !catalog.error) {
      catalog.sync().catch(() => {});
    }
  }, [catalog]);

  const renderPage = () => {
    switch (page) {
      case "home":
        return (
          <HomePage
            catalog={catalog}
            onSelectPackage={setSelectedPkg}
            selectedPkg={selectedPkg}
            onBack={() => setSelectedPkg(null)}
            onInstalled={catalog.addInstalled}
            onRemoved={catalog.removeInstalled}
          />
        );
      case "updates":
        return <UpdatesPage catalog={catalog} />;
      case "settings":
        return <SettingsPage catalog={catalog} />;
    }
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>AviUtl2 カタログ</h1>
        </div>
        <nav className="sidebar-nav">
          <button
            className={`nav-btn ${page === "home" ? "active" : ""}`}
            onClick={() => { setPage("home"); setSelectedPkg(null); }}
          >
            <span className="nav-icon">🏠</span>
            パッケージ一覧
          </button>
          <button
            className={`nav-btn ${page === "updates" ? "active" : ""}`}
            onClick={() => setPage("updates")}
          >
            <span className="nav-icon">🔄</span>
            アップデート
            {Object.keys(catalog.installed).length > 0 && (
              <span className="badge">{Object.keys(catalog.installed).length}</span>
            )}
          </button>
          <button
            className={`nav-btn ${page === "settings" ? "active" : ""}`}
            onClick={() => setPage("settings")}
          >
            <span className="nav-icon">⚙️</span>
            設定
          </button>
        </nav>
        <div className="sidebar-footer">
          <button className="sync-btn" onClick={() => catalog.sync().catch(() => {})} disabled={catalog.loading}>
            {catalog.loading ? "同期中..." : "🔄 同期"}
          </button>
        </div>
      </aside>
      <main className="content">
        {catalog.error && (
          <div className="error-banner">
            {catalog.error}
            <button onClick={() => catalog.sync().catch(() => {})}>再試行</button>
          </div>
        )}
        {renderPage()}
      </main>
    </div>
  );
}

export default App;
