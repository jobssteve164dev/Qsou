"""
中文分词处理器

支持多种分词工具：
- jieba分词
- pkuseg分词  
- LAC分词
- 自定义金融词典
"""
import jieba
import jieba.posseg as pseg
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger
import os
import re

try:
    import pkuseg
    PKUSEG_AVAILABLE = True
except ImportError:
    PKUSEG_AVAILABLE = False
    logger.warning("pkuseg未安装，将使用jieba作为备选")

try:
    from LAC import LAC
    LAC_AVAILABLE = True
except ImportError:
    LAC_AVAILABLE = False
    logger.warning("LAC未安装，将使用jieba作为备选")


class ChineseSegmenter:
    """中文分词处理器"""
    
    def __init__(self, segmenter_type: str = "jieba"):
        """
        初始化分词器
        
        Args:
            segmenter_type: 分词器类型 ("jieba", "pkuseg", "lac")
        """
        self.segmenter_type = segmenter_type
        self.segmenter = None
        
        # 金融专业词典
        self.financial_dict = self._load_financial_dictionary()
        
        # 停用词列表
        self.stopwords = self._load_stopwords()
        
        # 初始化分词器
        self._initialize_segmenter()
        
        logger.info(f"中文分词器初始化完成: {segmenter_type}")
    
    def _initialize_segmenter(self):
        """初始化分词器"""
        if self.segmenter_type == "jieba":
            self._initialize_jieba()
        elif self.segmenter_type == "pkuseg" and PKUSEG_AVAILABLE:
            self._initialize_pkuseg()
        elif self.segmenter_type == "lac" and LAC_AVAILABLE:
            self._initialize_lac()
        else:
            logger.warning(f"分词器 {self.segmenter_type} 不可用，回退到jieba")
            self.segmenter_type = "jieba"
            self._initialize_jieba()
    
    def _initialize_jieba(self):
        """初始化jieba分词器"""
        # 加载自定义词典
        for word in self.financial_dict:
            jieba.add_word(word)
        
        # 设置词典路径（如果有自定义词典文件）
        # jieba.load_userdict("path/to/financial_dict.txt")
        
        self.segmenter = jieba
        logger.info("jieba分词器初始化完成")
    
    def _initialize_pkuseg(self):
        """初始化pkuseg分词器"""
        try:
            # 使用金融领域模型（如果可用）
            self.segmenter = pkuseg.pkuseg(model_name='default')
            logger.info("pkuseg分词器初始化完成")
        except Exception as e:
            logger.error(f"pkuseg初始化失败: {str(e)}")
            self._initialize_jieba()
    
    def _initialize_lac(self):
        """初始化LAC分词器"""
        try:
            self.segmenter = LAC(mode='seg')
            logger.info("LAC分词器初始化完成")
        except Exception as e:
            logger.error(f"LAC初始化失败: {str(e)}")
            self._initialize_jieba()
    
    def _load_financial_dictionary(self) -> List[str]:
        """加载金融专业词典"""
        financial_terms = [
            # 股票相关
            "A股", "B股", "H股", "科创板", "创业板", "主板", "中小板",
            "涨停板", "跌停板", "停牌", "复牌", "退市", "ST股", "*ST股",
            "市盈率", "市净率", "市销率", "市现率", "股息率", "净资产收益率",
            "每股收益", "每股净资产", "每股现金流", "资产负债率",
            
            # 基金相关
            "公募基金", "私募基金", "ETF基金", "LOF基金", "QDII基金",
            "货币基金", "债券基金", "股票基金", "混合基金", "指数基金",
            "基金净值", "基金份额", "基金经理", "基金托管", "基金分红",
            
            # 债券相关
            "国债", "企业债", "公司债", "可转债", "政府债", "金融债",
            "债券收益率", "债券久期", "信用评级", "违约风险",
            
            # 期货期权
            "商品期货", "金融期货", "股指期货", "国债期货",
            "看涨期权", "看跌期权", "期权费", "行权价", "到期日",
            
            # 外汇相关
            "人民币汇率", "美元指数", "汇率波动", "外汇储备",
            "离岸人民币", "在岸人民币", "汇率中间价",
            
            # 宏观经济
            "GDP", "CPI", "PPI", "PMI", "M1", "M2", "社会融资规模",
            "央行", "货币政策", "财政政策", "降准", "降息", "加息",
            "量化宽松", "流动性", "通胀", "通缩",
            
            # 公司财务
            "营业收入", "净利润", "毛利率", "净利率", "资产总额",
            "股东权益", "现金流量", "应收账款", "存货周转率",
            "IPO", "增发", "配股", "分红", "股票回购", "股权激励",
            
            # 投资机构
            "证监会", "银保监会", "央行", "上交所", "深交所", "北交所",
            "公募基金公司", "私募基金", "券商", "银行", "保险公司",
            "信托公司", "期货公司", "QFII", "RQFII",
            
            # 投资策略
            "价值投资", "成长投资", "量化投资", "对冲基金",
            "多头策略", "空头策略", "套利策略", "事件驱动",
            "技术分析", "基本面分析", "资产配置", "风险管理"
        ]
        
        return financial_terms
    
    def _load_stopwords(self) -> set:
        """加载停用词"""
        # 基础停用词
        basic_stopwords = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', 
            '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', 
            '着', '没有', '看', '好', '自己', '这', '那', '里', '就是', '还是',
            '但是', '如果', '可以', '这样', '现在', '因为', '所以', '虽然',
            '已经', '还有', '只是', '或者', '而且', '然后', '但', '与', '及',
            '以及', '等', '等等', '之', '之后', '之前', '当', '当时', '此',
            '此时', '为', '为了', '由于', '关于', '对于', '根据', '按照'
        }
        
        # 金融领域特定停用词
        financial_stopwords = {
            '股票', '公司', '市场', '投资', '资金', '价格', '今日', '昨日',
            '本周', '上周', '本月', '上月', '今年', '去年', '目前', '当前',
            '消息', '报道', '据悉', '据了解', '有关', '相关', '方面'
        }
        
        return basic_stopwords | financial_stopwords
    
    def segment_text(self, text: str, with_pos: bool = False, 
                    remove_stopwords: bool = True) -> List[str] or List[Tuple[str, str]]:
        """
        对文本进行分词
        
        Args:
            text: 待分词文本
            with_pos: 是否返回词性标注
            remove_stopwords: 是否移除停用词
            
        Returns:
            分词结果列表
        """
        if not text or not isinstance(text, str):
            return []
        
        try:
            # 预处理文本
            text = self._preprocess_text(text)
            
            # 执行分词
            if self.segmenter_type == "jieba":
                if with_pos:
                    words = [(word, flag) for word, flag in pseg.cut(text)]
                else:
                    words = list(jieba.cut(text))
            elif self.segmenter_type == "pkuseg":
                words = self.segmenter.cut(text)
                if with_pos:
                    # pkuseg默认不提供词性，这里简单处理
                    words = [(word, 'n') for word in words]
            elif self.segmenter_type == "lac":
                if with_pos:
                    lac_result = self.segmenter.run(text)
                    words = list(zip(lac_result[0], lac_result[1]))
                else:
                    words = self.segmenter.run(text)[0]
            else:
                words = text.split()  # 备用方案
            
            # 后处理
            if with_pos:
                words = self._postprocess_words_with_pos(words, remove_stopwords)
            else:
                words = self._postprocess_words(words, remove_stopwords)
            
            return words
            
        except Exception as e:
            logger.error(f"分词处理失败: {str(e)}")
            return []
    
    def _preprocess_text(self, text: str) -> str:
        """预处理文本"""
        # 移除多余的空白字符
        text = re.sub(r'\s+', ' ', text)
        
        # 移除特殊字符（保留中文、英文、数字）
        text = re.sub(r'[^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a\s]', '', text)
        
        return text.strip()
    
    def _postprocess_words(self, words: List[str], remove_stopwords: bool) -> List[str]:
        """后处理分词结果"""
        processed_words = []
        
        for word in words:
            word = word.strip()
            
            # 过滤条件
            if len(word) < 1:  # 过短的词
                continue
            if word.isspace():  # 空白字符
                continue
            if remove_stopwords and word in self.stopwords:  # 停用词
                continue
            if word.isdigit() and len(word) > 10:  # 过长的数字
                continue
            
            processed_words.append(word)
        
        return processed_words
    
    def _postprocess_words_with_pos(self, words: List[Tuple[str, str]], 
                                  remove_stopwords: bool) -> List[Tuple[str, str]]:
        """后处理带词性的分词结果"""
        processed_words = []
        
        for word, pos in words:
            word = word.strip()
            
            # 过滤条件
            if len(word) < 1:
                continue
            if word.isspace():
                continue
            if remove_stopwords and word in self.stopwords:
                continue
            if word.isdigit() and len(word) > 10:
                continue
            
            processed_words.append((word, pos))
        
        return processed_words
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """
        提取关键词
        
        Args:
            text: 输入文本
            top_k: 返回前k个关键词
            
        Returns:
            关键词及其权重列表
        """
        try:
            if self.segmenter_type == "jieba":
                import jieba.analyse
                
                # 使用TF-IDF提取关键词
                keywords = jieba.analyse.extract_tags(
                    text, 
                    topK=top_k, 
                    withWeight=True,
                    allowPOS=('n', 'nr', 'ns', 'nt', 'nz', 'v', 'vd', 'vn', 'a', 'ad', 'an')
                )
                
                return keywords
            else:
                # 其他分词器的简单关键词提取
                words = self.segment_text(text, remove_stopwords=True)
                
                # 简单的词频统计
                word_freq = {}
                for word in words:
                    if len(word) > 1:  # 只考虑长度大于1的词
                        word_freq[word] = word_freq.get(word, 0) + 1
                
                # 按频率排序
                sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
                
                # 归一化权重
                max_freq = sorted_words[0][1] if sorted_words else 1
                keywords = [(word, freq / max_freq) for word, freq in sorted_words[:top_k]]
                
                return keywords
                
        except Exception as e:
            logger.error(f"关键词提取失败: {str(e)}")
            return []
    
    def batch_segment(self, texts: List[str], **kwargs) -> List[List[str]]:
        """批量分词"""
        results = []
        
        logger.info(f"开始批量分词 {len(texts)} 个文本")
        
        for i, text in enumerate(texts):
            try:
                words = self.segment_text(text, **kwargs)
                results.append(words)
                
                if (i + 1) % 100 == 0:
                    logger.info(f"已分词 {i + 1}/{len(texts)} 个文本")
                    
            except Exception as e:
                logger.error(f"文本 {i} 分词失败: {str(e)}")
                results.append([])
        
        logger.info(f"批量分词完成")
        return results
    
    def get_segmenter_info(self) -> Dict[str, Any]:
        """获取分词器信息"""
        return {
            'type': self.segmenter_type,
            'dictionary_size': len(self.financial_dict),
            'stopwords_size': len(self.stopwords),
            'available_segmenters': {
                'jieba': True,
                'pkuseg': PKUSEG_AVAILABLE,
                'lac': LAC_AVAILABLE
            }
        }
