import { useState, useEffect, useCallback } from "react";
import { invoke } from "@tauri-apps/api/core";

// ── Types matching GitHub index.json schema ──

export interface CatalogPackageRaw {
  id: string;
  name: string;
  /** Japanese type label, e.g. "フィルタプラグイン" */
  type?: string;
  author?: string;
  summary?: string;
  description?: string;
  tags?: string[];
  "latest-version"?: string;
  release_date?: string;
  popularity?: number;
  trend?: number;
  niconi_comons_id?: string;
  installer?: unknown;
  version?: unknown[];
  dependencies?: string[];
  images?: unknown[];
  licenses?: unknown[];
  repo_url?: string;
  package_page_url?: string;
}

export interface PackageItem {
  id: string;
  name: string;
  package_type: string;
  author: string;
  summary: string;
  latest_version: string;
  tags: string[];
  niconi_comons_id: string;
}

export interface SystemInfo {
  os: string;
  kernel: string;
  aviutl_root: string | null;
  aviutl_exe_exists: boolean;
  wine_prefix: string | null;
  wine_prefix_exists: boolean;
  catalog_dir: string;
  installed_count: number;
}

// ── Normalization ──

const TYPE_MAP: Record<string, string> = {
  "本体": "core",
  "入力プラグイン": "inputPlugin",
  "出力プラグイン": "outputPlugin",
  "拡張プラグイン": "generalPlugin",
  "フィルタプラグイン": "filterPlugin",
  "スクリプト": "script",
  "カスタム": "custom",
};

function normalizeType(t: string | undefined): string {
  return TYPE_MAP[t ?? ""] ?? t ?? "custom";
}

function normalize(raw: CatalogPackageRaw): PackageItem {
  return {
    id: raw.id,
    name: raw.name,
    package_type: normalizeType(raw.type),
    author: raw.author ?? "",
    summary: raw.summary ?? "",
    latest_version: raw["latest-version"] ?? "",
    tags: raw.tags ?? [],
    niconi_comons_id: raw.niconi_comons_id ?? "",
  };
}

// ── Storage keys ──

const CACHE_KEY = "catalog-packages";
const INSTALLED_KEY = "catalog-installed";
const CATALOG_URL =
  "https://raw.githubusercontent.com/Neosku/aviutl2-catalog-data/main/index.json";

function loadCache<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function saveCache<T>(key: string, value: T): void {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // quota exceeded — silently ignore
  }
}

// ── Browser-side system info ──

function detectOS(): string {
  if (typeof navigator === "undefined") return "unknown";
  const ua = navigator.userAgent;
  if (ua.includes("Win")) return "windows";
  if (ua.includes("Mac")) return "macos";
  if (ua.includes("Linux")) return "linux";
  if (ua.includes("Android")) return "android";
  if (ua.includes("iOS") || ua.includes("iPhone") || ua.includes("iPad"))
    return "ios";
  return "unknown";
}

// ── Hook ──

export function useCatalog() {
  const [packages, setPackages] = useState<PackageItem[]>(() =>
    loadCache<PackageItem[]>(CACHE_KEY, []),
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [installed, setInstalled] = useState<Record<string, string>>(() =>
    loadCache<Record<string, string>>(INSTALLED_KEY, {}),
  );
  const [systemInfo, setSystemInfo] = useState<SystemInfo | null>(null);

  // ── Sync: fetch catalog from GitHub ──

  const sync = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(CATALOG_URL);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      const raw: CatalogPackageRaw[] = await resp.json();
      const normalized = raw.map(normalize);
      setPackages(normalized);
      saveCache(CACHE_KEY, normalized);
      return normalized.length;
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      throw e;
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Load from cache (re-reads localStorage) ──

  const loadPackages = useCallback(async () => {
    setPackages(loadCache(CACHE_KEY, []));
    setInstalled(loadCache(INSTALLED_KEY, {}));
  }, []);

  // ── System info: try Tauri, fall back to browser ──

  const loadSystemInfo = useCallback(async () => {
    // Try Tauri IPC first
    try {
      const info = await invoke<SystemInfo>("get_system_info");
      setSystemInfo(info);
      return;
    } catch {
      // not in Tauri — fall through to browser info
    }
    // Browser fallback
    setSystemInfo({
      os: detectOS(),
      kernel: "",
      aviutl_root: null,
      aviutl_exe_exists: false,
      wine_prefix: null,
      wine_prefix_exists: false,
      catalog_dir: "localStorage",
      installed_count: Object.keys(
        loadCache<Record<string, string>>(INSTALLED_KEY, {}),
      ).length,
    });
  }, []);

  // ── Local search ──

  const search = useCallback(
    async (query: string): Promise<PackageItem[]> => {
      const q = query.toLowerCase();
      return packages.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          p.author.toLowerCase().includes(q) ||
          p.summary.toLowerCase().includes(q) ||
          p.tags.some((t) => t.toLowerCase().includes(q)),
      );
    },
    [packages],
  );

  // ── Installed helpers ──

  const addInstalled = useCallback(
    (packageId: string, version: string) => {
      setInstalled((prev) => {
        const next = { ...prev, [packageId]: version };
        saveCache(INSTALLED_KEY, next);
        return next;
      });
    },
    [],
  );

  const removeInstalledWith = useCallback((packageId: string) => {
    setInstalled((prev) => {
      const next = { ...prev };
      delete next[packageId];
      saveCache(INSTALLED_KEY, next);
      return next;
    });
  }, []);

  // ── Detect installed (Tauri only) ──

  const detect = useCallback(
    async (aviutlRoot: string) => {
      try {
        const results = await invoke<
          { package_id: string; version: string; matched: boolean }[]
        >("detect_installed", { aviutlRoot });
        const map: Record<string, string> = {};
        for (const r of results) {
          if (r.matched) map[r.package_id] = r.version;
        }
        setInstalled(map);
        saveCache(INSTALLED_KEY, map);
      } catch (e) {
        setError(String(e));
      }
    },
    [],
  );

  // ── Init ──

  useEffect(() => {
    loadSystemInfo();
  }, [loadSystemInfo]);

  return {
    packages,
    loading,
    error,
    installed,
    systemInfo,
    sync,
    loadPackages,
    search,
    detect,
    addInstalled,
    removeInstalled: removeInstalledWith,
  };
}
