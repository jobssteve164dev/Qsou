"""
同步管理器

负责：
- 数据源同步
- 增量更新调度
- 同步状态管理
- 冲突解决
"""
from typing import List, Dict, Any, Optional, Callable
from loguru import logger
from datetime import datetime, timedelta
import asyncio
import threading
import time
from enum import Enum

from incremental.change_detector import ChangeDetector
from incremental.incremental_processor import IncrementalProcessor
from config import config


class SyncStatus(Enum):
    """同步状态枚举"""
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"
    STOPPED = "stopped"


class SyncManager:
    """同步管理器"""
    
    def __init__(self,
                 change_detector: ChangeDetector = None,
                 incremental_processor: IncrementalProcessor = None):
        """
        初始化同步管理器
        
        Args:
            change_detector: 变更检测器
            incremental_processor: 增量处理器
        """
        self.change_detector = change_detector or ChangeDetector()
        self.incremental_processor = incremental_processor or IncrementalProcessor()
        
        # 同步状态
        self.status = SyncStatus.IDLE
        self.sync_thread = None
        self.stop_event = threading.Event()
        
        # 同步配置
        self.sync_interval = 30  # 默认30分钟
        self.max_batch_size = 1000
        self.retry_attempts = 3
        self.retry_delay = 60  # 重试延迟60秒
        
        # 数据源配置
        self.data_sources = {}
        self.sync_callbacks = {}
        
        # 同步统计
        self.sync_stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'last_sync_time': None,
            'next_sync_time': None,
            'total_documents_processed': 0,
            'sync_errors': []
        }
        
        # 冲突解决策略
        self.conflict_resolution = 'latest_wins'  # 'latest_wins', 'manual', 'skip'
        
        logger.info("同步管理器初始化完成")
    
    def register_data_source(self, 
                           source_name: str,
                           fetch_callback: Callable,
                           sync_interval: int = None,
                           enabled: bool = True) -> None:
        """
        注册数据源
        
        Args:
            source_name: 数据源名称
            fetch_callback: 数据获取回调函数
            sync_interval: 同步间隔（分钟）
            enabled: 是否启用
        """
        self.data_sources[source_name] = {
            'fetch_callback': fetch_callback,
            'sync_interval': sync_interval or self.sync_interval,
            'enabled': enabled,
            'last_sync': None,
            'next_sync': None,
            'error_count': 0,
            'total_documents': 0
        }
        
        logger.info(f"数据源已注册: {source_name}, 间隔: {sync_interval or self.sync_interval} 分钟")
    
    def start_sync(self, 
                  interval_minutes: int = None,
                  immediate: bool = True) -> bool:
        """
        启动同步
        
        Args:
            interval_minutes: 同步间隔（分钟）
            immediate: 是否立即执行一次同步
            
        Returns:
            启动是否成功
        """
        if self.status == SyncStatus.RUNNING:
            logger.warning("同步已在运行中")
            return False
        
        if interval_minutes:
            self.sync_interval = interval_minutes
        
        self.status = SyncStatus.RUNNING
        self.stop_event.clear()
        
        # 启动同步线程
        self.sync_thread = threading.Thread(
            target=self._sync_loop,
            args=(immediate,),
            daemon=True
        )
        self.sync_thread.start()
        
        logger.info(f"同步已启动，间隔: {self.sync_interval} 分钟")
        return True
    
    def stop_sync(self) -> bool:
        """停止同步"""
        if self.status != SyncStatus.RUNNING:
            logger.warning("同步未在运行")
            return False
        
        self.status = SyncStatus.STOPPED
        self.stop_event.set()
        
        # 等待同步线程结束
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join(timeout=30)
        
        logger.info("同步已停止")
        return True
    
    def pause_sync(self) -> bool:
        """暂停同步"""
        if self.status != SyncStatus.RUNNING:
            logger.warning("同步未在运行")
            return False
        
        self.status = SyncStatus.PAUSED
        logger.info("同步已暂停")
        return True
    
    def resume_sync(self) -> bool:
        """恢复同步"""
        if self.status != SyncStatus.PAUSED:
            logger.warning("同步未暂停")
            return False
        
        self.status = SyncStatus.RUNNING
        logger.info("同步已恢复")
        return True
    
    def _sync_loop(self, immediate: bool = True):
        """同步循环"""
        if immediate:
            self._execute_sync_cycle()
        
        while not self.stop_event.is_set():
            try:
                if self.status == SyncStatus.RUNNING:
                    # 检查是否需要同步
                    if self._should_sync():
                        self._execute_sync_cycle()
                
                # 等待下次检查
                if self.stop_event.wait(timeout=60):  # 每分钟检查一次
                    break
                    
            except Exception as e:
                logger.error(f"同步循环异常: {str(e)}")
                self.status = SyncStatus.ERROR
                self.sync_stats['sync_errors'].append({
                    'timestamp': datetime.now().isoformat(),
                    'error': str(e)
                })
                
                # 等待后重试
                if self.stop_event.wait(timeout=self.retry_delay):
                    break
                
                self.status = SyncStatus.RUNNING
    
    def _should_sync(self) -> bool:
        """检查是否应该执行同步"""
        now = datetime.now()
        
        # 检查全局同步时间
        if self.sync_stats['last_sync_time']:
            last_sync = datetime.fromisoformat(self.sync_stats['last_sync_time'])
            if now - last_sync < timedelta(minutes=self.sync_interval):
                return False
        
        # 检查各数据源是否需要同步
        for source_name, source_config in self.data_sources.items():
            if not source_config['enabled']:
                continue
            
            if source_config['last_sync']:
                last_sync = datetime.fromisoformat(source_config['last_sync'])
                interval = timedelta(minutes=source_config['sync_interval'])
                
                if now - last_sync >= interval:
                    return True
            else:
                # 从未同步过
                return True
        
        return False
    
    def _execute_sync_cycle(self):
        """执行同步周期"""
        start_time = datetime.now()
        
        logger.info("开始执行同步周期")
        
        try:
            self.sync_stats['total_syncs'] += 1
            
            total_processed = 0
            sync_results = {}
            
            # 同步各个数据源
            for source_name, source_config in self.data_sources.items():
                if not source_config['enabled']:
                    continue
                
                try:
                    result = self._sync_data_source(source_name, source_config)
                    sync_results[source_name] = result
                    
                    if result['success']:
                        total_processed += result.get('processed_count', 0)
                    
                except Exception as e:
                    logger.error(f"数据源同步失败: {source_name}, 错误: {str(e)}")
                    sync_results[source_name] = {
                        'success': False,
                        'error': str(e)
                    }
                    source_config['error_count'] += 1
            
            # 更新统计信息
            end_time = datetime.now()
            sync_time = (end_time - start_time).total_seconds()
            
            self.sync_stats['successful_syncs'] += 1
            self.sync_stats['last_sync_time'] = end_time.isoformat()
            self.sync_stats['next_sync_time'] = (end_time + timedelta(minutes=self.sync_interval)).isoformat()
            self.sync_stats['total_documents_processed'] += total_processed
            
            logger.info(f"同步周期完成，耗时: {sync_time:.2f}秒, 处理文档: {total_processed}")
            
        except Exception as e:
            logger.error(f"同步周期失败: {str(e)}")
            self.sync_stats['failed_syncs'] += 1
            self.sync_stats['sync_errors'].append({
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            })
    
    def _sync_data_source(self, 
                         source_name: str,
                         source_config: Dict[str, Any]) -> Dict[str, Any]:
        """同步单个数据源"""
        logger.info(f"开始同步数据源: {source_name}")
        
        start_time = datetime.now()
        
        try:
            # 获取数据
            fetch_callback = source_config['fetch_callback']
            new_documents = fetch_callback()
            
            if not new_documents:
                logger.info(f"数据源 {source_name} 没有新数据")
                source_config['last_sync'] = start_time.isoformat()
                return {'success': True, 'processed_count': 0}
            
            logger.info(f"数据源 {source_name} 获取到 {len(new_documents)} 个文档")
            
            # 处理增量变更
            processing_result = self.incremental_processor.process_incremental_changes(
                new_documents,
                time_threshold=self._get_last_sync_time(source_config),
                enable_full_processing=True
            )
            
            if processing_result['success']:
                # 更新数据源状态
                source_config['last_sync'] = start_time.isoformat()
                source_config['total_documents'] += processing_result['summary']['total_processed']
                source_config['error_count'] = 0  # 重置错误计数
                
                logger.info(f"数据源 {source_name} 同步成功: {processing_result['summary']}")
                
                return {
                    'success': True,
                    'processed_count': processing_result['summary']['total_processed'],
                    'processing_result': processing_result
                }
            else:
                logger.error(f"数据源 {source_name} 处理失败: {processing_result.get('error', '未知错误')}")
                return {
                    'success': False,
                    'error': processing_result.get('error', '处理失败')
                }
                
        except Exception as e:
            logger.error(f"数据源 {source_name} 同步异常: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _get_last_sync_time(self, source_config: Dict[str, Any]) -> Optional[datetime]:
        """获取上次同步时间"""
        last_sync = source_config.get('last_sync')
        if last_sync:
            try:
                return datetime.fromisoformat(last_sync)
            except Exception:
                pass
        
        # 如果没有上次同步时间，使用24小时前
        return datetime.now() - timedelta(hours=24)
    
    def trigger_manual_sync(self, 
                          source_names: List[str] = None,
                          force: bool = False) -> Dict[str, Any]:
        """
        手动触发同步
        
        Args:
            source_names: 指定数据源列表，None表示所有数据源
            force: 是否强制同步（忽略时间间隔）
            
        Returns:
            同步结果
        """
        if self.status == SyncStatus.RUNNING and not force:
            return {
                'success': False,
                'error': '自动同步正在运行中，请先停止或使用force=True'
            }
        
        logger.info("开始手动同步")
        
        start_time = datetime.now()
        results = {}
        
        # 确定要同步的数据源
        if source_names is None:
            sources_to_sync = self.data_sources.keys()
        else:
            sources_to_sync = [name for name in source_names if name in self.data_sources]
        
        # 执行同步
        for source_name in sources_to_sync:
            source_config = self.data_sources[source_name]
            
            if not source_config['enabled'] and not force:
                results[source_name] = {
                    'success': False,
                    'error': '数据源未启用'
                }
                continue
            
            try:
                result = self._sync_data_source(source_name, source_config)
                results[source_name] = result
                
            except Exception as e:
                results[source_name] = {
                    'success': False,
                    'error': str(e)
                }
        
        end_time = datetime.now()
        sync_time = (end_time - start_time).total_seconds()
        
        # 统计结果
        successful_sources = sum(1 for r in results.values() if r['success'])
        total_processed = sum(r.get('processed_count', 0) for r in results.values() if r['success'])
        
        logger.info(f"手动同步完成，耗时: {sync_time:.2f}秒, 成功: {successful_sources}/{len(sources_to_sync)}, 处理文档: {total_processed}")
        
        return {
            'success': successful_sources > 0,
            'sync_time': sync_time,
            'sources_synced': len(sources_to_sync),
            'successful_sources': successful_sources,
            'total_processed': total_processed,
            'results': results
        }
    
    def get_sync_status(self) -> Dict[str, Any]:
        """获取同步状态"""
        status_info = {
            'status': self.status.value,
            'sync_interval': self.sync_interval,
            'statistics': self.sync_stats.copy(),
            'data_sources': {}
        }
        
        # 添加数据源状态
        for source_name, source_config in self.data_sources.items():
            source_status = {
                'enabled': source_config['enabled'],
                'sync_interval': source_config['sync_interval'],
                'last_sync': source_config['last_sync'],
                'error_count': source_config['error_count'],
                'total_documents': source_config['total_documents']
            }
            
            # 计算下次同步时间
            if source_config['last_sync']:
                try:
                    last_sync = datetime.fromisoformat(source_config['last_sync'])
                    next_sync = last_sync + timedelta(minutes=source_config['sync_interval'])
                    source_status['next_sync'] = next_sync.isoformat()
                except Exception:
                    source_status['next_sync'] = None
            else:
                source_status['next_sync'] = None
            
            status_info['data_sources'][source_name] = source_status
        
        return status_info
    
    def configure_conflict_resolution(self, strategy: str):
        """
        配置冲突解决策略
        
        Args:
            strategy: 策略名称 ('latest_wins', 'manual', 'skip')
        """
        valid_strategies = ['latest_wins', 'manual', 'skip']
        
        if strategy not in valid_strategies:
            raise ValueError(f"无效的冲突解决策略: {strategy}, 可选: {valid_strategies}")
        
        self.conflict_resolution = strategy
        logger.info(f"冲突解决策略已设置为: {strategy}")
    
    def enable_data_source(self, source_name: str) -> bool:
        """启用数据源"""
        if source_name not in self.data_sources:
            logger.error(f"数据源不存在: {source_name}")
            return False
        
        self.data_sources[source_name]['enabled'] = True
        logger.info(f"数据源已启用: {source_name}")
        return True
    
    def disable_data_source(self, source_name: str) -> bool:
        """禁用数据源"""
        if source_name not in self.data_sources:
            logger.error(f"数据源不存在: {source_name}")
            return False
        
        self.data_sources[source_name]['enabled'] = False
        logger.info(f"数据源已禁用: {source_name}")
        return True
    
    def update_sync_interval(self, 
                           source_name: str = None,
                           interval_minutes: int = 30) -> bool:
        """
        更新同步间隔
        
        Args:
            source_name: 数据源名称，None表示全局间隔
            interval_minutes: 间隔时间（分钟）
        """
        if source_name is None:
            # 更新全局间隔
            self.sync_interval = interval_minutes
            logger.info(f"全局同步间隔已更新为: {interval_minutes} 分钟")
            return True
        
        if source_name not in self.data_sources:
            logger.error(f"数据源不存在: {source_name}")
            return False
        
        self.data_sources[source_name]['sync_interval'] = interval_minutes
        logger.info(f"数据源 {source_name} 同步间隔已更新为: {interval_minutes} 分钟")
        return True
    
    def get_sync_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取同步历史"""
        # 从变更检测器获取历史
        change_history = self.change_detector.get_change_history(limit)
        
        # 添加同步错误历史
        sync_errors = self.sync_stats['sync_errors'][-limit:]
        
        return {
            'change_history': change_history,
            'sync_errors': sync_errors
        }
    
    def cleanup(self):
        """清理资源"""
        try:
            # 停止同步
            self.stop_sync()
            
            # 清理组件资源
            if hasattr(self.incremental_processor, 'cleanup'):
                self.incremental_processor.cleanup()
            
            logger.info("同步管理器资源清理完成")
            
        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")


# 全局同步管理器实例
sync_manager = SyncManager()
