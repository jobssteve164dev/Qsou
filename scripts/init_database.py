#!/usr/bin/env python3
"""
数据库初始化脚本
创建必要的数据库表和初始数据
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def create_database():
    """创建项目数据库"""
    try:
        # 连接到默认的 postgres 数据库
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="postgres",
            user="postgres",
            password=os.getenv("POSTGRES_PASSWORD", "")
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # 创建用户（如果不存在）
        cursor.execute("""
            SELECT 1 FROM pg_user WHERE usename = 'qsou';
        """)
        if not cursor.fetchone():
            cursor.execute("CREATE USER qsou WITH PASSWORD 'your_password';")
            print("✅ 创建用户 qsou 成功")
        
        # 创建数据库（如果不存在）
        cursor.execute("""
            SELECT 1 FROM pg_database WHERE datname = 'qsou_investment_intel';
        """)
        if not cursor.fetchone():
            cursor.execute("CREATE DATABASE qsou_investment_intel OWNER qsou;")
            print("✅ 创建数据库 qsou_investment_intel 成功")
        
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ 数据库创建失败: {e}")
        return False


def create_tables():
    """创建数据表"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="qsou_investment_intel",
            user="qsou",
            password="your_password"
        )
        cursor = conn.cursor()
        
        # 创建数据源表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_sources (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                base_url VARCHAR(500) NOT NULL,
                source_type VARCHAR(50) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                crawl_frequency INTEGER DEFAULT 3600,
                last_crawl_time TIMESTAMP,
                robots_txt_url VARCHAR(500),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ 创建数据源表成功")
        
        # 创建文档表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id SERIAL PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                url VARCHAR(1000) UNIQUE,
                source_id INTEGER REFERENCES data_sources(id),
                content_type VARCHAR(100),
                publish_time TIMESTAMP,
                crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content_hash VARCHAR(64),
                elasticsearch_id VARCHAR(100),
                qdrant_id INTEGER,
                is_processed BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ 创建文档表成功")
        
        # 创建用户表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) NOT NULL UNIQUE,
                email VARCHAR(255) NOT NULL UNIQUE,
                hashed_password VARCHAR(255) NOT NULL,
                is_active BOOLEAN DEFAULT TRUE,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );
        """)
        print("✅ 创建用户表成功")
        
        # 创建主题监控表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS topic_monitors (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                topic_name VARCHAR(200) NOT NULL,
                keywords TEXT[], 
                is_active BOOLEAN DEFAULT TRUE,
                alert_threshold FLOAT DEFAULT 0.8,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_check_time TIMESTAMP
            );
        """)
        print("✅ 创建主题监控表成功")
        
        # 创建爬虫任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_jobs (
                id SERIAL PRIMARY KEY,
                source_id INTEGER REFERENCES data_sources(id),
                job_status VARCHAR(50) DEFAULT 'pending',
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                items_scraped INTEGER DEFAULT 0,
                items_failed INTEGER DEFAULT 0,
                error_message TEXT,
                job_metadata JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ 创建爬虫任务表成功")
        
        # 创建系统配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_configs (
                id SERIAL PRIMARY KEY,
                config_key VARCHAR(100) NOT NULL UNIQUE,
                config_value TEXT,
                description TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        print("✅ 创建系统配置表成功")
        
        # 提交事务
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ 数据表创建失败: {e}")
        return False


def insert_initial_data():
    """插入初始数据"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="qsou_investment_intel",
            user="qsou",
            password="your_password"
        )
        cursor = conn.cursor()
        
        # 插入初始数据源
        initial_sources = [
            ('新浪财经', 'https://finance.sina.com.cn/', 'news', True, 1800),
            ('东方财富', 'https://www.eastmoney.com/', 'news', True, 1800),
            ('证券时报', 'https://www.stcn.com/', 'news', True, 3600),
            ('上交所公告', 'http://www.sse.com.cn/', 'announcement', True, 300),
            ('深交所公告', 'http://www.szse.cn/', 'announcement', True, 300),
        ]
        
        for name, url, source_type, is_active, frequency in initial_sources:
            cursor.execute("""
                INSERT INTO data_sources (name, base_url, source_type, is_active, crawl_frequency)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (name) DO NOTHING;
            """, (name, url, source_type, is_active, frequency))
        
        print("✅ 插入初始数据源成功")
        
        # 插入系统配置
        initial_configs = [
            ('elasticsearch_index_prefix', 'qsou_', 'Elasticsearch索引前缀'),
            ('qdrant_collection_name', 'investment_documents', 'Qdrant集合名称'),
            ('max_crawl_depth', '3', '最大爬取深度'),
            ('min_content_length', '100', '最小内容长度'),
            ('duplicate_threshold', '0.9', '重复内容阈值'),
        ]
        
        for key, value, desc in initial_configs:
            cursor.execute("""
                INSERT INTO system_configs (config_key, config_value, description)
                VALUES (%s, %s, %s)
                ON CONFLICT (config_key) DO NOTHING;
            """, (key, value, desc))
        
        print("✅ 插入系统配置成功")
        
        # 提交事务
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ 初始数据插入失败: {e}")
        return False


def main():
    """主函数"""
    print("🗄️  开始初始化 PostgreSQL 数据库...")
    print("=" * 50)
    
    # 创建数据库
    if not create_database():
        print("❌ 数据库创建失败，退出...")
        sys.exit(1)
    
    # 创建数据表
    if not create_tables():
        print("❌ 数据表创建失败，退出...")
        sys.exit(1)
    
    # 插入初始数据
    if not insert_initial_data():
        print("❌ 初始数据插入失败，退出...")
        sys.exit(1)
    
    print("=" * 50)
    print("🎉 数据库初始化完成！")
    print("\n📋 创建的表:")
    print("  - data_sources (数据源)")
    print("  - documents (文档)")
    print("  - users (用户)")
    print("  - topic_monitors (主题监控)")
    print("  - crawl_jobs (爬虫任务)")
    print("  - system_configs (系统配置)")
    
    return True


if __name__ == "__main__":
    main()
