"""
情感分析器

分析金融文本的情感倾向：
- 正面/负面/中性情感分类
- 情感强度评分
- 金融领域特定的情感词典
- 基于BERT的深度情感分析
"""
import re
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger
import json
from datetime import datetime

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    logger.warning("transformers未安装，将使用基于词典的情感分析")


class SentimentAnalyzer:
    """情感分析器"""
    
    def __init__(self, model_type: str = "dictionary"):
        """
        初始化情感分析器
        
        Args:
            model_type: 模型类型 ("dictionary", "bert", "finbert")
        """
        self.model_type = model_type
        self.model = None
        self.tokenizer = None
        
        # 初始化情感词典
        self._initialize_sentiment_dict()
        
        # 初始化模型
        self._initialize_model()
        
        logger.info(f"情感分析器初始化完成: {model_type}")
    
    def _initialize_sentiment_dict(self):
        """初始化情感词典"""
        # 正面情感词
        self.positive_words = {
            # 基础正面词
            '好', '棒', '优秀', '出色', '卓越', '杰出', '优异', '良好', '不错', '满意',
            '成功', '胜利', '获胜', '赢得', '取得', '实现', '达成', '完成', '突破', '创新',
            '增长', '上涨', '提升', '改善', '优化', '加强', '扩大', '增加', '提高', '发展',
            
            # 金融正面词
            '盈利', '获利', '赚钱', '收益', '回报', '分红', '派息', '配股', '送股',
            '涨停', '大涨', '暴涨', '飙升', '攀升', '走高', '上扬', '反弹', '回升',
            '买入', '增持', '推荐', '看好', '看涨', '做多', '利好', '积极', '乐观',
            '强势', '强劲', '稳健', '稳定', '健康', '良性', '向好', '改善', '复苏',
            '突破', '创新高', '新高', '历史新高', '超预期', '超额', '领先', '领涨',
            
            # 业绩相关
            '超预期', '增长', '提升', '改善', '扭亏', '扭亏为盈', '减亏', '盈转',
            '营收增长', '利润增长', '业绩增长', '净利润增长', '毛利率提升',
        }
        
        # 负面情感词
        self.negative_words = {
            # 基础负面词
            '差', '糟', '坏', '恶劣', '糟糕', '失败', '错误', '问题', '困难', '麻烦',
            '下降', '下跌', '减少', '降低', '恶化', '衰退', '萎缩', '缩减', '削减',
            '损失', '亏损', '赔钱', '破产', '倒闭', '关闭', '停产', '裁员', '减薪',
            
            # 金融负面词
            '亏损', '巨亏', '预亏', '首亏', '扩亏', '亏转', '由盈转亏',
            '跌停', '大跌', '暴跌', '重挫', '下挫', '走低', '下滑', '回落', '跳水',
            '卖出', '减持', '抛售', '看空', '看跌', '做空', '利空', '悲观', '担忧',
            '疲软', '疲弱', '低迷', '萎靡', '不振', '下行', '恶化', '衰退', '危机',
            '破位', '跌破', '创新低', '新低', '历史新低', '不及预期', '低于预期',
            
            # 风险相关
            '风险', '危险', '警告', '预警', '违约', '违规', '处罚', '罚款', '调查',
            '暂停', '停牌', '退市', '摘牌', 'ST', '*ST', '特别处理',
        }
        
        # 中性词（用于调节情感强度）
        self.neutral_words = {
            '平稳', '稳定', '持平', '维持', '保持', '继续', '延续', '正常', '一般',
            '预期', '符合预期', '基本', '大致', '约', '大约', '左右', '附近'
        }
        
        # 程度副词（情感强度修饰词）
        self.intensity_modifiers = {
            '极其': 2.0, '非常': 1.8, '特别': 1.6, '十分': 1.5, '很': 1.3, '比较': 1.1,
            '相对': 0.9, '稍微': 0.7, '略微': 0.6, '有点': 0.5, '一点': 0.4,
            '大幅': 1.8, '显著': 1.6, '明显': 1.4, '小幅': 0.8, '微幅': 0.6,
            '急剧': 2.0, '快速': 1.5, '迅速': 1.5, '缓慢': 0.7, '逐步': 0.8
        }
        
        # 否定词
        self.negation_words = {'不', '没', '无', '非', '未', '否', '别', '莫', '勿', '毋'}
    
    def _initialize_model(self):
        """初始化深度学习模型"""
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("transformers不可用，使用词典方法")
            return
        
        try:
            if self.model_type == "bert":
                # 使用通用中文BERT情感分析模型
                model_name = "uer/roberta-base-finetuned-chinanews-chinese"
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
                logger.info("BERT情感分析模型加载完成")
                
            elif self.model_type == "finbert":
                # 使用金融领域BERT模型
                model_name = "ProsusAI/finbert"  # 英文金融BERT
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
                logger.info("FinBERT情感分析模型加载完成")
                
        except Exception as e:
            logger.error(f"模型加载失败: {str(e)}")
            self.model_type = "dictionary"
            logger.info("回退到词典方法")
    
    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """
        分析文本情感
        
        Args:
            text: 输入文本
            
        Returns:
            情感分析结果
        """
        if not text or not isinstance(text, str):
            return self._create_neutral_result()
        
        try:
            if self.model_type in ["bert", "finbert"] and self.model:
                return self._analyze_with_model(text)
            else:
                return self._analyze_with_dictionary(text)
                
        except Exception as e:
            logger.error(f"情感分析失败: {str(e)}")
            return self._create_neutral_result()
    
    def _analyze_with_model(self, text: str) -> Dict[str, Any]:
        """使用深度学习模型进行情感分析"""
        try:
            # 文本预处理
            text = self._preprocess_text(text)
            
            # 截断过长文本
            max_length = 512
            if len(text) > max_length:
                text = text[:max_length]
            
            # 分词和编码
            inputs = self.tokenizer(text, return_tensors="pt", 
                                  truncation=True, padding=True, max_length=max_length)
            
            # 模型推理
            with torch.no_grad():
                outputs = self.model(**inputs)
                predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
            
            # 解析结果
            if self.model_type == "finbert":
                # FinBERT输出: [negative, neutral, positive]
                probs = predictions[0].tolist()
                negative_prob = probs[0]
                neutral_prob = probs[1]
                positive_prob = probs[2]
            else:
                # 通用BERT可能有不同的标签顺序
                probs = predictions[0].tolist()
                if len(probs) == 3:
                    negative_prob = probs[0]
                    neutral_prob = probs[1]
                    positive_prob = probs[2]
                else:
                    # 二分类情况
                    negative_prob = probs[0]
                    positive_prob = probs[1]
                    neutral_prob = 0.0
            
            # 确定主要情感
            max_prob = max(negative_prob, neutral_prob, positive_prob)
            if max_prob == positive_prob:
                label = 'positive'
                score = positive_prob - negative_prob
            elif max_prob == negative_prob:
                label = 'negative'
                score = negative_prob - positive_prob
            else:
                label = 'neutral'
                score = 0.0
            
            return {
                'label': label,
                'score': float(score),
                'confidence': float(max_prob),
                'probabilities': {
                    'positive': float(positive_prob),
                    'negative': float(negative_prob),
                    'neutral': float(neutral_prob)
                },
                'method': 'model',
                'model_type': self.model_type
            }
            
        except Exception as e:
            logger.error(f"模型情感分析失败: {str(e)}")
            return self._analyze_with_dictionary(text)
    
    def _analyze_with_dictionary(self, text: str) -> Dict[str, Any]:
        """使用词典方法进行情感分析"""
        # 文本预处理
        text = self._preprocess_text(text)
        words = text.split()
        
        positive_score = 0.0
        negative_score = 0.0
        
        i = 0
        while i < len(words):
            word = words[i]
            
            # 检查程度副词
            intensity = 1.0
            if i > 0 and words[i-1] in self.intensity_modifiers:
                intensity = self.intensity_modifiers[words[i-1]]
            
            # 检查否定词
            negation = False
            if i > 0 and words[i-1] in self.negation_words:
                negation = True
            elif i > 1 and words[i-2] in self.negation_words:
                negation = True
            
            # 计算情感分数
            if word in self.positive_words:
                score = 1.0 * intensity
                if negation:
                    negative_score += score
                else:
                    positive_score += score
                    
            elif word in self.negative_words:
                score = 1.0 * intensity
                if negation:
                    positive_score += score
                else:
                    negative_score += score
            
            i += 1
        
        # 计算最终分数
        total_sentiment_words = positive_score + negative_score
        
        if total_sentiment_words == 0:
            label = 'neutral'
            score = 0.0
            confidence = 0.5
        else:
            net_score = (positive_score - negative_score) / total_sentiment_words
            
            if net_score > 0.2:
                label = 'positive'
                confidence = min(0.9, abs(net_score) + 0.5)
            elif net_score < -0.2:
                label = 'negative'
                confidence = min(0.9, abs(net_score) + 0.5)
            else:
                label = 'neutral'
                confidence = 0.6
            
            score = net_score
        
        # 计算概率分布
        if label == 'positive':
            pos_prob = confidence
            neg_prob = (1 - confidence) / 2
            neu_prob = (1 - confidence) / 2
        elif label == 'negative':
            neg_prob = confidence
            pos_prob = (1 - confidence) / 2
            neu_prob = (1 - confidence) / 2
        else:
            neu_prob = confidence
            pos_prob = (1 - confidence) / 2
            neg_prob = (1 - confidence) / 2
        
        return {
            'label': label,
            'score': score,
            'confidence': confidence,
            'probabilities': {
                'positive': pos_prob,
                'negative': neg_prob,
                'neutral': neu_prob
            },
            'method': 'dictionary',
            'sentiment_words_count': int(total_sentiment_words)
        }
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本"""
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符（保留中文、英文、数字、基本标点）
        text = re.sub(r'[^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a\s\.\,\!\?\;\:]', '', text)
        
        return text.strip()
    
    def _create_neutral_result(self) -> Dict[str, Any]:
        """创建中性情感结果"""
        return {
            'label': 'neutral',
            'score': 0.0,
            'confidence': 0.5,
            'probabilities': {
                'positive': 0.33,
                'negative': 0.33,
                'neutral': 0.34
            },
            'method': 'default'
        }
    
    def analyze_financial_sentiment(self, text: str, context: str = None) -> Dict[str, Any]:
        """
        分析金融文本的情感，考虑金融语境
        
        Args:
            text: 输入文本
            context: 上下文信息（如股票代码、公司名等）
            
        Returns:
            金融情感分析结果
        """
        # 基础情感分析
        base_result = self.analyze_sentiment(text)
        
        # 金融语境调整
        financial_adjustment = self._calculate_financial_adjustment(text, context)
        
        # 调整情感分数
        adjusted_score = base_result['score'] + financial_adjustment
        adjusted_score = max(-1.0, min(1.0, adjusted_score))  # 限制在[-1, 1]范围内
        
        # 重新确定标签
        if adjusted_score > 0.2:
            adjusted_label = 'positive'
        elif adjusted_score < -0.2:
            adjusted_label = 'negative'
        else:
            adjusted_label = 'neutral'
        
        result = base_result.copy()
        result.update({
            'adjusted_score': adjusted_score,
            'adjusted_label': adjusted_label,
            'financial_adjustment': financial_adjustment,
            'context': context
        })
        
        return result
    
    def _calculate_financial_adjustment(self, text: str, context: str = None) -> float:
        """计算金融语境调整值"""
        adjustment = 0.0
        
        # 检查金融特定模式
        financial_patterns = {
            # 正面模式
            r'超预期|好于预期|业绩增长|盈利增长|营收增长': 0.2,
            r'涨停|大涨|暴涨|飙升|创新高': 0.3,
            r'买入|增持|推荐|看好|利好': 0.2,
            r'分红|派息|送股|配股': 0.1,
            
            # 负面模式
            r'不及预期|低于预期|业绩下滑|亏损|巨亏': -0.2,
            r'跌停|大跌|暴跌|重挫|创新低': -0.3,
            r'卖出|减持|看空|利空|风险': -0.2,
            r'ST|退市|停牌|违约|处罚': -0.3,
        }
        
        for pattern, adj in financial_patterns.items():
            if re.search(pattern, text):
                adjustment += adj
        
        # 限制调整范围
        return max(-0.5, min(0.5, adjustment))
    
    def batch_analyze(self, texts: List[str], contexts: List[str] = None) -> List[Dict[str, Any]]:
        """批量情感分析"""
        results = []
        
        logger.info(f"开始批量情感分析 {len(texts)} 个文本")
        
        if contexts is None:
            contexts = [None] * len(texts)
        
        for i, (text, context) in enumerate(zip(texts, contexts)):
            try:
                result = self.analyze_financial_sentiment(text, context)
                results.append(result)
                
                if (i + 1) % 100 == 0:
                    logger.info(f"已分析 {i + 1}/{len(texts)} 个文本")
                    
            except Exception as e:
                logger.error(f"文本 {i} 情感分析失败: {str(e)}")
                results.append(self._create_neutral_result())
        
        logger.info("批量情感分析完成")
        return results
    
    def get_sentiment_statistics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取情感分析统计信息"""
        if not results:
            return {}
        
        stats = {
            'total_texts': len(results),
            'label_distribution': {'positive': 0, 'negative': 0, 'neutral': 0},
            'avg_confidence': 0.0,
            'avg_score': 0.0,
            'method_distribution': {}
        }
        
        total_confidence = 0.0
        total_score = 0.0
        
        for result in results:
            # 标签分布
            label = result.get('label', 'neutral')
            stats['label_distribution'][label] += 1
            
            # 置信度和分数
            confidence = result.get('confidence', 0.0)
            score = result.get('score', 0.0)
            total_confidence += confidence
            total_score += score
            
            # 方法分布
            method = result.get('method', 'unknown')
            stats['method_distribution'][method] = stats['method_distribution'].get(method, 0) + 1
        
        # 计算平均值
        stats['avg_confidence'] = total_confidence / len(results)
        stats['avg_score'] = total_score / len(results)
        
        # 计算百分比
        for label in stats['label_distribution']:
            count = stats['label_distribution'][label]
            stats['label_distribution'][label] = {
                'count': count,
                'percentage': (count / len(results)) * 100
            }
        
        return stats
