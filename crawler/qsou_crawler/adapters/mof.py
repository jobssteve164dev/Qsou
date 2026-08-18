"""Ministry of Finance official statistical release adapter."""

from .official_statistics import OfficialStatisticsAdapter


class MofAdapter(OfficialStatisticsAdapter):
    source_id = "mof"
    adapter_id = "mof-statistical-releases"
    version = "1.0.0"
    link_patterns = (
        r"(?:gks|yss|bgt)\.mof\.gov\.cn/.*/(?:t\d+_\d+\.htm|P\d+\.(?:pdf|xlsx?|csv))(?:$|\?)",
    )
