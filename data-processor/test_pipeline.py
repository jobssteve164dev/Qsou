"""
数据处理管道测试和验证模块

用于验证数据处理管道的完整性和正确性
"""
import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime
from loguru import logger
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import data_processor_manager


class PipelineValidator:
    """数据处理管道验证器"""
    
    def __init__(self):
        """初始化验证器"""
        self.test_results = {}
        self.validation_start_time = None
        
    def create_test_documents(self) -> List[Dict[str, Any]]:
        """创建测试文档"""
        test_documents = [
            {
                'title': '中国平安发布2024年三季度业绩报告',
                'content': '''
                中国平安保险（集团）股份有限公司今日发布2024年第三季度业绩报告。
                报告显示，前三季度集团实现营业收入8,756亿元，同比增长4.2%；
                归属于母公司股东的净利润达到1,234亿元，同比增长8.5%。
                
                其中，寿险及健康险业务新业务价值同比增长12.3%，
                财产保险业务综合成本率为96.8%，保持行业领先水平。
                银行业务净利润同比增长6.7%，资产质量持续改善。
                
                公司表示，将继续深化"金融+科技"战略，
                加大在人工智能、区块链等前沿技术的投入，
                为客户提供更优质的金融服务体验。
                ''',
                'url': 'https://finance.sina.com.cn/stock/s/2024-10-30/doc-inaizmkx123456.shtml',
                'source': '新浪财经',
                'category': 'financial_report',
                'publish_time': '2024-10-30T09:30:00Z',
                'author': '财经记者',
                'tags': ['中国平安', '三季报', '业绩', '保险', '银行']
            },
            {
                'title': '新能源汽车产业政策利好频出，板块有望迎来新一轮上涨',
                'content': '''
                近期，国家发改委、工信部等多部门密集出台新能源汽车产业支持政策。
                政策内容涵盖充电基础设施建设、购车补贴延续、技术创新支持等多个方面。
                
                市场分析认为，随着政策利好的持续释放，
                新能源汽车产业链上下游企业将显著受益。
                特别是在电池技术、智能驾驶、充电设施等细分领域，
                相关上市公司有望迎来业绩和估值的双重提升。
                
                从技术面看，新能源汽车指数已突破前期高点，
                成交量明显放大，市场情绪转暖。
                建议投资者关注产业链龙头企业的投资机会。
                ''',
                'url': 'https://stock.eastmoney.com/news/1234567890.html',
                'source': '东方财富网',
                'category': 'market_analysis',
                'publish_time': '2024-10-30T14:15:00Z',
                'author': '市场分析师',
                'tags': ['新能源汽车', '政策利好', '投资机会', '技术分析']
            },
            {
                'title': '央行决定下调存款准备金率0.25个百分点',
                'content': '''
                中国人民银行今日宣布，为保持银行体系流动性合理充裕，
                支持实体经济发展，决定于2024年11月1日下调
                金融机构存款准备金率0.25个百分点。
                
                此次降准将释放长期资金约5000亿元，
                主要用于支持小微企业、民营企业和制造业等重点领域。
                央行表示，将继续实施稳健的货币政策，
                保持流动性合理充裕，促进经济平稳健康发展。
                
                市场人士认为，此次降准释放了积极的政策信号，
                有助于降低银行资金成本，推动贷款利率下行，
                对股市和债市都将产生积极影响。
                ''',
                'url': 'https://www.pbc.gov.cn/goutongjiaoliu/113456/113469/4567890/index.html',
                'source': '中国人民银行',
                'category': 'monetary_policy',
                'publish_time': '2024-10-30T16:00:00Z',
                'author': '央行新闻发言人',
                'tags': ['央行', '降准', '货币政策', '流动性', '实体经济']
            },
            {
                'title': '科技股集体走强，人工智能概念股领涨',
                'content': '''
                今日A股市场科技股表现强劲，人工智能概念股集体走强。
                截至收盘，科技股指数上涨3.8%，创近期新高。
                
                个股方面，多只AI概念股涨停，包括：
                - 科大讯飞：涨停，成交额超50亿元
                - 海康威视：涨9.2%，创历史新高
                - 商汤科技：涨8.5%，成交活跃
                
                分析师指出，随着AI技术在各行业的深度应用，
                相关公司的业绩增长预期不断提升。
                特别是在大模型、机器视觉、智能驾驶等细分赛道，
                头部企业的竞争优势日益明显。
                
                建议投资者关注具有核心技术和应用场景的AI龙头企业。
                ''',
                'url': 'https://finance.163.com/24/1030/18/JKLMNOPQ00258105.html',
                'source': '网易财经',
                'category': 'market_news',
                'publish_time': '2024-10-30T18:30:00Z',
                'author': '股市记者',
                'tags': ['科技股', '人工智能', 'AI概念', '涨停', '投资建议']
            },
            {
                'title': '重复内容测试：央行决定下调存款准备金率0.25个百分点',
                'content': '''
                中国人民银行今日宣布，为保持银行体系流动性合理充裕，
                支持实体经济发展，决定于2024年11月1日下调
                金融机构存款准备金率0.25个百分点。
                
                此次降准将释放长期资金约5000亿元...
                ''',
                'url': 'https://duplicate.test.com/news/123',
                'source': '测试重复来源',
                'category': 'monetary_policy',
                'publish_time': '2024-10-30T16:05:00Z',
                'author': '测试作者',
                'tags': ['央行', '降准', '重复测试']
            }
        ]
        
        return test_documents
    
    async def validate_initialization(self) -> Dict[str, Any]:
        """验证系统初始化"""
        logger.info("开始验证系统初始化")
        
        try:
            init_result = await data_processor_manager.initialize()
            
            validation_result = {
                'test_name': 'system_initialization',
                'success': init_result.get('success', False),
                'details': init_result,
                'timestamp': datetime.now().isoformat()
            }
            
            if validation_result['success']:
                logger.info("✅ 系统初始化验证通过")
            else:
                logger.error("❌ 系统初始化验证失败")
                
            return validation_result
            
        except Exception as e:
            logger.error(f"系统初始化验证异常: {str(e)}")
            return {
                'test_name': 'system_initialization',
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def validate_full_pipeline(self) -> Dict[str, Any]:
        """验证完整数据处理管道"""
        logger.info("开始验证完整数据处理管道")
        
        try:
            # 创建测试文档
            test_documents = self.create_test_documents()
            
            # 运行完整管道
            pipeline_result = await data_processor_manager.process_documents_full_pipeline(
                documents=test_documents,
                enable_elasticsearch=True,
                enable_vector_store=True
            )
            
            # 验证结果
            validation_checks = {
                'pipeline_success': pipeline_result.get('success', False),
                'input_documents': pipeline_result.get('input_documents', 0),
                'processed_documents': pipeline_result.get('processed_documents', 0),
                'elasticsearch_indexed': pipeline_result.get('elasticsearch_result', {}).get('success', False),
                'vector_stored': pipeline_result.get('vector_result', {}).get('success', False),
                'processing_time': pipeline_result.get('processing_time', 0)
            }
            
            # 检查去重功能
            deduplication_effective = (
                validation_checks['processed_documents'] < validation_checks['input_documents']
            )
            validation_checks['deduplication_working'] = deduplication_effective
            
            # 整体成功判断
            overall_success = (
                validation_checks['pipeline_success'] and
                validation_checks['processed_documents'] > 0 and
                validation_checks['elasticsearch_indexed'] and
                validation_checks['vector_stored']
            )
            
            validation_result = {
                'test_name': 'full_pipeline',
                'success': overall_success,
                'checks': validation_checks,
                'details': pipeline_result,
                'timestamp': datetime.now().isoformat()
            }
            
            if overall_success:
                logger.info("✅ 完整数据处理管道验证通过")
                logger.info(f"   - 输入文档: {validation_checks['input_documents']}")
                logger.info(f"   - 处理后文档: {validation_checks['processed_documents']}")
                logger.info(f"   - 处理时间: {validation_checks['processing_time']:.2f}秒")
                logger.info(f"   - 去重功能: {'正常' if deduplication_effective else '未生效'}")
            else:
                logger.error("❌ 完整数据处理管道验证失败")
                
            return validation_result
            
        except Exception as e:
            logger.error(f"完整管道验证异常: {str(e)}")
            return {
                'test_name': 'full_pipeline',
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def validate_search_functionality(self) -> Dict[str, Any]:
        """验证搜索功能"""
        logger.info("开始验证搜索功能")
        
        try:
            # 测试不同类型的搜索
            search_tests = []
            
            # 1. Elasticsearch搜索
            es_search = await data_processor_manager.search_documents(
                query="央行 降准",
                search_type="elasticsearch",
                limit=5
            )
            search_tests.append({
                'type': 'elasticsearch',
                'success': es_search.get('success', False),
                'results_count': len(es_search.get('result', {}).get('documents', [])),
                'details': es_search
            })
            
            # 2. 向量搜索
            vector_search = await data_processor_manager.search_documents(
                query="人工智能 科技股",
                search_type="vector",
                limit=5
            )
            search_tests.append({
                'type': 'vector',
                'success': vector_search.get('success', False),
                'results_count': len(vector_search.get('result', {}).get('documents', [])),
                'details': vector_search
            })
            
            # 3. 混合搜索
            hybrid_search = await data_processor_manager.search_documents(
                query="新能源汽车 投资机会",
                search_type="hybrid",
                limit=10
            )
            search_tests.append({
                'type': 'hybrid',
                'success': hybrid_search.get('success', False),
                'results_count': len(hybrid_search.get('result', {}).get('documents', [])),
                'details': hybrid_search
            })
            
            # 验证结果
            all_searches_successful = all(test['success'] for test in search_tests)
            total_results = sum(test['results_count'] for test in search_tests)
            
            validation_result = {
                'test_name': 'search_functionality',
                'success': all_searches_successful and total_results > 0,
                'search_tests': search_tests,
                'total_results': total_results,
                'timestamp': datetime.now().isoformat()
            }
            
            if validation_result['success']:
                logger.info("✅ 搜索功能验证通过")
                for test in search_tests:
                    logger.info(f"   - {test['type']}搜索: {test['results_count']}个结果")
            else:
                logger.error("❌ 搜索功能验证失败")
                
            return validation_result
            
        except Exception as e:
            logger.error(f"搜索功能验证异常: {str(e)}")
            return {
                'test_name': 'search_functionality',
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def validate_components_health(self) -> Dict[str, Any]:
        """验证组件健康状态"""
        logger.info("开始验证组件健康状态")
        
        try:
            # 获取系统统计信息
            system_stats = data_processor_manager.get_system_statistics()
            
            # 检查各组件状态
            component_health = {}
            overall_healthy = True
            
            for component, status in data_processor_manager.components_status.items():
                is_healthy = status.get('status') == 'healthy'
                component_health[component] = {
                    'healthy': is_healthy,
                    'status': status
                }
                if not is_healthy:
                    overall_healthy = False
            
            validation_result = {
                'test_name': 'components_health',
                'success': overall_healthy,
                'component_health': component_health,
                'system_statistics': system_stats,
                'timestamp': datetime.now().isoformat()
            }
            
            if overall_healthy:
                logger.info("✅ 组件健康状态验证通过")
                for component in component_health:
                    logger.info(f"   - {component}: 健康")
            else:
                logger.error("❌ 组件健康状态验证失败")
                for component, health in component_health.items():
                    status = "健康" if health['healthy'] else "异常"
                    logger.info(f"   - {component}: {status}")
                
            return validation_result
            
        except Exception as e:
            logger.error(f"组件健康验证异常: {str(e)}")
            return {
                'test_name': 'components_health',
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    async def run_comprehensive_validation(self) -> Dict[str, Any]:
        """运行综合验证"""
        logger.info("🚀 开始运行数据处理管道综合验证")
        self.validation_start_time = datetime.now()
        
        validation_results = {
            'overall_success': True,
            'tests': {},
            'summary': {},
            'start_time': self.validation_start_time.isoformat()
        }
        
        # 验证测试列表
        validation_tests = [
            ('initialization', self.validate_initialization),
            ('full_pipeline', self.validate_full_pipeline),
            ('search_functionality', self.validate_search_functionality),
            ('components_health', self.validate_components_health)
        ]
        
        # 执行所有验证测试
        for test_name, test_func in validation_tests:
            logger.info(f"执行验证测试: {test_name}")
            
            try:
                test_result = await test_func()
                validation_results['tests'][test_name] = test_result
                
                if not test_result.get('success', False):
                    validation_results['overall_success'] = False
                    
            except Exception as e:
                logger.error(f"验证测试 {test_name} 异常: {str(e)}")
                validation_results['tests'][test_name] = {
                    'test_name': test_name,
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                validation_results['overall_success'] = False
        
        # 生成验证摘要
        end_time = datetime.now()
        total_time = (end_time - self.validation_start_time).total_seconds()
        
        validation_results['summary'] = {
            'total_tests': len(validation_tests),
            'passed_tests': sum(1 for test in validation_results['tests'].values() if test.get('success', False)),
            'failed_tests': sum(1 for test in validation_results['tests'].values() if not test.get('success', False)),
            'total_time': total_time,
            'end_time': end_time.isoformat()
        }
        
        # 输出验证结果
        if validation_results['overall_success']:
            logger.info("🎉 数据处理管道综合验证全部通过！")
        else:
            logger.error("❌ 数据处理管道综合验证存在失败项")
        
        logger.info(f"验证摘要:")
        logger.info(f"  - 总测试数: {validation_results['summary']['total_tests']}")
        logger.info(f"  - 通过测试: {validation_results['summary']['passed_tests']}")
        logger.info(f"  - 失败测试: {validation_results['summary']['failed_tests']}")
        logger.info(f"  - 总耗时: {total_time:.2f}秒")
        
        return validation_results
    
    def save_validation_report(self, validation_results: Dict[str, Any], output_file: str = None):
        """保存验证报告"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"validation_report_{timestamp}.json"
        
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(validation_results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"验证报告已保存到: {output_file}")
            
        except Exception as e:
            logger.error(f"保存验证报告失败: {str(e)}")


async def main():
    """主函数"""
    # 配置日志
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO"
    )
    
    # 创建验证器
    validator = PipelineValidator()
    
    try:
        # 运行综合验证
        validation_results = await validator.run_comprehensive_validation()
        
        # 保存验证报告
        validator.save_validation_report(validation_results)
        
        # 清理资源
        data_processor_manager.cleanup()
        
        # 返回结果
        return validation_results
        
    except Exception as e:
        logger.error(f"验证过程异常: {str(e)}")
        return {
            'overall_success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }


if __name__ == "__main__":
    # 运行验证
    results = asyncio.run(main())
    
    # 输出最终结果
    if results.get('overall_success', False):
        print("\n🎉 数据处理管道验证成功！系统已准备就绪。")
        sys.exit(0)
    else:
        print("\n❌ 数据处理管道验证失败，请检查错误信息。")
        sys.exit(1)
