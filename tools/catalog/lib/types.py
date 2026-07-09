"""Data type definitions for catalog operations."""

from typing import Any, Optional, TypedDict


class CatalogManifest(TypedDict, total=False):
    schemaVersion: int
    generatedAt: str
    fallbackLocale: str
    locales: list[str]
    paths: dict[str, Any]


class CatalogListPackage(TypedDict, total=False):
    id: str
    legacyId: Optional[str]
    packageType: str
    packageRole: str
    addedAt: str
    name: str
    author: str
    typeLabel: Optional[str]
    tags: list[str]
    summary: str
    niconiCommonsId: Optional[str]
    latestVersion: str
    latestReleaseDate: str


class CatalogDetailPackage(TypedDict, total=False):
    packagePageUrl: str
    originalAuthor: Optional[str]
    description: Any
    licenses: list[Any]
    images: Optional[dict[str, Any]]


class CatalogVersion(TypedDict, total=False):
    version: str
    releaseDate: str
    files: list[dict[str, str]]


class InstallSource(TypedDict, total=False):
    type: str  # directUrl | booth | githubRelease | googleDrive
    url: str
    owner: str
    repo: str
    pattern: str
    id: str


class InstallStep(TypedDict, total=False):
    action: str  # download | extract | extractSfx | copy | delete | run | runAuoSetup
    from_path: str
    to: str
    path: str
    args: list[str]
    elevate: bool


class Installation(TypedDict, total=False):
    source: InstallSource
    installSteps: list[InstallStep]
    uninstallSteps: list[InstallStep]
