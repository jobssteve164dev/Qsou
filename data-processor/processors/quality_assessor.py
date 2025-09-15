"""
数据质量评估器

负责评估文档质量：
- 内容完整性检查
- 信息价值评估
- 数据质量评分
- 过滤低质量内容
"""
import re
from typing import Dict, Any, List, Optional
from loguru import logger
from datetime import datetime
from ..config import config


class QualityAssessor:
    """数据质量评估器"""
    
    def __init__(self):
        # 质量评估参数
        self.min_word_count = config.min_word_count
        self.max_word_count = config.max_word_count
        self.quality_threshold = config.quality_score_threshold
        
        # 垃圾内容模式
        self.spam_patterns = [
            re.compile(r'点击.*查看', re.IGNORECASE),
            re.compile(r'更多.*详情', re.IGNORECASE),
            re.compile(r'联系.*客服', re.IGNORECASE),
            re.compile(r'广告.*推广', re.IGNORECASE),
            re.compile(r'免费.*咨询', re.IGNORECASE),
        ]
        
        # 低质量内容指标
        self.low_quality_indicators = {
            'excessive_punctuation': re.compile(r'[!！]{3,}|[?？]{3,}|[.。]{5,}'),
            'excessive_caps': re.compile(r'[A-Z]{10,}'),
            'repetitive_chars': re.compile(r'(.)\1{5,}'),
            'too_many_numbers': re.compile(r'\d+'),
        }
        
        # 高质量内容指标
        self.high_quality_keywords = {
            '分析报告', '研究报告', '财务分析', '市场分析', '行业研究',
            '投资建议', '风险评估', '业绩预告', '公司公告', '监管公告'
        }
        
        # 必需字段
        self.required_fields = ['title', 'content', 'url', 'source']
    
    def assess_document_quality(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        评估单个文档质量
        
        Args:
            document: 待评估的文档
            
        Returns:
            包含质量评估结果的文档
        """
        try:
            # 复制文档
            assessed_doc = document.copy()
            
            # 执行各项质量检查
            quality_checks = {
                'completeness': self._check_completeness(document),
                'content_quality': self._check_content_quality(document),
                'information_value': self._check_information_value(document),
                'spam_detection': self._check_spam_content(document),
                'structure_quality': self._check_structure_quality(document)
            }
            
            # 计算综合质量评分
            overall_score = self._calculate_overall_score(quality_checks)
            
            # 添加质量评估结果
            assessed_doc['quality_assessment'] = {
                'overall_score': overall_score,
                'checks': quality_checks,
                'is_high_quality': overall_score >= self.quality_threshold,
                'assessment_time': datetime.now().isoformat()
            }
            
            # 添加质量标签
            assessed_doc['quality_label'] = self._get_quality_label(overall_score)
            
            logger.debug(f"文档质量评估完成: {document.get('title', 'Unknown')[:50]}... (评分: {overall_score:.3f})")
            
            return assessed_doc
            
        except Exception as e:
            logger.error(f"文档质量评估失败: {str(e)}")
            # 返回默认质量评估
            document['quality_assessment'] = {
                'overall_score': 0.5,
                'checks': {},
                'is_high_quality': False,
                'assessment_time': datetime.now().isoformat()
            }
            document['quality_label'] = 'medium'
            return document
    
    def _check_completeness(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """检查内容完整性"""
        score = 1.0
        issues = []
        
        # 检查必需字段
        for field in self.required_fields:
            if not document.get(field):
                score -= 0.2
                issues.append(f"缺少字段: {field}")
        
        # 检查内容长度
        content = document.get('content', '')
        word_count = len(content.split()) if content else 0
        
        if word_count < self.min_word_count:
            score -= 0.3
            issues.append(f"内容过短: {word_count} 字")
        elif word_count > self.max_word_count:
            score -= 0.1
            issues.append(f"内容过长: {word_count} 字")
        
        # 检查标题质量
        title = document.get('title', '')
        if not title or len(title) < 5:
            score -= 0.2
            issues.append("标题过短或缺失")
        elif len(title) > 200:
            score -= 0.1
            issues.append("标题过长")
        
        return {
            'score': max(0.0, score),
            'issues': issues,
            'word_count': word_count
        }
    
    def _check_content_quality(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """检查内容质量"""
        score = 1.0
        issues = []
        
        content = document.get('content', '')
        title = document.get('title', '')
        full_text = f"{title} {content}"
        
        if not full_text.strip():
            return {'score': 0.0, 'issues': ['内容为空']}
        
        # 检查低质量指标
        for indicator_name, pattern in self.low_quality_indicators.items():
            matches = pattern.findall(full_text)
            if matches:
                if indicator_name == 'too_many_numbers':
                    # 数字过多的特殊处理
                    number_ratio = len(matches) / len(full_text.split())
                    if number_ratio > 0.3:  # 数字占比超过30%
                        score -= 0.2
                        issues.append("数字内容过多")
                else:
                    score -= 0.15
                    issues.append(f"检测到低质量内容: {indicator_name}")
        
        # 检查文本多样性
        words = full_text.split()
        if len(words) > 10:
            unique_words = set(words)
            diversity_ratio = len(unique_words) / len(words)
            if diversity_ratio < 0.3:  # 词汇重复度过高
                score -= 0.2
                issues.append("内容重复度过高")
        
        # 检查句子结构
        sentences = re.split(r'[。！？]', content)
        valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
        
        if len(valid_sentences) < 2:
            score -= 0.2
            issues.append("句子结构过于简单")
        
        return {
            'score': max(0.0, score),
            'issues': issues,
            'diversity_ratio': len(set(words)) / len(words) if words else 0,
            'sentence_count': len(valid_sentences)
        }
    
    def _check_information_value(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """检查信息价值"""
        score = 0.5  # 基础分
        value_indicators = []
        
        content = document.get('content', '')
        title = document.get('title', '')
        full_text = f"{title} {content}".lower()
        
        # 检查高价值关键词
        high_value_count = 0
        for keyword in self.high_quality_keywords:
            if keyword in full_text:
                high_value_count += 1
        
        if high_value_count > 0:
            score += min(0.3, high_value_count * 0.1)
            value_indicators.append(f"包含 {high_value_count} 个高价值关键词")
        
        # 检查实体信息
        entities = document.get('entities', [])
        if entities:
            entity_score = min(0.2, len(entities) * 0.02)
            score += entity_score
            value_indicators.append(f"包含 {len(entities)} 个实体")
        
        # 检查数据和数字
        numbers = re.findall(r'\d+\.?\d*', content)
        if len(numbers) >= 3:  # 包含足够的数据
            score += 0.1
            value_indicators.append("包含数据信息")
        
        # 检查时效性
        publish_time = document.get('publish_time')
        if publish_time:
            try:
                # 简单的时效性检查（实际应该解析时间）
                score += 0.1
                value_indicators.append("包含时间信息")
            except Exception:
                pass
        
        return {
            'score': min(1.0, score),
            'indicators': value_indicators,
            'entity_count': len(entities),
            'number_count': len(numbers)
        }
    
    def _check_spam_content(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """检查垃圾内容"""
        score = 1.0
        spam_indicators = []
        
        content = document.get('content', '')
        title = document.get('title', '')
        full_text = f"{title} {content}"
        
        # 检查垃圾内容模式
        for pattern in self.spam_patterns:
            if pattern.search(full_text):
                score -= 0.3
                spam_indicators.append("包含垃圾内容模式")
        
        # 检查URL密度
        urls = re.findall(r'http[s]?://\S+', full_text)
        if len(urls) > 3:  # URL过多
            score -= 0.2
            spam_indicators.append("URL密度过高")
        
        # 检查联系方式
        contacts = re.findall(r'(?:电话|手机|微信|QQ)[:：]\s*\d+', full_text)
        if contacts:
            score -= 0.3
            spam_indicators.append("包含联系方式")
        
        return {
            'score': max(0.0, score),
            'indicators': spam_indicators,
            'is_spam': score < 0.5
        }
    
    def _check_structure_quality(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """检查结构质量"""
        score = 1.0
        structure_issues = []
        
        content = document.get('content', '')
        
        if not content:
            return {'score': 0.0, 'issues': ['内容为空']}
        
        # 检查段落结构
        paragraphs = content.split('\n')
        valid_paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 20]
        
        if len(valid_paragraphs) < 2:
            score -= 0.2
            structure_issues.append("段落结构不清晰")
        
        # 检查标点符号使用
        punctuation_count = len(re.findall(r'[。！？，；：]', content))
        word_count = len(content.split())
        
        if word_count > 50 and punctuation_count / word_count < 0.05:
            score -= 0.2
            structure_issues.append("标点符号使用不当")
        
        # 检查格式一致性
        if '\t' in content or '    ' in content:  # 包含制表符或多个空格
            score += 0.1  # 格式化内容加分
        
        return {
            'score': max(0.0, score),
            'issues': structure_issues,
            'paragraph_count': len(valid_paragraphs)
        }
    
    def _calculate_overall_score(self, quality_checks: Dict[str, Dict[str, Any]]) -> float:
        """计算综合质量评分"""
        # 权重配置
        weights = {
            'completeness': 0.25,
            'content_quality': 0.25,
            'information_value': 0.25,
            'spam_detection': 0.15,
            'structure_quality': 0.10
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for check_name, check_result in quality_checks.items():
            if check_name in weights and 'score' in check_result:
                weight = weights[check_name]
                score = check_result['score']
                total_score += score * weight
                total_weight += weight
        
        # 归一化评分
        if total_weight > 0:
            return total_score / total_weight
        else:
            return 0.5  # 默认评分
    
    def _get_quality_label(self, score: float) -> str:
        """获取质量标签"""
        if score >= 0.8:
            return 'high'
        elif score >= 0.6:
            return 'medium'
        elif score >= 0.4:
            return 'low'
        else:
            return 'very_low'
    
    def filter_high_quality_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤出高质量文档"""
        high_quality_docs = []
        
        for doc in documents:
            quality_assessment = doc.get('quality_assessment', {})
            if quality_assessment.get('is_high_quality', False):
                high_quality_docs.append(doc)
        
        logger.info(f"从 {len(documents)} 个文档中筛选出 {len(high_quality_docs)} 个高质量文档")
        
        return high_quality_docs
    
    def batch_assess(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量评估文档质量"""
        assessed_documents = []
        
        logger.info(f"开始批量评估 {len(documents)} 个文档的质量")
        
        for i, doc in enumerate(documents):
            try:
                assessed_doc = self.assess_document_quality(doc)
                assessed_documents.append(assessed_doc)
                
                if (i + 1) % 50 == 0:
                    logger.info(f"已评估 {i + 1}/{len(documents)} 个文档")
                    
            except Exception as e:
                logger.error(f"文档 {i} 质量评估失败: {str(e)}")
                assessed_documents.append(doc)
        
        # 统计质量分布
        quality_stats = self._get_quality_statistics(assessed_documents)
        logger.info(f"质量评估完成，统计信息: {quality_stats}")
        
        return assessed_documents
    
    def _get_quality_statistics(self, documents: List[Dict[str, Any]]) -> Dict[str, int]:
        """获取质量统计信息"""
        stats = {'high': 0, 'medium': 0, 'low': 0, 'very_low': 0}
        
        for doc in documents:
            quality_label = doc.get('quality_label', 'medium')
            if quality_label in stats:
                stats[quality_label] += 1
        
        return stats
