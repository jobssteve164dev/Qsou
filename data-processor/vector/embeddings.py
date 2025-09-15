"""
文本向量化器

支持多种向量化方法：
- Sentence Transformers (多语言BERT)
- 中文金融BERT模型
- TF-IDF向量化
- Word2Vec向量化
"""
import numpy as np
from typing import List, Dict, Any, Optional, Union, Tuple
from loguru import logger
import hashlib
import pickle
import os
from datetime import datetime

try:
    from sentence_transformers import SentenceTransformer
    import torch
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers未安装，将使用TF-IDF方法")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn未安装，向量化功能受限")

from ..config import config


class TextEmbedder:
    """文本向量化器"""
    
    def __init__(self, 
                 model_type: str = "sentence_transformers",
                 model_name: str = None,
                 cache_embeddings: bool = True):
        """
        初始化文本向量化器
        
        Args:
            model_type: 模型类型 ("sentence_transformers", "tfidf", "bert")
            model_name: 模型名称
            cache_embeddings: 是否缓存向量
        """
        self.model_type = model_type
        self.model_name = model_name or self._get_default_model_name()
        self.cache_embeddings = cache_embeddings
        self.model = None
        
        # 向量缓存
        self.embedding_cache = {}
        self.cache_file = "embeddings_cache.pkl"
        
        # 向量维度
        self.vector_dimension = config.vector_dimension
        
        # 初始化模型
        self._initialize_model()
        
        # 加载缓存
        if cache_embeddings:
            self._load_cache()
        
        logger.info(f"文本向量化器初始化完成: {model_type} - {self.model_name}")
    
    def _get_default_model_name(self) -> str:
        """获取默认模型名称"""
        if self.model_type == "sentence_transformers":
            # 多语言模型，支持中文
            return "paraphrase-multilingual-MiniLM-L12-v2"
        elif self.model_type == "bert":
            # 中文BERT模型
            return "bert-base-chinese"
        elif self.model_type == "tfidf":
            return "tfidf_vectorizer"
        else:
            return "default"
    
    def _initialize_model(self):
        """初始化向量化模型"""
        try:
            if self.model_type == "sentence_transformers" and SENTENCE_TRANSFORMERS_AVAILABLE:
                self._initialize_sentence_transformers()
            elif self.model_type == "tfidf" and SKLEARN_AVAILABLE:
                self._initialize_tfidf()
            elif self.model_type == "bert" and SENTENCE_TRANSFORMERS_AVAILABLE:
                self._initialize_bert()
            else:
                logger.warning(f"模型类型 {self.model_type} 不可用，回退到TF-IDF")
                self.model_type = "tfidf"
                self._initialize_tfidf()
                
        except Exception as e:
            logger.error(f"模型初始化失败: {str(e)}")
            # 回退到简单的TF-IDF
            self.model_type = "tfidf"
            self._initialize_tfidf()
    
    def _initialize_sentence_transformers(self):
        """初始化Sentence Transformers模型"""
        try:
            logger.info(f"加载Sentence Transformers模型: {self.model_name}")
            
            # 常用的多语言模型
            available_models = [
                "paraphrase-multilingual-MiniLM-L12-v2",  # 384维，支持50+语言
                "distiluse-base-multilingual-cased",       # 512维，多语言
                "paraphrase-MiniLM-L6-v2",                # 384维，英文为主
                "all-MiniLM-L6-v2"                        # 384维，英文
            ]
            
            # 尝试加载指定模型
            try:
                self.model = SentenceTransformer(self.model_name)
                self.vector_dimension = self.model.get_sentence_embedding_dimension()
                logger.info(f"成功加载模型 {self.model_name}，向量维度: {self.vector_dimension}")
            except Exception as e:
                logger.warning(f"加载模型 {self.model_name} 失败: {str(e)}")
                
                # 尝试备选模型
                for backup_model in available_models:
                    try:
                        logger.info(f"尝试备选模型: {backup_model}")
                        self.model = SentenceTransformer(backup_model)
                        self.model_name = backup_model
                        self.vector_dimension = self.model.get_sentence_embedding_dimension()
                        logger.info(f"成功加载备选模型 {backup_model}，向量维度: {self.vector_dimension}")
                        break
                    except Exception as e2:
                        logger.warning(f"备选模型 {backup_model} 也失败: {str(e2)}")
                        continue
                
                if self.model is None:
                    raise Exception("所有Sentence Transformers模型都加载失败")
                    
        except Exception as e:
            logger.error(f"Sentence Transformers初始化失败: {str(e)}")
            raise
    
    def _initialize_tfidf(self):
        """初始化TF-IDF向量化器"""
        try:
            # 创建TF-IDF向量化器
            self.tfidf_vectorizer = TfidfVectorizer(
                max_features=self.vector_dimension,
                stop_words=None,  # 中文停用词需要自定义
                ngram_range=(1, 2),
                min_df=2,
                max_df=0.95
            )
            
            # 创建SVD降维器（如果需要）
            self.svd_reducer = TruncatedSVD(
                n_components=min(self.vector_dimension, 300),
                random_state=42
            )
            
            self.model = "tfidf_initialized"
            logger.info(f"TF-IDF向量化器初始化完成，目标维度: {self.vector_dimension}")
            
        except Exception as e:
            logger.error(f"TF-IDF初始化失败: {str(e)}")
            raise
    
    def _initialize_bert(self):
        """初始化BERT模型"""
        try:
            # 使用中文BERT模型
            chinese_bert_models = [
                "uer/sbert-base-chinese-nli",
                "shibing624/text2vec-base-chinese", 
                "GanymedeNil/text2vec-large-chinese"
            ]
            
            for model_name in chinese_bert_models:
                try:
                    logger.info(f"尝试加载中文BERT模型: {model_name}")
                    self.model = SentenceTransformer(model_name)
                    self.model_name = model_name
                    self.vector_dimension = self.model.get_sentence_embedding_dimension()
                    logger.info(f"成功加载中文BERT模型 {model_name}，向量维度: {self.vector_dimension}")
                    return
                except Exception as e:
                    logger.warning(f"中文BERT模型 {model_name} 加载失败: {str(e)}")
                    continue
            
            # 如果中文模型都失败，回退到多语言模型
            logger.info("回退到多语言Sentence Transformers模型")
            self._initialize_sentence_transformers()
            
        except Exception as e:
            logger.error(f"BERT模型初始化失败: {str(e)}")
            raise
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        将单个文本转换为向量
        
        Args:
            text: 输入文本
            
        Returns:
            文本向量
        """
        if not text or not isinstance(text, str):
            return np.zeros(self.vector_dimension)
        
        # 检查缓存
        if self.cache_embeddings:
            text_hash = self._get_text_hash(text)
            if text_hash in self.embedding_cache:
                return self.embedding_cache[text_hash]
        
        try:
            # 预处理文本
            processed_text = self._preprocess_text(text)
            
            # 生成向量
            if self.model_type in ["sentence_transformers", "bert"] and self.model:
                vector = self._embed_with_transformers(processed_text)
            elif self.model_type == "tfidf":
                vector = self._embed_with_tfidf(processed_text)
            else:
                # 备用方案：简单的字符级向量
                vector = self._embed_with_simple_method(processed_text)
            
            # 缓存结果
            if self.cache_embeddings:
                self.embedding_cache[text_hash] = vector
            
            return vector
            
        except Exception as e:
            logger.error(f"文本向量化失败: {str(e)}")
            return np.zeros(self.vector_dimension)
    
    def _embed_with_transformers(self, text: str) -> np.ndarray:
        """使用Transformers模型生成向量"""
        try:
            # 限制文本长度
            max_length = 512
            if len(text) > max_length:
                text = text[:max_length]
            
            # 生成向量
            embedding = self.model.encode(text, convert_to_numpy=True)
            
            # 确保向量维度正确
            if len(embedding) != self.vector_dimension:
                # 如果维度不匹配，进行调整
                if len(embedding) > self.vector_dimension:
                    embedding = embedding[:self.vector_dimension]
                else:
                    # 填充零值
                    padding = np.zeros(self.vector_dimension - len(embedding))
                    embedding = np.concatenate([embedding, padding])
            
            return embedding.astype(np.float32)
            
        except Exception as e:
            logger.error(f"Transformers向量化失败: {str(e)}")
            return np.zeros(self.vector_dimension)
    
    def _embed_with_tfidf(self, text: str) -> np.ndarray:
        """使用TF-IDF生成向量"""
        try:
            # 如果是第一次使用，需要先训练
            if not hasattr(self, '_tfidf_fitted'):
                logger.warning("TF-IDF模型未训练，使用单文档训练（不推荐）")
                self.tfidf_vectorizer.fit([text])
                self._tfidf_fitted = True
            
            # 生成TF-IDF向量
            tfidf_vector = self.tfidf_vectorizer.transform([text])
            
            # 转换为密集向量
            dense_vector = tfidf_vector.toarray()[0]
            
            # 如果需要降维
            if len(dense_vector) > self.vector_dimension:
                if not hasattr(self, '_svd_fitted'):
                    self.svd_reducer.fit(tfidf_vector)
                    self._svd_fitted = True
                dense_vector = self.svd_reducer.transform(tfidf_vector)[0]
            
            # 调整维度
            if len(dense_vector) < self.vector_dimension:
                padding = np.zeros(self.vector_dimension - len(dense_vector))
                dense_vector = np.concatenate([dense_vector, padding])
            elif len(dense_vector) > self.vector_dimension:
                dense_vector = dense_vector[:self.vector_dimension]
            
            return dense_vector.astype(np.float32)
            
        except Exception as e:
            logger.error(f"TF-IDF向量化失败: {str(e)}")
            return np.zeros(self.vector_dimension)
    
    def _embed_with_simple_method(self, text: str) -> np.ndarray:
        """简单的向量化方法（备用）"""
        try:
            # 基于字符频率的简单向量化
            char_counts = {}
            for char in text:
                if '\u4e00' <= char <= '\u9fff':  # 中文字符
                    char_counts[char] = char_counts.get(char, 0) + 1
            
            # 创建向量
            vector = np.zeros(self.vector_dimension)
            
            # 使用字符哈希填充向量
            for char, count in char_counts.items():
                char_hash = hash(char) % self.vector_dimension
                vector[char_hash] += count
            
            # 归一化
            if np.sum(vector) > 0:
                vector = vector / np.linalg.norm(vector)
            
            return vector.astype(np.float32)
            
        except Exception as e:
            logger.error(f"简单向量化失败: {str(e)}")
            return np.zeros(self.vector_dimension)
    
    def embed_batch(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        批量文本向量化
        
        Args:
            texts: 文本列表
            batch_size: 批处理大小
            
        Returns:
            向量矩阵 (n_texts, vector_dimension)
        """
        if not texts:
            return np.empty((0, self.vector_dimension))
        
        logger.info(f"开始批量向量化 {len(texts)} 个文本")
        
        all_vectors = []
        
        # 分批处理
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            try:
                if self.model_type in ["sentence_transformers", "bert"] and self.model:
                    # 使用模型批量处理
                    batch_vectors = self._embed_batch_with_transformers(batch_texts)
                else:
                    # 逐个处理
                    batch_vectors = np.array([self.embed_text(text) for text in batch_texts])
                
                all_vectors.append(batch_vectors)
                
                if (i + batch_size) % (batch_size * 10) == 0:
                    logger.info(f"已处理 {min(i + batch_size, len(texts))}/{len(texts)} 个文本")
                    
            except Exception as e:
                logger.error(f"批次 {i}-{i+batch_size} 向量化失败: {str(e)}")
                # 使用零向量填充
                batch_vectors = np.zeros((len(batch_texts), self.vector_dimension))
                all_vectors.append(batch_vectors)
        
        # 合并所有向量
        result = np.vstack(all_vectors) if all_vectors else np.empty((0, self.vector_dimension))
        
        logger.info(f"批量向量化完成，生成 {result.shape[0]} 个向量")
        
        return result
    
    def _embed_batch_with_transformers(self, texts: List[str]) -> np.ndarray:
        """使用Transformers模型批量生成向量"""
        try:
            # 预处理文本
            processed_texts = [self._preprocess_text(text) for text in texts]
            
            # 批量生成向量
            embeddings = self.model.encode(processed_texts, convert_to_numpy=True, batch_size=len(texts))
            
            # 确保维度正确
            if embeddings.shape[1] != self.vector_dimension:
                if embeddings.shape[1] > self.vector_dimension:
                    embeddings = embeddings[:, :self.vector_dimension]
                else:
                    padding = np.zeros((embeddings.shape[0], self.vector_dimension - embeddings.shape[1]))
                    embeddings = np.concatenate([embeddings, padding], axis=1)
            
            return embeddings.astype(np.float32)
            
        except Exception as e:
            logger.error(f"批量Transformers向量化失败: {str(e)}")
            return np.zeros((len(texts), self.vector_dimension))
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本"""
        if not text:
            return ""
        
        # 移除多余空白
        text = ' '.join(text.split())
        
        # 限制长度
        max_length = 512
        if len(text) > max_length:
            text = text[:max_length]
        
        return text
    
    def _get_text_hash(self, text: str) -> str:
        """获取文本哈希值"""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def fit_tfidf(self, texts: List[str]):
        """训练TF-IDF模型"""
        if self.model_type != "tfidf":
            logger.warning("当前不是TF-IDF模型，跳过训练")
            return
        
        try:
            logger.info(f"开始训练TF-IDF模型，文档数: {len(texts)}")
            
            # 预处理文本
            processed_texts = [self._preprocess_text(text) for text in texts if text]
            
            # 训练TF-IDF
            self.tfidf_vectorizer.fit(processed_texts)
            self._tfidf_fitted = True
            
            # 如果需要降维，训练SVD
            if self.tfidf_vectorizer.max_features > self.vector_dimension:
                tfidf_matrix = self.tfidf_vectorizer.transform(processed_texts[:1000])  # 使用部分数据训练SVD
                self.svd_reducer.fit(tfidf_matrix)
                self._svd_fitted = True
            
            logger.info("TF-IDF模型训练完成")
            
        except Exception as e:
            logger.error(f"TF-IDF训练失败: {str(e)}")
    
    def save_model(self, save_path: str):
        """保存模型"""
        try:
            model_info = {
                'model_type': self.model_type,
                'model_name': self.model_name,
                'vector_dimension': self.vector_dimension,
                'cache_size': len(self.embedding_cache)
            }
            
            # 保存TF-IDF模型
            if self.model_type == "tfidf" and hasattr(self, '_tfidf_fitted'):
                joblib.dump(self.tfidf_vectorizer, f"{save_path}_tfidf.pkl")
                if hasattr(self, '_svd_fitted'):
                    joblib.dump(self.svd_reducer, f"{save_path}_svd.pkl")
            
            # 保存缓存
            if self.cache_embeddings and self.embedding_cache:
                with open(f"{save_path}_cache.pkl", 'wb') as f:
                    pickle.dump(self.embedding_cache, f)
            
            # 保存模型信息
            with open(f"{save_path}_info.json", 'w', encoding='utf-8') as f:
                import json
                json.dump(model_info, f, ensure_ascii=False, indent=2)
            
            logger.info(f"模型已保存到: {save_path}")
            
        except Exception as e:
            logger.error(f"模型保存失败: {str(e)}")
    
    def _load_cache(self):
        """加载向量缓存"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'rb') as f:
                    self.embedding_cache = pickle.load(f)
                logger.info(f"加载向量缓存，缓存大小: {len(self.embedding_cache)}")
        except Exception as e:
            logger.warning(f"缓存加载失败: {str(e)}")
            self.embedding_cache = {}
    
    def _save_cache(self):
        """保存向量缓存"""
        try:
            if self.cache_embeddings and self.embedding_cache:
                with open(self.cache_file, 'wb') as f:
                    pickle.dump(self.embedding_cache, f)
                logger.info(f"向量缓存已保存，缓存大小: {len(self.embedding_cache)}")
        except Exception as e:
            logger.warning(f"缓存保存失败: {str(e)}")
    
    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        info = {
            'model_type': self.model_type,
            'model_name': self.model_name,
            'vector_dimension': self.vector_dimension,
            'cache_enabled': self.cache_embeddings,
            'cache_size': len(self.embedding_cache),
            'available_backends': {
                'sentence_transformers': SENTENCE_TRANSFORMERS_AVAILABLE,
                'sklearn': SKLEARN_AVAILABLE
            }
        }
        
        if self.model_type in ["sentence_transformers", "bert"] and self.model:
            info['model_max_seq_length'] = getattr(self.model, 'max_seq_length', 'unknown')
        
        return info
    
    def cleanup(self):
        """清理资源"""
        try:
            # 保存缓存
            self._save_cache()
            
            # 清理模型
            if hasattr(self, 'model') and self.model:
                del self.model
            
            logger.info("文本向量化器资源清理完成")
            
        except Exception as e:
            logger.error(f"资源清理失败: {str(e)}")
