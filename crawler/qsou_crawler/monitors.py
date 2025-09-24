"""
Spidermon 监控套件

定义基本的开放/关闭监控：字段完整性、失败率、最小 item 数等。
"""

from spidermon import Monitor, MonitorSuite, monitors
from spidermon.contrib.monitors.mixins import StatsMonitorMixin, SaveReportMixin


REQUIRED_FIELDS = [
    "title",
    "content",
    "url",
]


class RequiredFieldsMonitor(Monitor, StatsMonitorMixin):
    @monitors.name("必须字段存在率")
    def test_required_fields(self):
        missing = self.data.stats.get("items_missing_required_fields", 0)
        total = self.data.stats.get("item_scraped_count", 0)
        # 允许小比例缺失
        assert missing <= max(1, 0.02 * max(1, total)), (
            f"缺少关键字段的items过多: {missing}/{total}"
        )


class FailureRateMonitor(Monitor, StatsMonitorMixin):
    @monitors.name("请求失败率")
    def test_failure_rate(self):
        total = self.data.stats.get("downloader/request_count", 0)
        failed = self.data.stats.get("downloader/exception_count", 0) + self.data.stats.get(
            "downloader/response_status_count/500", 0
        )
        # 失败率 < 10%
        if total:
            assert failed / total < 0.1, f"失败率过高: {failed}/{total}"


class ItemCountMonitor(Monitor, StatsMonitorMixin):
    @monitors.name("最小产出数量")
    def test_min_items(self):
        total = self.data.stats.get("item_scraped_count", 0)
        assert total >= 1, "本次抓取未产出有效 items"


class SpiderOpenMonitorSuite(MonitorSuite):
    monitors = []


class SpiderCloseMonitorSuite(MonitorSuite, SaveReportMixin):
    monitors = [
        RequiredFieldsMonitor,
        FailureRateMonitor,
        ItemCountMonitor,
    ]


