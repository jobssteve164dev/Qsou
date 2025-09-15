"""
NLP处理器统一接口

整合所有NLP功能：
- 中文分词
- 实体识别
- 情感分析
- 文本分类
- 关键词提取
"""
from typing import Dict, Any, List, Optional
from loguru import logger
from datetime import datetime

from .segmentation import ChineseSegmenter
from .entity_recognition import EntityRecognizer
from .sentiment_analysis import SentimentAnalyzer
from .text_classifier import TextClassifier


class NLPProcessor:
    """NLP处理器统一接口"""
    
    def __init__(self, 
                 segmenter_type: str = "jieba",
                 entity_model: str = "rule_based", 
                 sentiment_model: str = "dictionary",
                 classifier_type: str = "rule_based"):
        """
        初始化NLP处理器
        
        Args:
            segmenter_type: 分词器类型
            entity_model: 实体识别模型类型
            sentiment_model: 情感分析模型类型
            classifier_type: 文本分类器类型
        """
        # 初始化各个组件
        self.segmenter = ChineseSegmenter(segmenter_type)
        self.entity_recognizer = EntityRecognizer(entity_model)
        self.sentiment_analyzer = SentimentAnalyzer(sentiment_model)
        self.text_classifier = TextClassifier(classifier_type)
        
        # 处理统计
        self.stats = {
            'total_processed': 0,
            'segmentation_count': 0,
            'entity_recognition_count': 0,
            'sentiment_analysis_count': 0,
            'classification_count': 0,
            'processing_time': 0.0
        }
        
        logger.info("NLP处理器初始化完成")
    
    def process_document(self, document: Dict[str, Any], 
                        enable_segmentation: bool = True,
                        enable_entity_recognition: bool = True,
                        enable_sentiment_analysis: bool = True,
                        enable_classification: bool = True) -> Dict[str, Any]:
        """
        处理单个文档的NLP任务
        
        Args:
            document: 输入文档
            enable_segmentation: 是否启用分词
            enable_entity_recognition: 是否启用实体识别
            enable_sentiment_analysis: 是否启用情感分析
            enable_classification: 是否启用文本分类
            
        Returns:
            处理后的文档
        """
        start_time = datetime.now()
        
        try:
            # 复制文档
            processed_doc = document.copy()
            
            # 提取文本内容
            title = document.get('title', '')
            content = document.get('content', '')
            full_text = f"{title} {content}".strip()
            
            if not full_text:
                logger.warning("文档内容为空，跳过NLP处理")
                return processed_doc
            
            # 1. 中文分词
            if enable_segmentation:
                try:
                    # 分词结果
                    words = self.segmenter.segment_text(content, remove_stopwords=True)
                    processed_doc['segmented_words'] = words
                    
                    # 提取关键词
                    keywords = self.segmenter.extract_keywords(full_text, top_k=10)
                    processed_doc['extracted_keywords'] = [kw[0] for kw in keywords]
                    processed_doc['keyword_weights'] = dict(keywords)
                    
                    self.stats['segmentation_count'] += 1
                    
                except Exception as e:
                    logger.error(f"分词处理失败: {str(e)}")
            
            # 2. 命名实体识别
            if enable_entity_recognition:
                try:
                    entities = self.entity_recognizer.recognize_entities(full_text)
                    processed_doc['entities'] = entities
                    
                    # 按类型分组实体
                    grouped_entities = self.entity_recognizer.extract_financial_entities(full_text)
                    processed_doc['grouped_entities'] = grouped_entities
                    
                    self.stats['entity_recognition_count'] += 1
                    
                except Exception as e:
                    logger.error(f"实体识别失败: {str(e)}")
            
            # 3. 情感分析
            if enable_sentiment_analysis:
                try:
                    # 分析标题情感
                    title_sentiment = self.sentiment_analyzer.analyze_sentiment(title) if title else None
                    
                    # 分析内容情感
                    content_sentiment = self.sentiment_analyzer.analyze_sentiment(content) if content else None
                    
                    # 金融情感分析
                    financial_sentiment = self.sentiment_analyzer.analyze_financial_sentiment(
                        full_text, 
                        context=document.get('source', '')
                    )
                    
                    processed_doc['sentiment_analysis'] = {
                        'title_sentiment': title_sentiment,
                        'content_sentiment': content_sentiment,
                        'financial_sentiment': financial_sentiment,
                        'overall_sentiment': financial_sentiment  # 使用金融情感作为总体情感
                    }
                    
                    self.stats['sentiment_analysis_count'] += 1
                    
                except Exception as e:
                    logger.error(f"情感分析失败: {str(e)}")
            
            # 4. 文本分类
            if enable_classification:
                try:
                    classification = self.text_classifier.classify_text(content, title)
                    processed_doc['classification'] = classification
                    
                    # 提取主要分类标签
                    processed_doc['news_type'] = classification.get('news_type', {}).get('category', '其他')
                    processed_doc['industry'] = classification.get('industry', {}).get('category', '综合')
                    processed_doc['importance_level'] = classification.get('importance', {}).get('level', 'medium')
                    processed_doc['investment_relevance'] = classification.get('investment_relevance', {}).get('relevance', 'medium')
                    
                    self.stats['classification_count'] += 1
                    
                except Exception as e:
                    logger.error(f"文本分类失败: {str(e)}")
            
            # 添加NLP处理元信息
            end_time = datetime.now()
            processing_time = (end_time - start_time).total_seconds()
            
            processed_doc['nlp_processing'] = {
                'processed_at': end_time.isoformat(),
                'processing_time': processing_time,
                'enabled_features': {
                    'segmentation': enable_segmentation,
                    'entity_recognition': enable_entity_recognition,
                    'sentiment_analysis': enable_sentiment_analysis,
                    'classification': enable_classification
                },
                'processor_version': '1.0.0'
            }
            
            self.stats['total_processed'] += 1
            self.stats['processing_time'] += processing_time
            
            logger.debug(f"NLP处理完成: {title[:50]}... (耗时: {processing_time:.3f}s)")
            
            return processed_doc
            
        except Exception as e:
            logger.error(f"NLP处理失败: {str(e)}")
            return document
    
    def process_batch(self, documents: List[Dict[str, Any]], **kwargs) -> List[Dict[str, Any]]:
        """批量处理文档"""
        processed_documents = []
        
        logger.info(f"开始批量NLP处理 {len(documents)} 个文档")
        
        for i, doc in enumerate(documents):
            try:
                processed_doc = self.process_document(doc, **kwargs)
                processed_documents.append(processed_doc)
                
                if (i + 1) % 20 == 0:
                    logger.info(f"已处理 {i + 1}/{len(documents)} 个文档")
                    
            except Exception as e:
                logger.error(f"文档 {i} NLP处理失败: {str(e)}")
                processed_documents.append(doc)
        
        logger.info(f"批量NLP处理完成，成功处理 {len(processed_documents)} 个文档")
        
        return processed_documents
    
    def extract_document_features(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取文档的NLP特征摘要
        
        Args:
            document: 已处理的文档
            
        Returns:
            特征摘要
        """
        features = {}
        
        try:
            # 基础信息
            features['title'] = document.get('title', '')
            features['word_count'] = len(document.get('segmented_words', []))
            
            # 关键词
            features['top_keywords'] = document.get('extracted_keywords', [])[:5]
            
            # 实体信息
            entities = document.get('entities', [])
            features['entity_count'] = len(entities)
            features['entity_types'] = list(set(entity['type'] for entity in entities))
            
            # 情感信息
            sentiment = document.get('sentiment_analysis', {}).get('overall_sentiment', {})
            features['sentiment_label'] = sentiment.get('label', 'neutral')
            features['sentiment_score'] = sentiment.get('score', 0.0)
            features['sentiment_confidence'] = sentiment.get('confidence', 0.0)
            
            # 分类信息
            classification = document.get('classification', {})
            features['news_type'] = classification.get('news_type', {}).get('category', '其他')
            features['industry'] = classification.get('industry', {}).get('category', '综合')
            features['importance'] = classification.get('importance', {}).get('level', 'medium')
            
            # 投资相关性
            features['investment_relevance'] = classification.get('investment_relevance', {}).get('relevance', 'medium')
            
            return features
            
        except Exception as e:
            logger.error(f"特征提取失败: {str(e)}")
            return {}
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """获取处理统计信息"""
        stats = self.stats.copy()
        
        # 计算平均处理时间
        if stats['total_processed'] > 0:
            stats['avg_processing_time'] = stats['processing_time'] / stats['total_processed']
        else:
            stats['avg_processing_time'] = 0.0
        
        # 添加组件信息
        stats['components'] = {
            'segmenter': self.segmenter.get_segmenter_info(),
            'entity_recognizer': {
                'type': self.entity_recognizer.model_type,
                'available_models': {
                    'lac': hasattr(self.entity_recognizer, 'model') and self.entity_recognizer.model_type == 'lac',
                    'spacy': hasattr(self.entity_recognizer, 'model') and self.entity_recognizer.model_type == 'spacy',
                    'rule_based': True
                }
            },
            'sentiment_analyzer': {
                'type': self.sentiment_analyzer.model_type,
                'dictionary_size': {
                    'positive': len(self.sentiment_analyzer.positive_words),
                    'negative': len(self.sentiment_analyzer.negative_words)
                }
            },
            'text_classifier': {
                'type': self.text_classifier.classifier_type,
                'categories': {
                    'news_types': len(self.text_classifier.news_type_rules),
                    'industries': len(self.text_classifier.industry_rules)
                }
            }
        }
        
        return stats
    
    def reset_statistics(self):
        """重置统计信息"""
        for key in self.stats:
            if isinstance(self.stats[key], (int, float)):
                self.stats[key] = 0
    
    def validate_document(self, document: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """验证文档格式"""
        errors = []
        
        if not isinstance(document, dict):
            errors.append("文档必须是字典类型")
            return False, errors
        
        # 检查必需字段
        required_fields = ['title', 'content']
        for field in required_fields:
            if field not in document:
                errors.append(f"缺少必需字段: {field}")
            elif not isinstance(document[field], str):
                errors.append(f"字段 {field} 必须是字符串类型")
        
        # 检查内容长度
        title = document.get('title', '')
        content = document.get('content', '')
        
        if not title and not content:
            errors.append("标题和内容不能同时为空")
        
        if len(title) > 500:
            errors.append("标题过长（超过500字符）")
        
        if len(content) > 50000:
            errors.append("内容过长（超过50000字符）")
        
        return len(errors) == 0, errors
    
    def create_nlp_summary(self, documents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """创建NLP处理摘要报告"""
        if not documents:
            return {}
        
        # 统计各种NLP特征
        sentiment_distribution = {'positive': 0, 'negative': 0, 'neutral': 0}
        news_type_distribution = {}
        industry_distribution = {}
        importance_distribution = {'high': 0, 'medium': 0, 'low': 0}
        
        total_entities = 0
        total_keywords = 0
        
        for doc in documents:
            # 情感分布
            sentiment = doc.get('sentiment_analysis', {}).get('overall_sentiment', {})
            label = sentiment.get('label', 'neutral')
            if label in sentiment_distribution:
                sentiment_distribution[label] += 1
            
            # 新闻类型分布
            news_type = doc.get('news_type', '其他')
            news_type_distribution[news_type] = news_type_distribution.get(news_type, 0) + 1
            
            # 行业分布
            industry = doc.get('industry', '综合')
            industry_distribution[industry] = industry_distribution.get(industry, 0) + 1
            
            # 重要性分布
            importance = doc.get('importance_level', 'medium')
            if importance in importance_distribution:
                importance_distribution[importance] += 1
            
            # 实体和关键词统计
            entities = doc.get('entities', [])
            keywords = doc.get('extracted_keywords', [])
            total_entities += len(entities)
            total_keywords += len(keywords)
        
        summary = {
            'total_documents': len(documents),
            'sentiment_distribution': sentiment_distribution,
            'news_type_distribution': news_type_distribution,
            'industry_distribution': industry_distribution,
            'importance_distribution': importance_distribution,
            'avg_entities_per_doc': total_entities / len(documents) if documents else 0,
            'avg_keywords_per_doc': total_keywords / len(documents) if documents else 0,
            'processing_stats': self.get_processing_statistics()
        }
        
        return summary
