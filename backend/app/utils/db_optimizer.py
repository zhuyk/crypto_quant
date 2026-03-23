"""
数据库查询优化模块
查询缓存、批量操作、连接池优化
"""
import time
import logging
from typing import Optional, Any, Callable, List, Dict, TypeVar, Generic
from functools import wraps
from contextlib import contextmanager
from sqlalchemy import text
from sqlalchemy.orm import Session, Query
from sqlalchemy.exc import SQLAlchemyError

from app.utils.cache import get_cache, CacheKeys
from app.core.config import settings

logger = logging.getLogger(__name__)

T = TypeVar('T')


class QueryOptimizer:
    """查询优化器"""
    
    def __init__(self, session: Session):
        self.session = session
        self.cache = get_cache()
        self._query_log: List[Dict] = []
    
    def execute_with_cache(
        self,
        query_key: str,
        query_func: Callable[[], Any],
        expire: int = 300,
        force_refresh: bool = False,
    ) -> Any:
        """
        带缓存执行查询
        
        Args:
            query_key: 缓存键
            query_func: 查询函数
            expire: 缓存过期时间 (秒)
            force_refresh: 强制刷新缓存
        
        Returns:
            查询结果
        """
        if not force_refresh:
            # 尝试从缓存获取
            cached = self.cache.get(query_key)
            if cached is not None:
                logger.debug(f"✅ 查询缓存命中：{query_key}")
                return cached
        
        # 执行查询
        start_time = time.time()
        result = query_func()
        duration = (time.time() - start_time) * 1000
        
        # 记录查询日志
        self._query_log.append({
            "key": query_key,
            "duration_ms": duration,
            "cache_hit": False,
            "timestamp": time.time(),
        })
        
        # 写入缓存
        if result is not None:
            self.cache.set(query_key, result, expire=expire)
            logger.debug(f"💾 查询已缓存：{query_key} ({duration:.2f}ms)")
        
        return result
    
    def bulk_insert(
        self,
        model_class: Any,
        items: List[Dict],
        batch_size: int = 100,
    ) -> int:
        """
        批量插入
        
        Args:
            model_class: SQLAlchemy 模型类
            items: 数据列表
            batch_size: 每批数量
        
        Returns:
            插入数量
        """
        if not items:
            return 0
        
        total_inserted = 0
        start_time = time.time()
        
        # 分批插入
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            try:
                self.session.bulk_insert_mappings(model_class, batch)
                self.session.commit()
                total_inserted += len(batch)
                
                logger.debug(f"✅ 批量插入 {len(batch)} 条记录")
            except SQLAlchemyError as e:
                logger.error(f"批量插入失败：{e}")
                self.session.rollback()
                # 继续处理下一批
                continue
        
        duration = (time.time() - start_time) * 1000
        logger.info(
            f"📊 批量插入完成：{total_inserted}/{len(items)} 条记录 ({duration:.2f}ms)"
        )
        
        return total_inserted
    
    def bulk_update(
        self,
        model_class: Any,
        items: List[Dict],
        filter_field: str = "id",
        batch_size: int = 100,
    ) -> int:
        """
        批量更新
        
        Args:
            model_class: SQLAlchemy 模型类
            items: 数据列表 (必须包含 filter_field)
            filter_field: 筛选字段
            batch_size: 每批数量
        
        Returns:
            更新数量
        """
        if not items:
            return 0
        
        total_updated = 0
        start_time = time.time()
        
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            try:
                self.session.bulk_update_mappings(model_class, batch)
                self.session.commit()
                total_updated += len(batch)
                
                logger.debug(f"✅ 批量更新 {len(batch)} 条记录")
            except SQLAlchemyError as e:
                logger.error(f"批量更新失败：{e}")
                self.session.rollback()
                continue
        
        duration = (time.time() - start_time) * 1000
        logger.info(
            f"📊 批量更新完成：{total_updated}/{len(items)} 条记录 ({duration:.2f}ms)"
        )
        
        return total_updated
    
    def optimize_query(
        self,
        query: Query,
        enable_cache: bool = True,
        cache_expire: int = 300,
    ) -> Query:
        """
        优化查询
        
        Args:
            query: SQLAlchemy Query 对象
            enable_cache: 启用缓存
            cache_expire: 缓存过期时间
        
        Returns:
            优化后的 Query
        """
        # 启用查询缓存
        if enable_cache:
            query = query.enable_caching()
        
        # 添加执行超时 (如果支持)
        # query = query.execution_options(stream_results=True)
        
        return query
    
    def get_slow_queries(self, threshold_ms: float = 100) -> List[Dict]:
        """获取慢查询日志"""
        return [
            q for q in self._query_log
            if q.get("duration_ms", 0) > threshold_ms
        ]
    
    def get_query_stats(self) -> Dict:
        """获取查询统计"""
        if not self._query_log:
            return {
                "total_queries": 0,
                "avg_duration_ms": 0,
                "cache_hit_rate": 0,
            }
        
        total = len(self._query_log)
        cache_hits = sum(1 for q in self._query_log if q.get("cache_hit"))
        total_duration = sum(q.get("duration_ms", 0) for q in self._query_log)
        
        return {
            "total_queries": total,
            "cache_hits": cache_hits,
            "cache_misses": total - cache_hits,
            "cache_hit_rate": cache_hits / total if total > 0 else 0,
            "avg_duration_ms": total_duration / total if total > 0 else 0,
            "total_duration_ms": total_duration,
        }
    
    def clear_query_log(self):
        """清空查询日志"""
        self._query_log = []


