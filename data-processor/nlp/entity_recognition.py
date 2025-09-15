"""
命名实体识别器

识别金融文本中的关键实体：
- 公司名称
- 股票代码
- 金额数值
- 日期时间
- 人名
- 地名
- 金融产品
"""
import re
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger
from datetime import datetime
import json

try:
    from LAC import LAC
    LAC_AVAILABLE = True
except ImportError:
    LAC_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False


class EntityRecognizer:
    """命名实体识别器"""
    
    def __init__(self, model_type: str = "rule_based"):
        """
        初始化实体识别器
        
        Args:
            model_type: 模型类型 ("rule_based", "lac", "spacy")
        """
        self.model_type = model_type
        self.model = None
        
        # 初始化正则表达式模式
        self._initialize_patterns()
        
        # 初始化实体词典
        self._initialize_entity_dict()
        
        # 初始化模型
        self._initialize_model()
        
        logger.info(f"命名实体识别器初始化完成: {model_type}")
    
    def _initialize_patterns(self):
        """初始化正则表达式模式"""
        self.patterns = {
            # 股票代码模式
            'stock_code': [
                re.compile(r'\b[0-9]{6}\b'),  # A股代码
                re.compile(r'\b[A-Z]{1,5}\b'),  # 美股代码
                re.compile(r'\b[0-9]{4}\.HK\b', re.IGNORECASE),  # 港股代码
            ],
            
            # 金额模式
            'money': [
                re.compile(r'[0-9,]+\.?[0-9]*\s*[万亿千百]*元'),
                re.compile(r'[0-9,]+\.?[0-9]*\s*万'),
                re.compile(r'[0-9,]+\.?[0-9]*\s*亿'),
                re.compile(r'\$[0-9,]+\.?[0-9]*[MBK]?'),  # 美元
                re.compile(r'[0-9,]+\.?[0-9]*\s*美元'),
            ],
            
            # 百分比模式
            'percentage': [
                re.compile(r'[0-9]+\.?[0-9]*%'),
                re.compile(r'百分之[0-9]+\.?[0-9]*'),
            ],
            
            # 日期模式
            'date': [
                re.compile(r'[0-9]{4}[-年][0-9]{1,2}[-月][0-9]{1,2}[日]?'),
                re.compile(r'[0-9]{1,2}月[0-9]{1,2}[日号]'),
                re.compile(r'[0-9]{4}/[0-9]{1,2}/[0-9]{1,2}'),
                re.compile(r'[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}'),
            ],
            
            # 时间模式
            'time': [
                re.compile(r'[0-9]{1,2}:[0-9]{2}(:[0-9]{2})?'),
                re.compile(r'[上下午]*[0-9]{1,2}点[0-9]{0,2}[分]?'),
            ],
            
            # 公司名称模式
            'company': [
                re.compile(r'[A-Za-z\u4e00-\u9fa5]+(?:股份)?(?:有限)?公司'),
                re.compile(r'[A-Za-z\u4e00-\u9fa5]+集团(?:股份)?(?:有限公司)?'),
                re.compile(r'[A-Za-z\u4e00-\u9fa5]+(?:银行|证券|保险|基金|信托)'),
                re.compile(r'[A-Z][a-z]+\s+(?:Inc\.|Corp\.|Ltd\.|Co\.)'),
            ],
            
            # 金融产品模式
            'financial_product': [
                re.compile(r'[A-Za-z\u4e00-\u9fa5]+基金'),
                re.compile(r'[A-Za-z\u4e00-\u9fa5]+债券'),
                re.compile(r'[A-Za-z\u4e00-\u9fa5]+期货'),
                re.compile(r'[A-Za-z\u4e00-\u9fa5]+ETF'),
            ],
            
            # 人名模式（简化）
            'person': [
                re.compile(r'[A-Za-z\u4e00-\u9fa5]{2,4}(?:先生|女士|总裁|董事长|CEO|CFO|CTO)'),
                re.compile(r'(?:董事长|总经理|CEO|CFO|CTO)[A-Za-z\u4e00-\u9fa5]{2,4}'),
            ],
            
            # 地名模式
            'location': [
                re.compile(r'[A-Za-z\u4e00-\u9fa5]+(?:省|市|区|县|镇|村)'),
                re.compile(r'(?:北京|上海|广州|深圳|杭州|南京|成都|重庆|天津|武汉|西安|青岛|大连|厦门|苏州|无锡|宁波|佛山|东莞|中山|珠海|惠州|江门|汕头|湛江|肇庆|梅州|茂名|阳江|韶关|河源|清远|潮州|揭阳|云浮)'),
            ],
        }
    
    def _initialize_entity_dict(self):
        """初始化实体词典"""
        self.entity_dict = {
            # 知名公司
            'companies': {
                '中国平安', '招商银行', '工商银行', '建设银行', '农业银行', '中国银行',
                '中信证券', '华泰证券', '国泰君安', '海通证券', '广发证券', '申万宏源',
                '腾讯控股', '阿里巴巴', '百度', '京东', '美团', '拼多多', '字节跳动',
                '中国移动', '中国联通', '中国电信', '中国石油', '中国石化', '中国海油',
                '贵州茅台', '五粮液', '泸州老窖', '剑南春', '水井坊', '舍得酒业',
                '比亚迪', '宁德时代', '特斯拉', '蔚来', '小鹏汽车', '理想汽车',
            },
            
            # 金融机构
            'financial_institutions': {
                '证监会', '银保监会', '央行', '人民银行', '上交所', '深交所', '北交所',
                '中金公司', '中信建投', '东方财富', '同花顺', '大智慧', '通达信',
                '天弘基金', '易方达', '华夏基金', '嘉实基金', '南方基金', '博时基金',
            },
            
            # 金融产品
            'financial_products': {
                '沪深300', '上证50', '中证500', '创业板指', '科创50',
                '国债ETF', '黄金ETF', '原油ETF', '纳指ETF', '标普500ETF',
                '货币基金', '债券基金', '股票基金', '混合基金', '指数基金',
            },
            
            # 经济指标
            'economic_indicators': {
                'GDP', 'CPI', 'PPI', 'PMI', 'M1', 'M2', 'M0',
                '社会融资规模', '新增贷款', '外汇储备', '贸易顺差', '贸易逆差',
                '失业率', '通胀率', '基准利率', '存款准备金率',
            }
        }
    
    def _initialize_model(self):
        """初始化模型"""
        if self.model_type == "lac" and LAC_AVAILABLE:
            try:
                self.model = LAC(mode='lac')
                logger.info("LAC实体识别模型初始化完成")
            except Exception as e:
                logger.error(f"LAC模型初始化失败: {str(e)}")
                self.model_type = "rule_based"
        
        elif self.model_type == "spacy" and SPACY_AVAILABLE:
            try:
                # 尝试加载中文模型
                self.model = spacy.load("zh_core_web_sm")
                logger.info("spaCy中文模型初始化完成")
            except Exception as e:
                logger.warning(f"spaCy中文模型加载失败: {str(e)}")
                try:
                    # 尝试加载英文模型
                    self.model = spacy.load("en_core_web_sm")
                    logger.info("spaCy英文模型初始化完成")
                except Exception as e2:
                    logger.error(f"spaCy模型初始化失败: {str(e2)}")
                    self.model_type = "rule_based"
        
        if self.model_type == "rule_based":
            logger.info("使用基于规则的实体识别")
    
    def recognize_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        识别文本中的命名实体
        
        Args:
            text: 输入文本
            
        Returns:
            实体列表，每个实体包含text, type, start, end, confidence
        """
        if not text or not isinstance(text, str):
            return []
        
        try:
            entities = []
            
            if self.model_type == "lac" and self.model:
                entities.extend(self._recognize_with_lac(text))
            elif self.model_type == "spacy" and self.model:
                entities.extend(self._recognize_with_spacy(text))
            
            # 总是执行基于规则的识别作为补充
            entities.extend(self._recognize_with_rules(text))
            
            # 去重和合并
            entities = self._merge_entities(entities)
            
            return entities
            
        except Exception as e:
            logger.error(f"实体识别失败: {str(e)}")
            return []
    
    def _recognize_with_lac(self, text: str) -> List[Dict[str, Any]]:
        """使用LAC进行实体识别"""
        entities = []
        
        try:
            lac_result = self.model.run(text)
            words = lac_result[0]
            tags = lac_result[1]
            
            current_pos = 0
            for word, tag in zip(words, tags):
                start_pos = text.find(word, current_pos)
                if start_pos != -1:
                    end_pos = start_pos + len(word)
                    
                    # 映射LAC标签到我们的实体类型
                    entity_type = self._map_lac_tag(tag)
                    if entity_type:
                        entities.append({
                            'text': word,
                            'type': entity_type,
                            'start': start_pos,
                            'end': end_pos,
                            'confidence': 0.8,
                            'source': 'lac'
                        })
                    
                    current_pos = end_pos
                
        except Exception as e:
            logger.error(f"LAC实体识别失败: {str(e)}")
        
        return entities
    
    def _recognize_with_spacy(self, text: str) -> List[Dict[str, Any]]:
        """使用spaCy进行实体识别"""
        entities = []
        
        try:
            doc = self.model(text)
            
            for ent in doc.ents:
                entity_type = self._map_spacy_label(ent.label_)
                if entity_type:
                    entities.append({
                        'text': ent.text,
                        'type': entity_type,
                        'start': ent.start_char,
                        'end': ent.end_char,
                        'confidence': 0.85,
                        'source': 'spacy'
                    })
                
        except Exception as e:
            logger.error(f"spaCy实体识别失败: {str(e)}")
        
        return entities
    
    def _recognize_with_rules(self, text: str) -> List[Dict[str, Any]]:
        """使用规则进行实体识别"""
        entities = []
        
        # 正则表达式识别
        for entity_type, patterns in self.patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    entities.append({
                        'text': match.group(),
                        'type': entity_type,
                        'start': match.start(),
                        'end': match.end(),
                        'confidence': 0.7,
                        'source': 'regex'
                    })
        
        # 词典匹配
        for category, terms in self.entity_dict.items():
            entity_type = self._map_dict_category(category)
            for term in terms:
                start = 0
                while True:
                    pos = text.find(term, start)
                    if pos == -1:
                        break
                    
                    entities.append({
                        'text': term,
                        'type': entity_type,
                        'start': pos,
                        'end': pos + len(term),
                        'confidence': 0.9,
                        'source': 'dictionary'
                    })
                    
                    start = pos + 1
        
        return entities
    
    def _map_lac_tag(self, tag: str) -> Optional[str]:
        """映射LAC标签到实体类型"""
        mapping = {
            'PER': 'person',
            'LOC': 'location',
            'ORG': 'company',
            'TIME': 'date'
        }
        return mapping.get(tag)
    
    def _map_spacy_label(self, label: str) -> Optional[str]:
        """映射spaCy标签到实体类型"""
        mapping = {
            'PERSON': 'person',
            'ORG': 'company',
            'GPE': 'location',
            'DATE': 'date',
            'TIME': 'time',
            'MONEY': 'money',
            'PERCENT': 'percentage'
        }
        return mapping.get(label)
    
    def _map_dict_category(self, category: str) -> str:
        """映射词典分类到实体类型"""
        mapping = {
            'companies': 'company',
            'financial_institutions': 'company',
            'financial_products': 'financial_product',
            'economic_indicators': 'economic_indicator'
        }
        return mapping.get(category, 'other')
    
    def _merge_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """合并重叠的实体"""
        if not entities:
            return []
        
        # 按位置排序
        entities.sort(key=lambda x: (x['start'], x['end']))
        
        merged = []
        current = entities[0]
        
        for entity in entities[1:]:
            # 检查是否重叠
            if entity['start'] < current['end']:
                # 重叠，选择置信度更高的
                if entity['confidence'] > current['confidence']:
                    current = entity
                # 如果置信度相同，选择更长的
                elif (entity['confidence'] == current['confidence'] and 
                      (entity['end'] - entity['start']) > (current['end'] - current['start'])):
                    current = entity
            else:
                # 不重叠，添加当前实体并更新
                merged.append(current)
                current = entity
        
        # 添加最后一个实体
        merged.append(current)
        
        return merged
    
    def extract_financial_entities(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """
        提取金融相关实体并分类
        
        Args:
            text: 输入文本
            
        Returns:
            按类型分组的实体字典
        """
        entities = self.recognize_entities(text)
        
        # 按类型分组
        grouped_entities = {}
        for entity in entities:
            entity_type = entity['type']
            if entity_type not in grouped_entities:
                grouped_entities[entity_type] = []
            grouped_entities[entity_type].append(entity)
        
        return grouped_entities
    
    def batch_recognize(self, texts: List[str]) -> List[List[Dict[str, Any]]]:
        """批量实体识别"""
        results = []
        
        logger.info(f"开始批量实体识别 {len(texts)} 个文本")
        
        for i, text in enumerate(texts):
            try:
                entities = self.recognize_entities(text)
                results.append(entities)
                
                if (i + 1) % 50 == 0:
                    logger.info(f"已处理 {i + 1}/{len(texts)} 个文本")
                    
            except Exception as e:
                logger.error(f"文本 {i} 实体识别失败: {str(e)}")
                results.append([])
        
        logger.info("批量实体识别完成")
        return results
    
    def get_entity_statistics(self, entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """获取实体统计信息"""
        stats = {
            'total_entities': len(entities),
            'by_type': {},
            'by_source': {},
            'avg_confidence': 0.0
        }
        
        if not entities:
            return stats
        
        # 按类型统计
        for entity in entities:
            entity_type = entity['type']
            source = entity.get('source', 'unknown')
            
            stats['by_type'][entity_type] = stats['by_type'].get(entity_type, 0) + 1
            stats['by_source'][source] = stats['by_source'].get(source, 0) + 1
        
        # 计算平均置信度
        total_confidence = sum(entity['confidence'] for entity in entities)
        stats['avg_confidence'] = total_confidence / len(entities)
        
        return stats
