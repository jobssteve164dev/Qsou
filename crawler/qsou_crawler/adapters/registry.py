"""Single registry and compatibility gate for all production adapters."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

from qsou_data import SourceRegistry

from .base import SourceAdapter
from .caijing import CaijingAdapter
from .cninfo import CninfoAdapter
from .eastmoney import EastmoneyAdapter
from .netease import NeteaseFinanceAdapter
from .nbs import NbsAdapter
from .mof import MofAdapter
from .official_economic_apis import (
    BisAdapter,
    EcbAdapter,
    EurostatAdapter,
    OecdAdapter,
    UsTreasuryAdapter,
    WorldBankAdapter,
)
from .safe import SafeAdapter
from .sec_edgar import SecEdgarAdapter
from .sina import SinaFinanceAdapter
from .sse import SseAdapter
from .szse import SzseAdapter
from .yicai import YicaiAdapter


ADAPTER_TYPES: tuple[type[SourceAdapter], ...] = (
    SseAdapter,
    SzseAdapter,
    CninfoAdapter,
    EastmoneyAdapter,
    SinaFinanceAdapter,
    NeteaseFinanceAdapter,
    SecEdgarAdapter,
    CaijingAdapter,
    YicaiAdapter,
    NbsAdapter,
    MofAdapter,
    SafeAdapter,
    WorldBankAdapter,
    EcbAdapter,
    EurostatAdapter,
    OecdAdapter,
    BisAdapter,
    UsTreasuryAdapter,
)


class AdapterRegistry:
    def __init__(self, sources: Optional[SourceRegistry] = None) -> None:
        self.sources = sources or SourceRegistry()
        self._types = {adapter_type.source_id: adapter_type for adapter_type in ADAPTER_TYPES}
        if len(self._types) != len(ADAPTER_TYPES):
            raise ValueError("来源适配器存在重复 source_id")
        registered = {source["source_id"] for source in self.sources.all()}
        missing = registered - set(self._types)
        extra = set(self._types) - registered
        if missing or extra:
            raise ValueError(f"来源与适配器没有一一对应: missing={sorted(missing)}, extra={sorted(extra)}")
        for source_id in registered:
            self.create(source_id)

    def create(
        self,
        source_id: str,
        source: Optional[Mapping[str, Any]] = None,
    ) -> SourceAdapter:
        source_config = dict(source) if source is not None else self.sources.get(source_id)
        if source_config.get("source_id") != source_id:
            raise ValueError(f"有效来源配置与来源标识不一致: {source_id}")
        try:
            adapter_type = self._types[source_id]
        except KeyError as exc:
            raise ValueError(f"来源没有适配器: {source_id}") from exc
        return adapter_type(source_config)

    def all(self, selected: Optional[Iterable[str]] = None) -> list[SourceAdapter]:
        if selected is None:
            source_ids = [
                source["source_id"] for source in self.sources.all(enabled_only=True)
            ]
        else:
            source_ids = list(selected)
            disabled = [source_id for source_id in source_ids if not self.sources.get(source_id).get("enabled")]
            if disabled:
                raise ValueError(f"来源未启用，不能进入采集调度: {sorted(disabled)}")
        return [self.create(source_id) for source_id in source_ids]

    def catalog(self) -> list[dict[str, str]]:
        return [
            {
                "source_id": adapter.source_id,
                "adapter_id": adapter.adapter_id,
                "adapter_version": adapter.version,
                "document_type": adapter.document_type,
            }
            for adapter in [self.create(source["source_id"]) for source in self.sources.all()]
        ]
