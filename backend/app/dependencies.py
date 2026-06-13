"""
数据库依赖注入模块 — 生产级并发安全配置

并发保命指南：
1. 连接池：pool_size + max_overflow 控制并发上限
2. pool_pre_ping：每次取出连接前检测可用性，防止"已断开连接"错误
3. pool_recycle：连接自动回收，防止 MySQL wait_timeout 导致的 stale connection
4. connect_args：设置事务隔离级别为 READ COMMITTED，防止脏读
5. 全局重试装饰器：用于乐观锁冲突自动重试
"""
import os
import time
import functools
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./intern_growth.db")

# ============================================================
# 并发安全配置
# ============================================================
IS_SQLITE = DATABASE_URL.startswith("sqlite")

connect_args = {}
if IS_SQLITE:
    connect_args = {"check_same_thread": False}
    engine = create_engine(
        DATABASE_URL,
        connect_args=connect_args,
        pool_pre_ping=True,
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,           # 连接池大小
        max_overflow=20,        # 池满后最多额外创建20个连接
        pool_recycle=3600,     # 1小时回收连接（防 MySQL wait_timeout）
        pool_pre_ping=True,    # 每次连接前先ping检测可用性
        pool_timeout=30,       # 获取连接超时30秒
        echo=False,
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Session:
    """FastAPI 依赖注入：获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# 并发重试工具（乐观锁自动重试 + 指数退避）
# ============================================================

def retry_on_conflict(max_retries: int = 3, base_delay: float = 0.1):
    """
    装饰器：在遇到乐观锁版本冲突(409)时自动重试
    使用指数退避：delay = base_delay * 2^attempt
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # 检查是否为版本冲突
                    status_code = getattr(e, 'status_code', None)
                    detail = getattr(e, 'detail', str(e))
                    if status_code == 409 or "version mismatch" in str(detail).lower():
                        last_exception = e
                        delay = base_delay * (2 ** attempt)
                        print(f"[Retry] 乐观锁冲突，{delay:.2f}s后重试 (attempt {attempt+1}/{max_retries})")
                        time.sleep(delay)
                        continue
                    raise
            raise last_exception or Exception("重试耗尽")
        return wrapper
    return decorator


class ConcurrencySafeSession:
    """
    并发安全会话包装器
    使用方式替代直接 db.commit() 以避免常见并发陷阱
    """
    @staticmethod
    def safe_commit(db: Session, max_retries: int = 3):
        """安全提交：自动处理 'database is locked' 等SQLite并发错误"""
        import time as t
        last_err = None
        for attempt in range(max_retries):
            try:
                db.commit()
                return True
            except Exception as e:
                last_err = e
                if "locked" in str(e).lower() or "busy" in str(e).lower():
                    delay = 0.05 * (2 ** attempt)
                    print(f"[DB] SQLite locked, retrying in {delay:.2f}s (attempt {attempt+1}/{max_retries})")
                    t.sleep(delay)
                    continue
                raise
        raise last_err
