"""正式数据源登记与 URL 解析。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


class UnknownSourceError(ValueError):
    """URL 不属于任何已登记的正式来源。"""


AUTOMATED_ACCESS_RIGHTS = {"automated_access_allowed"}


def automated_access_allowed(source: Dict[str, Any]) -> bool:
    """Return whether a source may enter any network-driven collection path."""
    return bool(source.get("enabled")) and source.get("rights_status") in AUTOMATED_ACCESS_RIGHTS


def assert_automated_access(source: Dict[str, Any]) -> None:
    if not source.get("enabled"):
        raise ValueError(f"来源未启用，不能自动采集: {source.get('source_id', 'unknown')}")
    if source.get("rights_status") not in AUTOMATED_ACCESS_RIGHTS:
        raise ValueError(
            "来源没有允许自动访问的有效权利状态: "
            f"{source.get('source_id', 'unknown')}/{source.get('rights_status', 'missing')}"
        )


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_registry_path() -> Path:
    configured = os.getenv("QSOU_SOURCE_REGISTRY")
    return Path(configured).expanduser().resolve() if configured else project_root() / "config" / "sources.json"


class SourceRegistry:
    """从版本化 JSON 文件读取来源契约。"""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path or default_registry_path()).resolve()
        self.schema_version = 0
        self._sources: Dict[str, Dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        if not self.path.is_file():
            raise FileNotFoundError(f"来源登记文件不存在: {self.path}")

        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 2:
            raise ValueError("仅支持 schema_version=2 的来源登记文件")

        sources: Dict[str, Dict[str, Any]] = {}
        for source in payload.get("sources", []):
            source_id = str(source.get("source_id", "")).strip()
            domains = [self._normalize_domain(value) for value in source.get("domains", []) if value]
            if not source_id or not domains:
                raise ValueError("每个来源必须提供 source_id 和至少一个 domains 值")
            if source_id in sources:
                raise ValueError(f"来源重复登记: {source_id}")
            adapter_id = str(source.get("adapter_id", "")).strip()
            adapter_version = str(source.get("adapter_version", "")).strip()
            adapter_kind = str(source.get("adapter_kind", "")).strip()
            if not adapter_id or not adapter_version or not adapter_kind:
                raise ValueError(f"来源缺少适配器契约: {source_id}")
            rights_status = str(source.get("rights_status", "")).strip()
            rights_reference = str(source.get("rights_reference", "")).strip()
            enabled = bool(source.get("enabled", True))
            if not rights_status:
                raise ValueError(f"来源缺少权利状态: {source_id}")
            if rights_status in AUTOMATED_ACCESS_RIGHTS and not rights_reference:
                raise ValueError(f"允许自动访问的来源必须登记权利依据: {source_id}")
            if enabled and rights_status not in AUTOMATED_ACCESS_RIGHTS:
                raise ValueError(
                    f"未取得自动访问授权的来源不能启用: {source_id}/{rights_status}"
                )

            normalized = dict(source)
            normalized["source_id"] = source_id
            normalized["domains"] = domains
            normalized["rights_status"] = rights_status
            normalized["enabled"] = enabled
            normalized.setdefault("health_state", "configured")
            sources[source_id] = normalized

        if not sources:
            raise ValueError("来源登记不能为空")

        self.schema_version = payload["schema_version"]
        self._sources = sources

    def all(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        sources = [dict(source) for source in self._sources.values()]
        if enabled_only:
            sources = [source for source in sources if source.get("enabled")]
        return sorted(sources, key=lambda source: source["source_id"])

    def get(self, source_id: str) -> Dict[str, Any]:
        try:
            return dict(self._sources[source_id])
        except KeyError as exc:
            raise UnknownSourceError(f"来源未登记: {source_id}") from exc

    def resolve_url(self, url: str, enabled_only: bool = True) -> Dict[str, Any]:
        host = self._normalize_domain(urlparse(url).hostname or "")
        matches: List[tuple[int, Dict[str, Any]]] = []

        for source in self._sources.values():
            if enabled_only and not source.get("enabled"):
                continue
            for domain in source["domains"]:
                if host == domain or host.endswith(f".{domain}"):
                    matches.append((len(domain), source))

        if not matches:
            raise UnknownSourceError(f"URL 不属于已登记来源: {url}")

        matches.sort(key=lambda item: item[0], reverse=True)
        return dict(matches[0][1])

    @staticmethod
    def _normalize_domain(value: str) -> str:
        normalized = value.strip().lower().rstrip(".")
        return normalized[4:] if normalized.startswith("www.") else normalized
