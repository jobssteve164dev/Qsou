"""
PluginSpiderLoader

实现基于目录与 entry point 的可插拔爬虫发现机制。
"""

import os
import sys
import logging
from typing import List

try:  # Python 3.8+
    from importlib import metadata as importlib_metadata  # type: ignore
except Exception:  # pragma: no cover
    import importlib_metadata  # type: ignore

from importlib import import_module
import pkgutil
from scrapy.spiderloader import SpiderLoader


class PluginSpiderLoader(SpiderLoader):
    """扩展 SpiderLoader，支持插件化发现。

    支持两类发现来源：
    - 目录扫描：settings["CRAWLER_PLUGIN_DIRS"] 下的所有包的 `spiders` 子模块
    - Entry points：group = settings["CRAWLER_PLUGIN_ENTRYPOINT_GROUP"] 的模块的 `spiders` 子模块
    """

    def __init__(self, settings):
        self._logger = logging.getLogger(self.__class__.__name__)

        # 先加载核心 spiders
        super().__init__(settings)

        # 然后增量加载插件 spiders（不修改 settings，直接导入模块）
        plugin_modules = []
        plugin_modules.extend(self._discover_from_dirs(settings))
        plugin_modules.extend(self._discover_from_entry_points(settings))

        for module_path in plugin_modules:
            try:
                module = import_module(module_path)
                # 需要扫描该包内的所有子模块（spiders/*.py）
                modules_to_scan = [module]
                if hasattr(module, "__path__"):
                    try:
                        for _, subname, _ in pkgutil.iter_modules(module.__path__):
                            try:
                                submod = import_module(f"{module_path}.{subname}")
                                modules_to_scan.append(submod)
                            except Exception as ie:
                                self._logger.warning(f"导入插件子模块失败: {module_path}.{subname} - {ie}")
                    except Exception as pe:
                        self._logger.debug(f"遍历插件包失败: {module_path} - {pe}")

                # 手动扫描并注册 Spider 子类（避免依赖私有实现差异）
                import inspect
                from scrapy.spiders import Spider
                registered = []
                for mod in modules_to_scan:
                    for _, obj in inspect.getmembers(mod, inspect.isclass):
                        if issubclass(obj, Spider) and obj is not Spider and getattr(obj, "name", None):
                            name = obj.name
                            # 覆盖策略：后加载的插件可覆盖同名蜘蛛（记录日志）
                            if name in getattr(self, "_spiders", {}):
                                self._logger.info(f"覆写已存在的蜘蛛: {name} <- {obj}")
                            self._spiders[name] = obj  # type: ignore[attr-defined]
                            registered.append(name)
                if registered:
                    self._logger.info(f"已注册插件蜘蛛: {registered} 来自 {module_path}")
            except Exception as e:
                self._logger.warning(f"加载插件蜘蛛失败: {module_path} - {e}")

    # ---------------------
    # 发现：目录扫描
    # ---------------------
    def _discover_from_dirs(self, settings) -> List[str]:
        plugin_dirs = settings.getlist("CRAWLER_PLUGIN_DIRS") or []
        if isinstance(plugin_dirs, str):
            plugin_dirs = [plugin_dirs]

        discovered: List[str] = []

        for d in plugin_dirs:
            abs_dir = self._resolve_dir(d)
            if not abs_dir or not os.path.isdir(abs_dir):
                continue

            # 确保可导入
            if abs_dir not in sys.path:
                sys.path.insert(0, abs_dir)

            try:
                # 遍历一级子目录作为插件包
                for entry in os.listdir(abs_dir):
                    pkg_path = os.path.join(abs_dir, entry)
                    spiders_path = os.path.join(pkg_path, "spiders")
                    if os.path.isdir(pkg_path) and os.path.isdir(spiders_path):
                        discovered.append(f"{entry}.spiders")
            except Exception as e:
                self._logger.warning(f"扫描插件目录失败: {abs_dir} - {e}")

        if discovered:
            self._logger.info(f"发现插件蜘蛛模块(目录)：{discovered}")
        return discovered

    # ---------------------
    # 发现：Entry Points
    # ---------------------
    def _discover_from_entry_points(self, settings) -> List[str]:
        group = settings.get("CRAWLER_PLUGIN_ENTRYPOINT_GROUP", "qsou_crawler.plugins")
        discovered: List[str] = []
        try:
            eps = importlib_metadata.entry_points()
            selected = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])

            for ep in selected:
                try:
                    # 优先使用 module 属性；否则从 value 里解析
                    module_path = getattr(ep, "module", None) or str(getattr(ep, "value", "")).split(":")[0]
                    if not module_path:
                        continue
                    if module_path.endswith(".spiders"):
                        discovered.append(module_path)
                    else:
                        discovered.append(f"{module_path}.spiders")
                except Exception as e:
                    self._logger.warning(f"解析 entry point 失败: {ep!r} - {e}")
        except Exception as e:
            self._logger.debug(f"读取 entry points 失败: {e}")

        if discovered:
            self._logger.info(f"发现插件蜘蛛模块(EntryPoints)：{discovered}")
        return discovered

    def _resolve_dir(self, path: str) -> str:
        """将相对路径解析为以 `crawler/` 为基准的绝对路径。"""
        if not path:
            return ""
        if os.path.isabs(path):
            return path
        # 当前文件路径：crawler/qsou_crawler/plugin_loader.py → 上一层为 crawler/
        crawler_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
        return os.path.join(crawler_root, path)


