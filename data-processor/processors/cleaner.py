"""
数据清洗器

负责清洗爬取的原始数据，包括：
- 文本格式化
- HTML标签清理
- 特殊字符处理
- 编码规范化
- 内容结构化
"""
import re
import html
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup
from loguru import logger
import chardet
from datetime import datetime


class DataCleaner:
    """数据清洗器"""
    
    def __init__(self):
        # 编译常用正则表达式
        self.html_tag_pattern = re.compile(r'<[^>]+>')
        self.whitespace_pattern = re.compile(r'\s+')
        self.special_chars_pattern = re.compile(r'[^\u4e00-\u9fa5\u0030-\u0039\u0041-\u005a\u0061-\u007a\s\.\,\!\?\;\:\-\(\)\[\]\"\']+')
        self.url_pattern = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        self.email_pattern = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
        
        # 金融术语标准化映射
        self.financial_term_mapping = {
            '涨停板': '涨停',
            '跌停板': '跌停',
            '股票价格': '股价',
            '市场价值': '市值',
            '净资产收益率': 'ROE',
            '每股收益': 'EPS',
            '市盈率': 'PE',
            '市净率': 'PB'
        }
    
    def clean_document(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        清洗单个文档
        
        Args:
            raw_data: 原始爬取数据
            
        Returns:
            清洗后的数据
        """
        try:
            cleaned_data = raw_data.copy()
            
            # 清洗标题
            if 'title' in cleaned_data:
                cleaned_data['title'] = self._clean_text(cleaned_data['title'])
            
            # 清洗内容
            if 'content' in cleaned_data:
                cleaned_data['content'] = self._clean_content(cleaned_data['content'])
            
            # 清洗摘要
            if 'summary' in cleaned_data:
                cleaned_data['summary'] = self._clean_text(cleaned_data['summary'])
            
            # 规范化URL
            if 'url' in cleaned_data:
                cleaned_data['url'] = self._normalize_url(cleaned_data['url'])
            
            # 处理时间字段
            cleaned_data = self._normalize_timestamps(cleaned_data)
            
            # 生成内容哈希用于去重
            cleaned_data['content_hash'] = self._generate_content_hash(cleaned_data)
            
            # 计算基础统计信息
            cleaned_data = self._calculate_basic_stats(cleaned_data)
            
            logger.debug(f"文档清洗完成: {cleaned_data.get('title', 'Unknown')[:50]}...")
            
            return cleaned_data
            
        except Exception as e:
            logger.error(f"文档清洗失败: {str(e)}")
            return raw_data
    
    def _clean_text(self, text: str) -> str:
        """清洗文本内容"""
        if not text or not isinstance(text, str):
            return ""
        
        # 解码HTML实体
        text = html.unescape(text)
        
        # 移除HTML标签
        text = self.html_tag_pattern.sub('', text)
        
        # 规范化空白字符
        text = self.whitespace_pattern.sub(' ', text)
        
        # 移除URL和邮箱
        text = self.url_pattern.sub('', text)
        text = self.email_pattern.sub('', text)
        
        # 标准化金融术语
        for old_term, new_term in self.financial_term_mapping.items():
            text = text.replace(old_term, new_term)
        
        # 清理特殊字符（保留中文、英文、数字和基本标点）
        # text = self.special_chars_pattern.sub('', text)
        
        # 去除首尾空白
        text = text.strip()
        
        return text
    
    def _clean_content(self, content: str) -> str:
        """清洗正文内容（更严格的处理）"""
        if not content or not isinstance(content, str):
            return ""
        
        # 使用BeautifulSoup进行更精确的HTML清理
        try:
            soup = BeautifulSoup(content, 'lxml')
            
            # 移除脚本和样式标签
            for script in soup(["script", "style", "meta", "link"]):
                script.decompose()
            
            # 提取纯文本
            text = soup.get_text()
            
        except Exception:
            # 如果BeautifulSoup失败，使用正则表达式
            text = self.html_tag_pattern.sub('', content)
        
        # 应用通用文本清洗
        text = self._clean_text(text)
        
        # 移除过短的段落
        paragraphs = text.split('\n')
        valid_paragraphs = [p.strip() for p in paragraphs if len(p.strip()) > 10]
        
        return '\n'.join(valid_paragraphs)
    
    def _normalize_url(self, url: str) -> str:
        """规范化URL"""
        if not url:
            return ""
        
        # 移除URL参数中的跟踪信息
        tracking_params = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']
        
        # 简单的URL清理（可以根据需要扩展）
        url = url.strip()
        
        # 移除fragment
        if '#' in url:
            url = url.split('#')[0]
        
        return url
    
    def _normalize_timestamps(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """规范化时间戳字段"""
        timestamp_fields = ['publish_time', 'crawl_time', 'update_time']
        
        for field in timestamp_fields:
            if field in data and data[field]:
                try:
                    # 如果是字符串，尝试解析
                    if isinstance(data[field], str):
                        # 这里可以添加更多的时间格式解析逻辑
                        pass
                    # 如果是datetime对象，转换为ISO格式字符串
                    elif isinstance(data[field], datetime):
                        data[field] = data[field].isoformat()
                except Exception as e:
                    logger.warning(f"时间字段 {field} 规范化失败: {str(e)}")
        
        return data
    
    def _generate_content_hash(self, data: Dict[str, Any]) -> str:
        """生成内容哈希用于去重"""
        import hashlib
        
        # 使用标题和内容的前500字符生成哈希
        title = data.get('title', '')
        content = data.get('content', '')
        
        # 组合关键内容
        key_content = f"{title}|{content[:500]}"
        
        # 生成MD5哈希
        return hashlib.md5(key_content.encode('utf-8')).hexdigest()
    
    def _calculate_basic_stats(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """计算基础统计信息"""
        content = data.get('content', '')
        
        if content:
            # 字符数
            data['char_count'] = len(content)
            
            # 词数（简单按空格分割）
            data['word_count'] = len(content.split())
            
            # 估算阅读时间（按每分钟200字计算）
            data['reading_time'] = max(1, data['word_count'] // 200)
        else:
            data['char_count'] = 0
            data['word_count'] = 0
            data['reading_time'] = 0
        
        return data
    
    def batch_clean(self, documents: list) -> list:
        """批量清洗文档"""
        cleaned_documents = []
        
        logger.info(f"开始批量清洗 {len(documents)} 个文档")
        
        for i, doc in enumerate(documents):
            try:
                cleaned_doc = self.clean_document(doc)
                cleaned_documents.append(cleaned_doc)
                
                if (i + 1) % 100 == 0:
                    logger.info(f"已清洗 {i + 1}/{len(documents)} 个文档")
                    
            except Exception as e:
                logger.error(f"文档 {i} 清洗失败: {str(e)}")
                # 保留原始文档
                cleaned_documents.append(doc)
        
        logger.info(f"批量清洗完成，成功处理 {len(cleaned_documents)} 个文档")
        
        return cleaned_documents
