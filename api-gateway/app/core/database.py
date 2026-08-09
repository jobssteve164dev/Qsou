"""
数据库连接和会话管理
"""

import asyncio
from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

# 创建异步数据库引擎
def create_database_url(sync: bool = False) -> str:
    """创建数据库URL"""
    url = settings.DATABASE_URL.strip()
    if not url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise RuntimeError("QSou 运行时只支持 PostgreSQL DATABASE_URL")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url

# 同步引擎（用于Alembic迁移）
engine = create_engine(
    create_database_url(sync=True),
    pool_pre_ping=True,
    pool_recycle=300,
)

# 异步引擎（用于应用程序）
async_engine = create_async_engine(
    create_database_url(),
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.DEBUG,
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 创建基础模型类
Base = declarative_base()
metadata = MetaData()


async def get_async_session() -> AsyncSession:
    """获取异步数据库会话"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            logger.error(f"数据库会话错误: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()


def get_session():
    """获取同步数据库会话"""
    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        logger.error(f"数据库会话错误: {e}")
        session.rollback()
        raise
    finally:
        session.close()


async def create_tables():
    """创建数据库表"""
    try:
        async with async_engine.begin() as conn:
            # 在实际项目中，这里会导入所有模型来创建表
            # from app.models import User, Document, SearchHistory
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ 数据库表创建成功")
    except Exception as e:
        logger.error(f"❌ 数据库表创建失败: {e}")
        raise


async def check_database_connection() -> bool:
    """检查数据库连接"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("✅ 数据库连接正常")
        return True
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        return False
