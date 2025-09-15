"""
去重处理器

负责检测和处理重复内容：
- 基于内容哈希的精确去重
- 基于相似度的近似去重
- 增量去重检查
- 重复内容合并策略
"""
import hashlib
from typing import Dict, Any, List, Set, Tuple, Optional
from loguru import logger
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from datetime import datetime
import redis
from ..config import config


class Deduplicator:
    """去重处理器"""
    
    def __init__(self):
        # 连接Redis用于存储哈希值
        try:
            self.redis_client = redis.from_url(config.redis_url)
            self.redis_client.ping()
            logger.info("Redis连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败: {str(e)}，将使用内存存储")
            self.redis_client = None
        
        # 内存中的哈希缓存（备用方案）
        self.hash_cache: Set[str] = set()
        
        # TF-IDF向量化器用于相似度计算
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=None,  # 中文停用词需要自定义
            ngram_range=(1, 2)
        )
        
        # 相似度阈值
        self.similarity_threshold = config.similarity_threshold
        
        # Redis键前缀
        self.hash_key_prefix = "qsou:hash:"
        self.similarity_key_prefix = "qsou:similarity:"
    
    def deduplicate_documents(self, documents: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        对文档列表进行去重
        
        Args:
            documents: 待去重的文档列表
            
        Returns:
            (unique_documents, duplicate_documents): 去重后的文档和重复文档
        """
        logger.info(f"开始对 {len(documents)} 个文档进行去重处理")
        
        unique_documents = []
        duplicate_documents = []
        
        # 第一步：基于内容哈希的精确去重
        hash_filtered_docs, hash_duplicates = self._hash_based_deduplication(documents)
        duplicate_documents.extend(hash_duplicates)
        
        logger.info(f"哈希去重完成，剩余 {len(hash_filtered_docs)} 个文档")
        
        # 第二步：基于相似度的近似去重
        if len(hash_filtered_docs) > 1:
            similarity_filtered_docs, similarity_duplicates = self._similarity_based_deduplication(hash_filtered_docs)
            unique_documents.extend(similarity_filtered_docs)
            duplicate_documents.extend(similarity_duplicates)
        else:
            unique_documents.extend(hash_filtered_docs)
        
        logger.info(f"去重完成，唯一文档: {len(unique_documents)}, 重复文档: {len(duplicate_documents)}")
        
        return unique_documents, duplicate_documents
    
    def _hash_based_deduplication(self, documents: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """基于内容哈希的精确去重"""
        unique_docs = []
        duplicate_docs = []
        current_hashes = set()
        
        for doc in documents:
            content_hash = self._get_content_hash(doc)
            
            # 检查是否已存在
            if self._is_hash_exists(content_hash) or content_hash in current_hashes:
                duplicate_docs.append(doc)
                logger.debug(f"发现重复文档 (哈希): {doc.get('title', 'Unknown')[:50]}...")
            else:
                unique_docs.append(doc)
                current_hashes.add(content_hash)
                # 存储哈希值
                self._store_hash(content_hash)
        
        return unique_docs, duplicate_docs
    
    def _similarity_based_deduplication(self, documents: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """基于相似度的近似去重"""
        if len(documents) <= 1:
            return documents, []
        
        unique_docs = []
        duplicate_docs = []
        
        try:
            # 提取文本内容
            texts = []
            for doc in documents:
                title = doc.get('title', '')
                content = doc.get('content', '')
                text = f"{title} {content}"
                texts.append(text)
            
            # 计算TF-IDF向量
            tfidf_matrix = self.vectorizer.fit_transform(texts)
            
            # 计算相似度矩阵
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # 标记重复文档
            processed = set()
            
            for i in range(len(documents)):
                if i in processed:
                    continue
                
                unique_docs.append(documents[i])
                processed.add(i)
                
                # 查找与当前文档相似的其他文档
                for j in range(i + 1, len(documents)):
                    if j in processed:
                        continue
                    
                    similarity = similarity_matrix[i][j]
                    if similarity >= self.similarity_threshold:
                        # 选择质量更高的文档保留
                        if self._should_keep_document(documents[i], documents[j]):
                            duplicate_docs.append(documents[j])
                        else:
                            # 替换为质量更高的文档
                            unique_docs[-1] = documents[j]
                            duplicate_docs.append(documents[i])
                        
                        processed.add(j)
                        logger.debug(f"发现相似文档 (相似度: {similarity:.3f}): {documents[j].get('title', 'Unknown')[:50]}...")
            
        except Exception as e:
            logger.error(f"相似度去重失败: {str(e)}")
            # 如果相似度计算失败，返回所有文档作为唯一文档
            return documents, []
        
        return unique_docs, duplicate_docs
    
    def _get_content_hash(self, document: Dict[str, Any]) -> str:
        """获取文档内容哈希"""
        # 如果文档已有哈希值，直接使用
        if 'content_hash' in document:
            return document['content_hash']
        
        # 否则生成新的哈希值
        title = document.get('title', '')
        content = document.get('content', '')
        url = document.get('url', '')
        
        # 组合关键内容
        key_content = f"{title}|{content[:500]}|{url}"
        
        # 生成SHA256哈希
        return hashlib.sha256(key_content.encode('utf-8')).hexdigest()
    
    def _is_hash_exists(self, content_hash: str) -> bool:
        """检查哈希值是否已存在"""
        if self.redis_client:
            try:
                key = f"{self.hash_key_prefix}{content_hash}"
                return self.redis_client.exists(key) > 0
            except Exception as e:
                logger.warning(f"Redis查询失败: {str(e)}")
        
        # 使用内存缓存
        return content_hash in self.hash_cache
    
    def _store_hash(self, content_hash: str, ttl: int = 86400 * 30) -> None:
        """存储哈希值（30天过期）"""
        if self.redis_client:
            try:
                key = f"{self.hash_key_prefix}{content_hash}"
                self.redis_client.setex(key, ttl, "1")
                return
            except Exception as e:
                logger.warning(f"Redis存储失败: {str(e)}")
        
        # 使用内存缓存
        self.hash_cache.add(content_hash)
    
    def _should_keep_document(self, doc1: Dict[str, Any], doc2: Dict[str, Any]) -> bool:
        """
        判断应该保留哪个文档（返回True表示保留doc1）
        
        优先级：
        1. 内容更完整（字数更多）
        2. 发布时间更新
        3. 重要性评分更高
        """
        # 比较内容完整性
        word_count1 = doc1.get('word_count', 0)
        word_count2 = doc2.get('word_count', 0)
        
        if abs(word_count1 - word_count2) > 50:  # 字数差异超过50
            return word_count1 > word_count2
        
        # 比较发布时间
        try:
            time1 = doc1.get('publish_time', '')
            time2 = doc2.get('publish_time', '')
            
            if time1 and time2:
                # 简单的时间比较（实际应该解析为datetime对象）
                if time1 != time2:
                    return time1 > time2
        except Exception:
            pass
        
        # 比较重要性评分
        score1 = doc1.get('importance_score', 0.5)
        score2 = doc2.get('importance_score', 0.5)
        
        return score1 >= score2
    
    def check_duplicate_by_url(self, url: str) -> bool:
        """根据URL检查是否重复"""
        if not url:
            return False
        
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        
        if self.redis_client:
            try:
                key = f"qsou:url:{url_hash}"
                return self.redis_client.exists(key) > 0
            except Exception:
                pass
        
        return False
    
    def mark_url_processed(self, url: str, ttl: int = 86400 * 7) -> None:
        """标记URL已处理（7天过期）"""
        if not url:
            return
        
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        
        if self.redis_client:
            try:
                key = f"qsou:url:{url_hash}"
                self.redis_client.setex(key, ttl, "1")
            except Exception as e:
                logger.warning(f"URL标记失败: {str(e)}")
    
    def get_deduplication_stats(self) -> Dict[str, int]:
        """获取去重统计信息"""
        stats = {
            'total_hashes': 0,
            'memory_cache_size': len(self.hash_cache)
        }
        
        if self.redis_client:
            try:
                # 统计Redis中的哈希数量
                pattern = f"{self.hash_key_prefix}*"
                keys = self.redis_client.keys(pattern)
                stats['total_hashes'] = len(keys)
            except Exception as e:
                logger.warning(f"统计信息获取失败: {str(e)}")
        
        return stats
    
    def clear_cache(self, older_than_days: int = 30) -> None:
        """清理过期的缓存数据"""
        if self.redis_client:
            try:
                # Redis的TTL会自动清理过期数据
                logger.info("Redis缓存由TTL自动管理")
            except Exception as e:
                logger.warning(f"缓存清理失败: {str(e)}")
        
        # 清理内存缓存（简单清空）
        if len(self.hash_cache) > 10000:  # 如果缓存过大，清空
            self.hash_cache.clear()
            logger.info("内存缓存已清理")
