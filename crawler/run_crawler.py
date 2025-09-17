#!/usr/bin/env python3
"""
爬虫启动脚本

启动真实的爬虫进行数据采集
"""

import os
import sys
import subprocess
import logging
from datetime import datetime
from typing import List, Optional

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/crawler.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class CrawlerManager:
    """爬虫管理器"""
    
    def __init__(self):
        self.crawler_dir = current_dir
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def start_crawler(self, spider_name: str, **kwargs) -> bool:
        """启动指定爬虫"""
        try:
            self.logger.info(f"启动爬虫: {spider_name}")
            
            # 构建Scrapy命令
            cmd = [
                'scrapy', 'crawl', spider_name,
                '-L', 'INFO',
                '-s', 'LOG_FILE=logs/scrapy.log'
            ]
            
            # 添加自定义参数
            for key, value in kwargs.items():
                cmd.extend(['-a', f'{key}={value}'])
            
            # 执行命令
            result = subprocess.run(
                cmd,
                cwd=self.crawler_dir,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode == 0:
                self.logger.info(f"爬虫 {spider_name} 执行成功")
                self.logger.info(f"输出: {result.stdout}")
                return True
            else:
                self.logger.error(f"爬虫 {spider_name} 执行失败")
                self.logger.error(f"错误: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"启动爬虫失败: {str(e)}")
            return False
    
    def start_all_crawlers(self) -> bool:
        """启动所有爬虫"""
        spiders = ['financial_news', 'company_announcement']
        success_count = 0
        
        for spider in spiders:
            if self.start_crawler(spider):
                success_count += 1
        
        self.logger.info(f"成功启动 {success_count}/{len(spiders)} 个爬虫")
        return success_count == len(spiders)
    
    def check_dependencies(self) -> bool:
        """检查依赖"""
        try:
            # 检查Scrapy
            result = subprocess.run(
                ['scrapy', '--version'],
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.logger.error("Scrapy未安装或不可用")
                return False
            
            self.logger.info(f"Scrapy版本: {result.stdout.strip()}")
            
            # 检查数据处理系统
            import requests
            try:
                response = requests.get("http://localhost:8001/health", timeout=5)
                if response.status_code == 200:
                    self.logger.info("数据处理系统连接正常")
                else:
                    self.logger.warning("数据处理系统响应异常")
            except requests.exceptions.RequestException:
                self.logger.warning("数据处理系统不可用，将使用本地存储")
            
            return True
            
        except Exception as e:
            self.logger.error(f"依赖检查失败: {str(e)}")
            return False
    
    def create_directories(self):
        """创建必要的目录"""
        directories = [
            'logs',
            'downloads',
            'downloads/files',
            'downloads/images'
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            self.logger.info(f"创建目录: {directory}")


def main():
    """主函数"""
    print("=== Qsou投资情报搜索引擎 - 爬虫启动器 ===")
    print(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 创建爬虫管理器
    manager = CrawlerManager()
    
    # 创建必要目录
    manager.create_directories()
    
    # 检查依赖
    if not manager.check_dependencies():
        print("❌ 依赖检查失败，请检查环境配置")
        return False
    
    print("✅ 依赖检查通过")
    print()
    
    # 获取用户选择
    print("请选择要启动的爬虫:")
    print("1. 财经新闻爬虫 (financial_news)")
    print("2. 公司公告爬虫 (company_announcement)")
    print("3. 启动所有爬虫")
    print("4. 退出")
    
    while True:
        try:
            choice = input("\n请输入选择 (1-4): ").strip()
            
            if choice == '1':
                print("\n🚀 启动财经新闻爬虫...")
                success = manager.start_crawler('financial_news')
                break
            elif choice == '2':
                print("\n🚀 启动公司公告爬虫...")
                success = manager.start_crawler('company_announcement')
                break
            elif choice == '3':
                print("\n🚀 启动所有爬虫...")
                success = manager.start_all_crawlers()
                break
            elif choice == '4':
                print("👋 退出")
                return True
            else:
                print("❌ 无效选择，请输入1-4")
                
        except KeyboardInterrupt:
            print("\n👋 用户取消")
            return True
        except Exception as e:
            print(f"❌ 输入错误: {str(e)}")
    
    # 输出结果
    if success:
        print("\n✅ 爬虫执行完成")
        print("📊 查看日志文件: logs/crawler.log")
        print("📊 查看Scrapy日志: logs/scrapy.log")
    else:
        print("\n❌ 爬虫执行失败")
        print("📊 查看错误日志: logs/crawler.log")
    
    return success


if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 程序被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 程序执行失败: {str(e)}")
        sys.exit(1)
