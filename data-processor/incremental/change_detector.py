"""
变更检测器

负责：
- 检测新增文档
- 检测文档更新
- 检测文档删除
- 变更记录管理
"""
import hashlib
from typing import List, Dict, Any, Set, Tuple, Optional
from loguru import logger
from datetime import datetime, timedelta
import json
import os

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("redis未安装，将使用文件存储")

from ..config import config


class ChangeDetector:
    """变更检测器"""
    
    def __init__(self, 
                 redis_url: str = None,
                 storage_path: str = "change_tracking"):
        """
        初始化变更检测器
        
        Args:
            redis_url: Redis连接URL
            storage_path: 本地存储路径
        """
        self.redis_url = redis_url or config.redis_url
        self.storage_path = storage_path
        self.redis_client = None
        
        # 初始化存储
        self._initialize_storage()
        
        # 变更类型
        self.CHANGE_TYPES = {
            'CREATED': 'created',
            'UPDATED': 'updated', 
            'DELETED': 'deleted',
            'UNCHANGED': 'unchanged'
        }
        
        # Redis键前缀
        self.HASH_KEY_PREFIX = "qsou:doc_hash:"
        self.TIMESTAMP_KEY_PREFIX = "qsou:doc_timestamp:"
        self.CHANGE_LOG_KEY = "qsou:change_log"
        
        logger.info("变更检测器初始化完成")
    
    def _initialize_storage(self):
        """初始化存储"""
        # 尝试连接Redis
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.from_url(self.redis_url)
                self.redis_client.ping()
                logger.info("Redis连接成功，使用Redis存储变更信息")
            except Exception as e:
                logger.warning(f"Redis连接失败: {str(e)}，使用本地文件存储")
                self.redis_client = None
        
        # 创建本地存储目录
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path)
    
    def detect_changes(self, 
                      current_documents: List[Dict[str, Any]],
                      previous_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        检测文档变更
        
        Args:
            current_documents: 当前文档列表
            previous_snapshot: 上次快照（可选）
            
        Returns:
            变更检测结果
        """
        logger.info(f"开始检测 {len(current_documents)} 个文档的变更")
        
        start_time = datetime.now()
        
        # 获取上次快照
        if previous_snapshot is None:
            previous_snapshot = self._load_snapshot()
        
        # 生成当前快照
        current_snapshot = self._generate_snapshot(current_documents)
        
        # 检测变更
        changes = self._compare_snapshots(previous_snapshot, current_snapshot)
        
        # 保存当前快照
        self._save_snapshot(current_snapshot)
        
        # 记录变更日志
        self._log_changes(changes, start_time)
        
        end_time = datetime.now()
        detection_time = (end_time - start_time).total_seconds()
        
        result = {
            'detection_time': detection_time,
            'total_documents': len(current_documents),
            'changes': changes,
            'summary': self._generate_change_summary(changes),
            'timestamp': end_time.isoformat()
        }
        
        logger.info(f"变更检测完成，耗时: {detection_time:.2f}秒")
        logger.info(f"变更摘要: {result['summary']}")
        
        return result
    
    def _generate_snapshot(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成文档快照"""
        snapshot = {}
        
        for doc in documents:
            doc_id = self._get_document_id(doc)
            doc_hash = self._calculate_document_hash(doc)
            doc_timestamp = self._get_document_timestamp(doc)
            
            snapshot[doc_id] = {
                'hash': doc_hash,
                'timestamp': doc_timestamp,
                'url': doc.get('url', ''),
                'title': doc.get('title', '')[:100],  # 只保存前100字符用于调试
                'source': doc.get('source', '')
            }
        
        return snapshot
    
    def _compare_snapshots(self, 
                          previous: Dict[str, Any], 
                          current: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """比较快照，检测变更"""
        changes = {
            'created': [],
            'updated': [],
            'deleted': [],
            'unchanged': []
        }
        
        previous_ids = set(previous.keys()) if previous else set()
        current_ids = set(current.keys())
        
        # 检测新增文档
        created_ids = current_ids - previous_ids
        for doc_id in created_ids:
            changes['created'].append({
                'id': doc_id,
                'type': self.CHANGE_TYPES['CREATED'],
                'current': current[doc_id],
                'previous': None
            })
        
        # 检测删除文档
        deleted_ids = previous_ids - current_ids
        for doc_id in deleted_ids:
            changes['deleted'].append({
                'id': doc_id,
                'type': self.CHANGE_TYPES['DELETED'],
                'current': None,
                'previous': previous[doc_id]
            })
        
        # 检测更新文档
        common_ids = previous_ids & current_ids
        for doc_id in common_ids:
            current_info = current[doc_id]
            previous_info = previous[doc_id]
            
            if current_info['hash'] != previous_info['hash']:
                changes['updated'].append({
                    'id': doc_id,
                    'type': self.CHANGE_TYPES['UPDATED'],
                    'current': current_info,
                    'previous': previous_info
                })
            else:
                changes['unchanged'].append({
                    'id': doc_id,
                    'type': self.CHANGE_TYPES['UNCHANGED'],
                    'current': current_info,
                    'previous': previous_info
                })
        
        return changes
    
    def _get_document_id(self, document: Dict[str, Any]) -> str:
        """获取文档ID"""
        # 优先使用已有的ID
        if '_id' in document:
            return document['_id']
        
        if 'content_hash' in document:
            return document['content_hash']
        
        # 使用URL作为ID
        url = document.get('url', '')
        if url:
            return hashlib.md5(url.encode('utf-8')).hexdigest()
        
        # 使用标题+时间生成ID
        title = document.get('title', '')
        publish_time = document.get('publish_time', '')
        id_string = f"{title}|{publish_time}"
        
        return hashlib.md5(id_string.encode('utf-8')).hexdigest()
    
    def _calculate_document_hash(self, document: Dict[str, Any]) -> str:
        """计算文档内容哈希"""
        # 选择用于哈希计算的字段
        hash_fields = ['title', 'content', 'url', 'publish_time']
        
        hash_content = []
        for field in hash_fields:
            value = document.get(field, '')
            if isinstance(value, str):
                hash_content.append(value)
            else:
                hash_content.append(str(value))
        
        content_string = '|'.join(hash_content)
        return hashlib.sha256(content_string.encode('utf-8')).hexdigest()
    
    def _get_document_timestamp(self, document: Dict[str, Any]) -> str:
        """获取文档时间戳"""
        # 优先使用发布时间
        publish_time = document.get('publish_time')
        if publish_time:
            if isinstance(publish_time, datetime):
                return publish_time.isoformat()
            elif isinstance(publish_time, str):
                return publish_time
        
        # 使用爬取时间
        crawl_time = document.get('crawl_time')
        if crawl_time:
            if isinstance(crawl_time, datetime):
                return crawl_time.isoformat()
            elif isinstance(crawl_time, str):
                return crawl_time
        
        # 使用当前时间
        return datetime.now().isoformat()
    
    def _load_snapshot(self) -> Dict[str, Any]:
        """加载上次快照"""
        if self.redis_client:
            return self._load_snapshot_from_redis()
        else:
            return self._load_snapshot_from_file()
    
    def _save_snapshot(self, snapshot: Dict[str, Any]):
        """保存快照"""
        if self.redis_client:
            self._save_snapshot_to_redis(snapshot)
        else:
            self._save_snapshot_to_file(snapshot)
    
    def _load_snapshot_from_redis(self) -> Dict[str, Any]:
        """从Redis加载快照"""
        try:
            snapshot_key = "qsou:document_snapshot"
            snapshot_data = self.redis_client.get(snapshot_key)
            
            if snapshot_data:
                return json.loads(snapshot_data)
            else:
                logger.info("Redis中没有找到上次快照")
                return {}
                
        except Exception as e:
            logger.error(f"从Redis加载快照失败: {str(e)}")
            return {}
    
    def _save_snapshot_to_redis(self, snapshot: Dict[str, Any]):
        """保存快照到Redis"""
        try:
            snapshot_key = "qsou:document_snapshot"
            snapshot_data = json.dumps(snapshot, ensure_ascii=False)
            
            # 设置过期时间为7天
            self.redis_client.setex(snapshot_key, 7 * 24 * 3600, snapshot_data)
            
            logger.debug(f"快照已保存到Redis，文档数: {len(snapshot)}")
            
        except Exception as e:
            logger.error(f"保存快照到Redis失败: {str(e)}")
    
    def _load_snapshot_from_file(self) -> Dict[str, Any]:
        """从文件加载快照"""
        snapshot_file = os.path.join(self.storage_path, "document_snapshot.json")
        
        try:
            if os.path.exists(snapshot_file):
                with open(snapshot_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.info("没有找到上次快照文件")
                return {}
                
        except Exception as e:
            logger.error(f"从文件加载快照失败: {str(e)}")
            return {}
    
    def _save_snapshot_to_file(self, snapshot: Dict[str, Any]):
        """保存快照到文件"""
        snapshot_file = os.path.join(self.storage_path, "document_snapshot.json")
        
        try:
            with open(snapshot_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"快照已保存到文件，文档数: {len(snapshot)}")
            
        except Exception as e:
            logger.error(f"保存快照到文件失败: {str(e)}")
    
    def _log_changes(self, changes: Dict[str, List[Dict[str, Any]]], start_time: datetime):
        """记录变更日志"""
        change_log = {
            'timestamp': start_time.isoformat(),
            'summary': self._generate_change_summary(changes),
            'details': {
                'created_count': len(changes['created']),
                'updated_count': len(changes['updated']),
                'deleted_count': len(changes['deleted']),
                'unchanged_count': len(changes['unchanged'])
            }
        }
        
        if self.redis_client:
            self._log_changes_to_redis(change_log)
        else:
            self._log_changes_to_file(change_log)
    
    def _log_changes_to_redis(self, change_log: Dict[str, Any]):
        """记录变更日志到Redis"""
        try:
            # 添加到变更日志列表
            log_data = json.dumps(change_log, ensure_ascii=False)
            self.redis_client.lpush(self.CHANGE_LOG_KEY, log_data)
            
            # 只保留最近100条记录
            self.redis_client.ltrim(self.CHANGE_LOG_KEY, 0, 99)
            
        except Exception as e:
            logger.error(f"记录变更日志到Redis失败: {str(e)}")
    
    def _log_changes_to_file(self, change_log: Dict[str, Any]):
        """记录变更日志到文件"""
        log_file = os.path.join(self.storage_path, "change_log.jsonl")
        
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(change_log, ensure_ascii=False) + '\n')
            
        except Exception as e:
            logger.error(f"记录变更日志到文件失败: {str(e)}")
    
    def _generate_change_summary(self, changes: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
        """生成变更摘要"""
        return {
            'created': len(changes['created']),
            'updated': len(changes['updated']),
            'deleted': len(changes['deleted']),
            'unchanged': len(changes['unchanged']),
            'total_changes': len(changes['created']) + len(changes['updated']) + len(changes['deleted'])
        }
    
    def get_change_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取变更历史"""
        if self.redis_client:
            return self._get_change_history_from_redis(limit)
        else:
            return self._get_change_history_from_file(limit)
    
    def _get_change_history_from_redis(self, limit: int) -> List[Dict[str, Any]]:
        """从Redis获取变更历史"""
        try:
            log_entries = self.redis_client.lrange(self.CHANGE_LOG_KEY, 0, limit - 1)
            
            history = []
            for entry in log_entries:
                try:
                    log_data = json.loads(entry)
                    history.append(log_data)
                except json.JSONDecodeError:
                    continue
            
            return history
            
        except Exception as e:
            logger.error(f"从Redis获取变更历史失败: {str(e)}")
            return []
    
    def _get_change_history_from_file(self, limit: int) -> List[Dict[str, Any]]:
        """从文件获取变更历史"""
        log_file = os.path.join(self.storage_path, "change_log.jsonl")
        
        try:
            if not os.path.exists(log_file):
                return []
            
            history = []
            with open(log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
                # 取最后limit行
                for line in lines[-limit:]:
                    try:
                        log_data = json.loads(line.strip())
                        history.append(log_data)
                    except json.JSONDecodeError:
                        continue
            
            # 按时间倒序排列
            history.reverse()
            return history
            
        except Exception as e:
            logger.error(f"从文件获取变更历史失败: {str(e)}")
            return []
    
    def detect_incremental_changes(self, 
                                 new_documents: List[Dict[str, Any]],
                                 time_threshold: Optional[datetime] = None) -> Dict[str, Any]:
        """
        检测增量变更（基于时间阈值）
        
        Args:
            new_documents: 新文档列表
            time_threshold: 时间阈值，只处理此时间之后的文档
            
        Returns:
            增量变更结果
        """
        if time_threshold is None:
            # 默认处理最近24小时的文档
            time_threshold = datetime.now() - timedelta(hours=24)
        
        logger.info(f"检测增量变更，时间阈值: {time_threshold}")
        
        # 过滤出时间阈值之后的文档
        recent_documents = []
        for doc in new_documents:
            doc_time = self._parse_document_time(doc)
            if doc_time and doc_time > time_threshold:
                recent_documents.append(doc)
        
        logger.info(f"时间过滤后的文档数: {len(recent_documents)}")
        
        # 对过滤后的文档进行变更检测
        return self.detect_changes(recent_documents)
    
    def _parse_document_time(self, document: Dict[str, Any]) -> Optional[datetime]:
        """解析文档时间"""
        time_fields = ['publish_time', 'crawl_time', 'index_time']
        
        for field in time_fields:
            time_value = document.get(field)
            if time_value:
                try:
                    if isinstance(time_value, datetime):
                        return time_value
                    elif isinstance(time_value, str):
                        # 尝试解析ISO格式时间
                        return datetime.fromisoformat(time_value.replace('Z', '+00:00'))
                except Exception:
                    continue
        
        return None
    
    def clear_change_history(self):
        """清空变更历史"""
        if self.redis_client:
            try:
                self.redis_client.delete(self.CHANGE_LOG_KEY)
                logger.info("Redis变更历史已清空")
            except Exception as e:
                logger.error(f"清空Redis变更历史失败: {str(e)}")
        
        # 清空文件历史
        log_file = os.path.join(self.storage_path, "change_log.jsonl")
        try:
            if os.path.exists(log_file):
                os.remove(log_file)
                logger.info("文件变更历史已清空")
        except Exception as e:
            logger.error(f"清空文件变更历史失败: {str(e)}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            'storage_type': 'redis' if self.redis_client else 'file',
            'redis_available': self.redis_client is not None,
            'storage_path': self.storage_path
        }
        
        # 获取变更历史统计
        history = self.get_change_history(100)  # 获取最近100条记录
        
        if history:
            total_created = sum(h['summary']['created'] for h in history)
            total_updated = sum(h['summary']['updated'] for h in history)
            total_deleted = sum(h['summary']['deleted'] for h in history)
            
            stats.update({
                'history_records': len(history),
                'total_created': total_created,
                'total_updated': total_updated,
                'total_deleted': total_deleted,
                'last_check': history[0]['timestamp'] if history else None
            })
        else:
            stats.update({
                'history_records': 0,
                'total_created': 0,
                'total_updated': 0,
                'total_deleted': 0,
                'last_check': None
            })
        
        return stats