@contextmanager
def transaction_scope(session: Session, rollback_on_error: bool = True):
    """
    事务作用域上下文管理器
    
    Args:
        session: SQLAlchemy Session
        rollback_on_error: 错误时回滚
    
    Example:
        with transaction_scope(db) as tx:
            tx.add(obj1)
            tx.add(obj2)
    """
    try:
        yield session
        session.commit()
        logger.debug("✅ 事务提交成功")
    except Exception as e:
        if rollback_on_error:
            session.rollback()
            logger.error(f"❌ 事务回滚：{e}")
        raise
    finally:
        session.close()


def query_cache(
    key_prefix: str = "query",
    expire: int = 300,
    key_builder: Optional[Callable[..., str]] = None,
):
    """
    查询缓存装饰器
    
    Args:
        key_prefix: 缓存键前缀
        expire: 过期时间 (秒)
        key_builder: 自定义键构建函数
    
    Example:
        @query_cache(key_prefix="user", expire=600)
        def get_user_by_id(db: Session, user_id: int):
            return db.query(User).filter(User.id == user_id).first()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            cache = get_cache()
            
            # 构建缓存键
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                func_name = func.__name__
                param_str = f"{args}:{sorted(kwargs.items())}"
                import hashlib
                param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
                cache_key = f"{key_prefix}:{func_name}:{param_hash}"
            
            # 尝试缓存
            cached = cache.get(cache_key)
            if cached is not None:
                logger.debug(f"✅ 查询缓存命中：{cache_key}")
                return cached
            
            # 执行查询
            start_time = time.time()
            result = func(*args, **kwargs)
            duration = (time.time() - start_time) * 1000
            
            # 写入缓存
            if result is not None:
                cache.set(cache_key, result, expire=expire)
                logger.debug(f"💾 查询已缓存：{cache_key} ({duration:.2f}ms)")
            
            return result
        
        return wrapper
    return decorator


def batch_operation(batch_size: int = 100):
    """
    批量操作装饰器
    
    Args:
        batch_size: 每批数量
    
    Example:
        @batch_operation(batch_size=100)
        def process_items(items: List[Dict]):
            # 处理逻辑
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(items: List[Any], *args, **kwargs) -> Any:
            if not items:
                return []
            
            results = []
            start_time = time.time()
            
            # 分批处理
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                logger.debug(f"处理批次 {i // batch_size + 1}, 数量：{len(batch)}")
                
                try:
                    batch_result = func(batch, *args, **kwargs)
                    if batch_result:
                        results.extend(batch_result)
                except Exception as e:
                    logger.error(f"批次处理失败：{e}")
                    continue
            
            duration = (time.time() - start_time) * 1000
            logger.info(
                f"📊 批量处理完成：{len(results)} 条记录 ({duration:.2f}ms)"
            )
            
            return results
        
        return wrapper
    return decorator


# 性能监控装饰器
def monitor_performance(threshold_ms: float = 100):
    """
    性能监控装饰器
    
    Args:
        threshold_ms: 慢操作阈值 (毫秒)
    
    Example:
        @monitor_performance(threshold_ms=50)
        def slow_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = (time.time() - start_time) * 1000
                if duration > threshold_ms:
                    logger.warning(
                        f"⚠️  慢操作：{func.__name__} ({duration:.2f}ms > {threshold_ms}ms)"
                    )
                else:
                    logger.debug(f"✅ {func.__name__} ({duration:.2f}ms)")
        
        return wrapper
    return decorator
