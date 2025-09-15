"""
内容提取器

负责从清洗后的数据中提取结构化信息：
- 关键信息提取
- 摘要生成
- 标签提取
- 分类标注
"""
import re
from typing import Dict, Any, List, Optional
from loguru import logger
import jieba
from datetime import datetime


class ContentExtractor:
    """内容提取器"""
    
    def __init__(self):
        # 初始化jieba分词
        jieba.initialize()
        
        # 金融关键词词典
        self.financial_keywords = {
            '股票相关': ['股票', '股价', '涨停', '跌停', '成交量', '市值', '股东', '分红', '配股'],
            '财务指标': ['营收', '利润', 'ROE', 'EPS', 'PE', 'PB', '资产', '负债', '现金流'],
            '市场动态': ['IPO', '重组', '并购', '增发', '回购', '停牌', '复牌', '退市'],
            '监管政策': ['证监会', '交易所', '监管', '政策', '法规', '公告', '处罚', '审核'],
            '行业分析': ['行业', '板块', '概念', '龙头', '景气度', '周期', '趋势', '竞争']
        }
        
        # 实体识别模式
        self.entity_patterns = {
            'stock_code': re.compile(r'[0-9]{6}|[A-Z]{2,4}'),  # 股票代码
            'money': re.compile(r'[0-9,]+\.?[0-9]*\s*[万亿千百]*元'),  # 金额
            'percentage': re.compile(r'[0-9]+\.?[0-9]*%'),  # 百分比
            'date': re.compile(r'[0-9]{4}[-年][0-9]{1,2}[-月][0-9]{1,2}[日]?'),  # 日期
            'company': re.compile(r'[A-Za-z\u4e00-\u9fa5]+(?:股份)?(?:有限)?公司|[A-Za-z\u4e00-\u9fa5]+集团')  # 公司名
        }
        
        # 情感词典（简化版）
        self.positive_words = {'上涨', '增长', '盈利', '利好', '看好', '推荐', '买入', '强势', '突破'}
        self.negative_words = {'下跌', '亏损', '利空', '看空', '卖出', '弱势', '跌破', '风险', '警告'}
    
    def extract_content_features(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        提取文档内容特征
        
        Args:
            document: 清洗后的文档数据
            
        Returns:
            包含提取特征的文档数据
        """
        try:
            # 复制原始文档
            enriched_doc = document.copy()
            
            content = document.get('content', '')
            title = document.get('title', '')
            
            if not content and not title:
                logger.warning("文档内容和标题均为空，跳过特征提取")
                return enriched_doc
            
            # 合并标题和内容用于分析
            full_text = f"{title} {content}"
            
            # 提取关键词
            enriched_doc['keywords'] = self._extract_keywords(full_text)
            
            # 提取实体
            enriched_doc['entities'] = self._extract_entities(full_text)
            
            # 生成摘要
            enriched_doc['auto_summary'] = self._generate_summary(content, title)
            
            # 分类标注
            enriched_doc['categories'] = self._classify_content(full_text)
            
            # 情感分析（简单版）
            enriched_doc['sentiment'] = self._analyze_sentiment(full_text)
            
            # 重要性评分
            enriched_doc['importance_score'] = self._calculate_importance_score(enriched_doc)
            
            logger.debug(f"内容特征提取完成: {title[:50]}...")
            
            return enriched_doc
            
        except Exception as e:
            logger.error(f"内容特征提取失败: {str(e)}")
            return document
    
    def _extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """提取关键词"""
        if not text:
            return []
        
        try:
            # 使用jieba进行分词
            words = jieba.cut(text)
            
            # 过滤停用词和短词
            stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
            
            # 统计词频
            word_freq = {}
            for word in words:
                word = word.strip()
                if len(word) > 1 and word not in stopwords:
                    word_freq[word] = word_freq.get(word, 0) + 1
            
            # 按频率排序并返回前top_k个
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            
            return [word for word, freq in sorted_words[:top_k]]
            
        except Exception as e:
            logger.error(f"关键词提取失败: {str(e)}")
            return []
    
    def _extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """提取命名实体"""
        entities = []
        
        if not text:
            return entities
        
        try:
            for entity_type, pattern in self.entity_patterns.items():
                matches = pattern.findall(text)
                for match in matches:
                    entities.append({
                        'text': match,
                        'type': entity_type,
                        'confidence': 0.8  # 简单的置信度
                    })
            
            return entities
            
        except Exception as e:
            logger.error(f"实体提取失败: {str(e)}")
            return []
    
    def _generate_summary(self, content: str, title: str = "") -> str:
        """生成文档摘要"""
        if not content:
            return title
        
        try:
            # 简单的摘要生成：取前3个句子
            sentences = re.split(r'[。！？]', content)
            valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 10]
            
            if len(valid_sentences) >= 3:
                summary = '。'.join(valid_sentences[:3]) + '。'
            elif len(valid_sentences) > 0:
                summary = '。'.join(valid_sentences) + '。'
            else:
                summary = title
            
            # 限制摘要长度
            if len(summary) > 200:
                summary = summary[:200] + '...'
            
            return summary
            
        except Exception as e:
            logger.error(f"摘要生成失败: {str(e)}")
            return title
    
    def _classify_content(self, text: str) -> List[str]:
        """内容分类"""
        categories = []
        
        if not text:
            return categories
        
        try:
            # 基于关键词的简单分类
            text_lower = text.lower()
            
            for category, keywords in self.financial_keywords.items():
                for keyword in keywords:
                    if keyword in text_lower:
                        if category not in categories:
                            categories.append(category)
                        break
            
            # 如果没有匹配到任何分类，设为通用
            if not categories:
                categories.append('通用财经')
            
            return categories
            
        except Exception as e:
            logger.error(f"内容分类失败: {str(e)}")
            return ['通用财经']
    
    def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """情感分析（简化版）"""
        if not text:
            return {'label': 'neutral', 'score': 0.0, 'confidence': 0.0}
        
        try:
            positive_count = sum(1 for word in self.positive_words if word in text)
            negative_count = sum(1 for word in self.negative_words if word in text)
            
            total_sentiment_words = positive_count + negative_count
            
            if total_sentiment_words == 0:
                return {'label': 'neutral', 'score': 0.0, 'confidence': 0.5}
            
            # 计算情感倾向
            sentiment_score = (positive_count - negative_count) / total_sentiment_words
            
            # 确定标签
            if sentiment_score > 0.2:
                label = 'positive'
            elif sentiment_score < -0.2:
                label = 'negative'
            else:
                label = 'neutral'
            
            # 计算置信度
            confidence = min(0.9, abs(sentiment_score) + 0.3)
            
            return {
                'label': label,
                'score': sentiment_score,
                'confidence': confidence
            }
            
        except Exception as e:
            logger.error(f"情感分析失败: {str(e)}")
            return {'label': 'neutral', 'score': 0.0, 'confidence': 0.0}
    
    def _calculate_importance_score(self, document: Dict[str, Any]) -> float:
        """计算文档重要性评分"""
        try:
            score = 0.0
            
            # 基于内容长度
            word_count = document.get('word_count', 0)
            if word_count > 100:
                score += 0.2
            if word_count > 500:
                score += 0.2
            
            # 基于实体数量
            entities = document.get('entities', [])
            entity_score = min(0.3, len(entities) * 0.05)
            score += entity_score
            
            # 基于分类
            categories = document.get('categories', [])
            if '股票相关' in categories or '市场动态' in categories:
                score += 0.2
            
            # 基于情感强度
            sentiment = document.get('sentiment', {})
            sentiment_confidence = sentiment.get('confidence', 0)
            if sentiment_confidence > 0.7:
                score += 0.1
            
            # 基于关键词质量
            keywords = document.get('keywords', [])
            keyword_score = min(0.2, len(keywords) * 0.02)
            score += keyword_score
            
            # 确保评分在0-1之间
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.error(f"重要性评分计算失败: {str(e)}")
            return 0.5
    
    def batch_extract(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量提取内容特征"""
        enriched_documents = []
        
        logger.info(f"开始批量提取 {len(documents)} 个文档的内容特征")
        
        for i, doc in enumerate(documents):
            try:
                enriched_doc = self.extract_content_features(doc)
                enriched_documents.append(enriched_doc)
                
                if (i + 1) % 50 == 0:
                    logger.info(f"已处理 {i + 1}/{len(documents)} 个文档")
                    
            except Exception as e:
                logger.error(f"文档 {i} 特征提取失败: {str(e)}")
                enriched_documents.append(doc)
        
        logger.info(f"批量特征提取完成，成功处理 {len(enriched_documents)} 个文档")
        
        return enriched_documents
