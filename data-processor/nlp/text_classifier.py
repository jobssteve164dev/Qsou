"""
文本分类器

对金融文本进行主题分类：
- 新闻类型分类
- 行业分类
- 重要性等级分类
- 投资相关性分类
"""
import re
from typing import Dict, Any, List, Tuple, Optional
from loguru import logger
import json
from collections import Counter

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import train_test_split
    import numpy as np
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logger.warning("scikit-learn未安装，将使用基于规则的分类")


class TextClassifier:
    """文本分类器"""
    
    def __init__(self, classifier_type: str = "rule_based"):
        """
        初始化文本分类器
        
        Args:
            classifier_type: 分类器类型 ("rule_based", "ml")
        """
        self.classifier_type = classifier_type
        self.ml_model = None
        
        # 初始化分类规则
        self._initialize_classification_rules()
        
        # 初始化机器学习模型（如果可用）
        if classifier_type == "ml" and SKLEARN_AVAILABLE:
            self._initialize_ml_model()
        
        logger.info(f"文本分类器初始化完成: {classifier_type}")
    
    def _initialize_classification_rules(self):
        """初始化分类规则"""
        # 新闻类型分类规则
        self.news_type_rules = {
            '公司公告': {
                'keywords': ['公告', '披露', '股东大会', '董事会', '监事会', '年报', '季报', '半年报',
                           '重大事项', '关联交易', '股权变动', '高管变动', '业绩预告', '业绩快报'],
                'patterns': [r'.*公司.*公告', r'.*披露.*', r'.*股东大会.*决议']
            },
            
            '市场新闻': {
                'keywords': ['市场', '交易', '成交', '涨跌', '指数', '板块', '概念股', '龙头股',
                           '资金流向', '北向资金', '南向资金', '融资融券', '大宗交易'],
                'patterns': [r'.*指数.*', r'.*板块.*', r'.*概念.*']
            },
            
            '政策法规': {
                'keywords': ['政策', '法规', '监管', '央行', '证监会', '银保监会', '发改委',
                           '财政部', '国务院', '通知', '意见', '办法', '规定', '条例'],
                'patterns': [r'.*监管.*', r'.*政策.*', r'.*法规.*']
            },
            
            '行业动态': {
                'keywords': ['行业', '产业', '供应链', '上下游', '竞争', '市场份额', '技术',
                           '创新', '研发', '专利', '合作', '并购', '重组'],
                'patterns': [r'.*行业.*', r'.*产业.*']
            },
            
            '宏观经济': {
                'keywords': ['GDP', 'CPI', 'PPI', 'PMI', 'M1', 'M2', '通胀', '通缩', '利率',
                           '汇率', '贸易', '进出口', '外汇储备', '财政', '货币政策'],
                'patterns': [r'.*经济.*', r'.*宏观.*']
            },
            
            '国际财经': {
                'keywords': ['美联储', '欧央行', '日央行', '美股', '欧股', '港股', '原油', '黄金',
                           '美元', '欧元', '日元', '国际', '全球', '海外', '外盘'],
                'patterns': [r'.*国际.*', r'.*全球.*', r'.*海外.*']
            }
        }
        
        # 行业分类规则
        self.industry_rules = {
            '银行': ['银行', '工商银行', '建设银行', '农业银行', '中国银行', '交通银行', '招商银行'],
            '证券': ['证券', '券商', '中信证券', '华泰证券', '国泰君安', '海通证券', '广发证券'],
            '保险': ['保险', '中国平安', '中国人寿', '新华保险', '中国太保', '中国人保'],
            '房地产': ['房地产', '地产', '万科', '恒大', '碧桂园', '保利', '融创', '中海'],
            '科技': ['科技', '互联网', '人工智能', 'AI', '大数据', '云计算', '5G', '芯片', '半导体'],
            '医药': ['医药', '生物', '制药', '疫苗', '医疗', '医院', '药品', '医疗器械'],
            '汽车': ['汽车', '新能源车', '电动车', '比亚迪', '特斯拉', '蔚来', '小鹏', '理想'],
            '能源': ['能源', '石油', '天然气', '煤炭', '电力', '新能源', '风电', '光伏', '核电'],
            '消费': ['消费', '零售', '食品', '饮料', '白酒', '茅台', '五粮液', '家电', '服装'],
            '制造业': ['制造', '工业', '机械', '钢铁', '有色', '化工', '建材', '轻工']
        }
        
        # 重要性等级规则
        self.importance_rules = {
            'high': {
                'keywords': ['重大', '重要', '紧急', '突发', '首次', '历史', '创新高', '创新低',
                           '涨停', '跌停', '停牌', '复牌', '退市', 'IPO', '并购', '重组'],
                'patterns': [r'.*重大.*', r'.*重要.*', r'.*突发.*']
            },
            'medium': {
                'keywords': ['公告', '披露', '变动', '调整', '增长', '下降', '合作', '签约'],
                'patterns': [r'.*公告.*', r'.*变动.*']
            },
            'low': {
                'keywords': ['日常', '例行', '常规', '维持', '持续', '延续'],
                'patterns': [r'.*日常.*', r'.*例行.*']
            }
        }
        
        # 投资相关性规则
        self.investment_relevance_rules = {
            'high': {
                'keywords': ['投资', '买入', '卖出', '推荐', '评级', '目标价', '估值', '分红',
                           '业绩', '财报', '利润', '营收', '增长', '亏损'],
                'patterns': [r'.*投资.*', r'.*评级.*', r'.*业绩.*']
            },
            'medium': {
                'keywords': ['市场', '行业', '竞争', '发展', '前景', '趋势', '政策', '监管'],
                'patterns': [r'.*市场.*', r'.*行业.*']
            },
            'low': {
                'keywords': ['会议', '活动', '人事', '管理', '文化', '社会责任'],
                'patterns': [r'.*会议.*', r'.*活动.*']
            }
        }
    
    def _initialize_ml_model(self):
        """初始化机器学习模型"""
        try:
            # 创建文本分类管道
            self.ml_model = Pipeline([
                ('tfidf', TfidfVectorizer(max_features=1000, stop_words=None)),
                ('classifier', MultinomialNB())
            ])
            
            # 这里应该加载预训练的模型或使用标注数据训练
            # 由于没有标注数据，暂时使用规则方法
            logger.info("机器学习分类器准备就绪（需要训练数据）")
            
        except Exception as e:
            logger.error(f"机器学习模型初始化失败: {str(e)}")
            self.classifier_type = "rule_based"
    
    def classify_text(self, text: str, title: str = "") -> Dict[str, Any]:
        """
        对文本进行分类
        
        Args:
            text: 正文内容
            title: 标题（可选）
            
        Returns:
            分类结果
        """
        if not text and not title:
            return self._create_default_classification()
        
        # 合并标题和内容
        full_text = f"{title} {text}".strip()
        
        try:
            # 执行各种分类
            news_type = self._classify_news_type(full_text)
            industry = self._classify_industry(full_text)
            importance = self._classify_importance(full_text)
            investment_relevance = self._classify_investment_relevance(full_text)
            
            # 计算综合分类置信度
            avg_confidence = (
                news_type['confidence'] + 
                industry['confidence'] + 
                importance['confidence'] + 
                investment_relevance['confidence']
            ) / 4
            
            result = {
                'news_type': news_type,
                'industry': industry,
                'importance': importance,
                'investment_relevance': investment_relevance,
                'overall_confidence': avg_confidence,
                'method': self.classifier_type
            }
            
            return result
            
        except Exception as e:
            logger.error(f"文本分类失败: {str(e)}")
            return self._create_default_classification()
    
    def _classify_news_type(self, text: str) -> Dict[str, Any]:
        """分类新闻类型"""
        scores = {}
        
        for news_type, rules in self.news_type_rules.items():
            score = 0.0
            
            # 关键词匹配
            for keyword in rules['keywords']:
                if keyword in text:
                    score += 1.0
            
            # 正则模式匹配
            for pattern in rules['patterns']:
                if re.search(pattern, text):
                    score += 2.0
            
            scores[news_type] = score
        
        # 找到最高分
        if not scores or max(scores.values()) == 0:
            return {'category': '其他', 'confidence': 0.3}
        
        best_category = max(scores, key=scores.get)
        max_score = scores[best_category]
        
        # 计算置信度
        total_score = sum(scores.values())
        confidence = min(0.95, max_score / max(total_score, 1.0))
        
        return {
            'category': best_category,
            'confidence': confidence,
            'scores': scores
        }
    
    def _classify_industry(self, text: str) -> Dict[str, Any]:
        """分类行业"""
        scores = {}
        
        for industry, keywords in self.industry_rules.items():
            score = 0.0
            
            for keyword in keywords:
                if keyword in text:
                    score += 1.0
            
            scores[industry] = score
        
        if not scores or max(scores.values()) == 0:
            return {'category': '综合', 'confidence': 0.3}
        
        best_industry = max(scores, key=scores.get)
        max_score = scores[best_industry]
        
        # 计算置信度
        total_score = sum(scores.values())
        confidence = min(0.95, max_score / max(total_score, 1.0))
        
        return {
            'category': best_industry,
            'confidence': confidence,
            'scores': scores
        }
    
    def _classify_importance(self, text: str) -> Dict[str, Any]:
        """分类重要性等级"""
        scores = {'high': 0.0, 'medium': 0.0, 'low': 0.0}
        
        for level, rules in self.importance_rules.items():
            # 关键词匹配
            for keyword in rules['keywords']:
                if keyword in text:
                    scores[level] += 1.0
            
            # 正则模式匹配
            for pattern in rules['patterns']:
                if re.search(pattern, text):
                    scores[level] += 2.0
        
        # 默认为中等重要性
        if max(scores.values()) == 0:
            return {'level': 'medium', 'confidence': 0.5}
        
        best_level = max(scores, key=scores.get)
        max_score = scores[best_level]
        
        # 计算置信度
        total_score = sum(scores.values())
        confidence = min(0.95, max_score / max(total_score, 1.0))
        
        return {
            'level': best_level,
            'confidence': confidence,
            'scores': scores
        }
    
    def _classify_investment_relevance(self, text: str) -> Dict[str, Any]:
        """分类投资相关性"""
        scores = {'high': 0.0, 'medium': 0.0, 'low': 0.0}
        
        for relevance, rules in self.investment_relevance_rules.items():
            # 关键词匹配
            for keyword in rules['keywords']:
                if keyword in text:
                    scores[relevance] += 1.0
            
            # 正则模式匹配
            for pattern in rules['patterns']:
                if re.search(pattern, text):
                    scores[relevance] += 2.0
        
        # 默认为中等相关性
        if max(scores.values()) == 0:
            return {'relevance': 'medium', 'confidence': 0.5}
        
        best_relevance = max(scores, key=scores.get)
        max_score = scores[best_relevance]
        
        # 计算置信度
        total_score = sum(scores.values())
        confidence = min(0.95, max_score / max(total_score, 1.0))
        
        return {
            'relevance': best_relevance,
            'confidence': confidence,
            'scores': scores
        }
    
    def _create_default_classification(self) -> Dict[str, Any]:
        """创建默认分类结果"""
        return {
            'news_type': {'category': '其他', 'confidence': 0.3},
            'industry': {'category': '综合', 'confidence': 0.3},
            'importance': {'level': 'medium', 'confidence': 0.5},
            'investment_relevance': {'relevance': 'medium', 'confidence': 0.5},
            'overall_confidence': 0.4,
            'method': 'default'
        }
    
    def classify_batch(self, texts: List[str], titles: List[str] = None) -> List[Dict[str, Any]]:
        """批量文本分类"""
        results = []
        
        logger.info(f"开始批量文本分类 {len(texts)} 个文本")
        
        if titles is None:
            titles = [""] * len(texts)
        
        for i, (text, title) in enumerate(zip(texts, titles)):
            try:
                result = self.classify_text(text, title)
                results.append(result)
                
                if (i + 1) % 50 == 0:
                    logger.info(f"已分类 {i + 1}/{len(texts)} 个文本")
                    
            except Exception as e:
                logger.error(f"文本 {i} 分类失败: {str(e)}")
                results.append(self._create_default_classification())
        
        logger.info("批量文本分类完成")
        return results
    
    def get_classification_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取分类统计信息"""
        if not results:
            return {}
        
        stats = {
            'total_texts': len(results),
            'news_type_distribution': Counter(),
            'industry_distribution': Counter(),
            'importance_distribution': Counter(),
            'investment_relevance_distribution': Counter(),
            'avg_confidence': 0.0
        }
        
        total_confidence = 0.0
        
        for result in results:
            # 新闻类型分布
            news_type = result.get('news_type', {}).get('category', '其他')
            stats['news_type_distribution'][news_type] += 1
            
            # 行业分布
            industry = result.get('industry', {}).get('category', '综合')
            stats['industry_distribution'][industry] += 1
            
            # 重要性分布
            importance = result.get('importance', {}).get('level', 'medium')
            stats['importance_distribution'][importance] += 1
            
            # 投资相关性分布
            relevance = result.get('investment_relevance', {}).get('relevance', 'medium')
            stats['investment_relevance_distribution'][relevance] += 1
            
            # 总体置信度
            confidence = result.get('overall_confidence', 0.0)
            total_confidence += confidence
        
        # 计算平均置信度
        stats['avg_confidence'] = total_confidence / len(results)
        
        # 转换为百分比
        for dist_name in ['news_type_distribution', 'industry_distribution', 
                         'importance_distribution', 'investment_relevance_distribution']:
            distribution = stats[dist_name]
            total = sum(distribution.values())
            
            stats[dist_name] = {
                category: {
                    'count': count,
                    'percentage': (count / total) * 100
                }
                for category, count in distribution.items()
            }
        
        return stats
    
    def get_top_categories(self, results: List[Dict[str, Any]], 
                          category_type: str = "news_type", top_k: int = 5) -> List[Tuple[str, int]]:
        """获取最常见的分类"""
        if not results:
            return []
        
        counter = Counter()
        
        for result in results:
            if category_type == "news_type":
                category = result.get('news_type', {}).get('category', '其他')
            elif category_type == "industry":
                category = result.get('industry', {}).get('category', '综合')
            elif category_type == "importance":
                category = result.get('importance', {}).get('level', 'medium')
            elif category_type == "investment_relevance":
                category = result.get('investment_relevance', {}).get('relevance', 'medium')
            else:
                continue
            
            counter[category] += 1
        
        return counter.most_common(top_k)
