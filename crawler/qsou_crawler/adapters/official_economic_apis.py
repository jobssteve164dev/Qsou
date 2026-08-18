"""Machine-readable public economic datasets from authoritative institutions."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any, Mapping, Optional

from .base import DocumentReference, ResponsePayload, SourceAdapter, normalize_text


class OfficialEconomicApiAdapter(SourceAdapter):
    """Treat one bounded official API response as one versioned data release."""

    dataset_id = ""
    dataset_title = ""
    attribution = ""
    document_type = "economic_dataset"

    def discover(self, response: ResponsePayload) -> list[DocumentReference]:
        rows, published_at = self.extract_rows(response)
        if not rows:
            raise ValueError(f"{self.source_id} 官方接口没有返回数据")
        return [
            DocumentReference(
                url=response.url,
                source_document_id=self.dataset_id,
                title=self.dataset_title,
                published_at=published_at,
                document_type=self.document_type,
                metadata={"inline_document": True, "row_count": len(rows)},
            )
        ]

    def parse_document(
        self,
        response: ResponsePayload,
        reference: DocumentReference,
    ) -> Optional[dict[str, Any]]:
        rows, published_at = self.extract_rows(response)
        if not rows:
            return None
        rendered = []
        for row in rows[:500]:
            rendered.append("；".join(f"{key}: {value}" for key, value in row.items() if value not in (None, "")))
        content = normalize_text("\n".join([self.dataset_title, *rendered]))
        if len(content) < 50:
            return None
        return {
            "source_document_id": self.dataset_id,
            "type": self.document_type,
            "title": self.dataset_title,
            "content": content[:500_000],
            "url": response.url,
            "source": self.source.get("source_name", self.source_id),
            "source_id": self.source_id,
            "source_published_at": published_at or reference.published_at,
            "parser_version": f"{self.adapter_id}/{self.version}",
            "metadata": {
                "adapter_id": self.adapter_id,
                "adapter_version": self.version,
                "extraction": "official_machine_api",
                "dataset_id": self.dataset_id,
                "row_count": len(rows),
                "attribution": self.attribution,
            },
        }

    def extract_rows(self, response: ResponsePayload) -> tuple[list[dict[str, Any]], Optional[str]]:
        raise NotImplementedError

    @staticmethod
    def csv_rows(response: ResponsePayload) -> list[dict[str, Any]]:
        return [dict(row) for row in csv.DictReader(StringIO(response.text))]

    @staticmethod
    def latest(rows: list[Mapping[str, Any]], *fields: str) -> Optional[str]:
        values = [str(row.get(field)) for row in rows for field in fields if row.get(field)]
        return max(values) if values else None


class WorldBankAdapter(OfficialEconomicApiAdapter):
    source_id = "world-bank"
    adapter_id = "world-bank-wdi"
    version = "1.0.0"
    dataset_id = "WDI-NY.GDP.MKTP.CD-CHN"
    dataset_title = "世界银行：中国国内生产总值（现价美元）"
    attribution = "World Bank: World Development Indicators"

    def extract_rows(self, response):
        payload = json.loads(response.text)
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            raise ValueError("世界银行指标接口响应结构无效")
        rows = [
            {
                "国家": item.get("country", {}).get("value"),
                "指标": item.get("indicator", {}).get("value"),
                "年份": item.get("date"),
                "数值": item.get("value"),
            }
            for item in payload[1]
            if item.get("value") is not None
        ]
        updated = payload[0].get("lastupdated") if isinstance(payload[0], Mapping) else None
        return rows, updated or self.latest(rows, "年份")


class EcbAdapter(OfficialEconomicApiAdapter):
    source_id = "ecb"
    adapter_id = "ecb-reference-rates"
    version = "1.0.0"
    dataset_id = "EXR-D-USD-EUR-SP00-A"
    dataset_title = "欧洲央行：欧元兑美元参考汇率"
    attribution = "Source: ECB statistics"

    def extract_rows(self, response):
        rows = self.csv_rows(response)
        selected = [
            {
                "日期": row.get("TIME_PERIOD"),
                "币种": row.get("CURRENCY"),
                "计价币": row.get("CURRENCY_DENOM"),
                "参考汇率": row.get("OBS_VALUE"),
                "状态": row.get("OBS_STATUS"),
            }
            for row in rows
        ]
        return selected, self.latest(selected, "日期")


class EurostatAdapter(OfficialEconomicApiAdapter):
    source_id = "eurostat"
    adapter_id = "eurostat-hicp"
    version = "1.0.0"
    dataset_id = "prc_hicp_manr-EA20-CP00"
    dataset_title = "欧盟统计局：欧元区调和消费价格指数年率"
    attribution = "Source: Eurostat, prc_hicp_manr"

    def extract_rows(self, response):
        payload = json.loads(response.text)
        values = payload.get("value", {})
        time_category = payload.get("dimension", {}).get("time", {}).get("category", {})
        time_index = time_category.get("index", {})
        if isinstance(time_index, list):
            ordered_times = time_index
        else:
            ordered_times = [key for key, _ in sorted(time_index.items(), key=lambda item: item[1])]
        rows = [
            {"期间": period, "年率（%）": values.get(str(index))}
            for index, period in enumerate(ordered_times)
            if str(index) in values
        ]
        return rows, payload.get("updated") or self.latest(rows, "期间")


class OecdAdapter(OfficialEconomicApiAdapter):
    source_id = "oecd"
    adapter_id = "oecd-leading-indicator"
    version = "1.0.0"
    dataset_id = "DF_CLI-CHN-M-LI"
    dataset_title = "经合组织：中国综合领先指标"
    attribution = "Source: OECD Data Explorer"

    def extract_rows(self, response):
        rows = self.csv_rows(response)
        selected = [
            {
                "地区": row.get("Reference area") or row.get("REF_AREA"),
                "期间": row.get("TIME_PERIOD"),
                "指标": row.get("Measure") or row.get("MEASURE"),
                "数值": row.get("OBS_VALUE"),
                "单位": row.get("Unit of measure") or row.get("UNIT_MEASURE"),
            }
            for row in rows
        ]
        return selected, self.latest(selected, "期间")


class BisAdapter(OfficialEconomicApiAdapter):
    source_id = "bis"
    adapter_id = "bis-policy-rates"
    version = "1.0.0"
    dataset_id = "WS_CBPOL-D-US"
    dataset_title = "国际清算银行：美国央行政策利率"
    attribution = "Source: Bank for International Settlements statistics"

    def extract_rows(self, response):
        data = self.csv_rows(response)
        rows = [
            {
                "地区": item.get("REF_AREA"),
                "日期": item.get("TIME_PERIOD"),
                "政策利率": item.get("OBS_VALUE"),
                "状态": item.get("OBS_STATUS"),
                "说明": item.get("TITLE"),
            }
            for item in data
        ]
        return rows, self.latest(rows, "日期")


class UsTreasuryAdapter(OfficialEconomicApiAdapter):
    source_id = "us-treasury"
    adapter_id = "us-treasury-debt"
    version = "1.0.0"
    dataset_id = "debt-to-the-penny"
    dataset_title = "美国财政部：每日联邦债务余额"
    attribution = "U.S. Department of the Treasury, Fiscal Data"

    def extract_rows(self, response):
        payload = json.loads(response.text)
        rows = [
            {
                "日期": item.get("record_date"),
                "公众持有债务": item.get("debt_held_public_amt"),
                "政府内部持有": item.get("intragov_hold_amt"),
                "联邦债务总额": item.get("tot_pub_debt_out_amt"),
            }
            for item in payload.get("data", [])
        ]
        return rows, self.latest(rows, "日期")
