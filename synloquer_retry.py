"""
Synloquer 重试机制

对网络请求等可能瞬时失败的操作提供指数退避重试。
"""

import time
from functools import wraps

import synloquer_logger as logger


def retry(max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 30.0,
          retry_on: tuple = (Exception,)):
    """
    指数退避重试装饰器。

    Args:
        max_attempts: 最大尝试次数（含首次）
        base_delay: 首次重试延迟（秒）
        max_delay: 最大延迟上限（秒）
        retry_on: 需要重试的异常类型元组
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    last_exception = e
                    if attempt < max_attempts:
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        logger.warning(f"{func.__name__} 第{attempt}次失败: {e}，{delay:.1f}秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} 重试{max_attempts}次后仍失败: {e}")
            raise last_exception
        return wrapper
    return decorator


def retry_request(func, *args, max_attempts: int = 3, base_delay: float = 1.0, **kwargs):
    """
    对 requests 调用进行重试的便捷函数。

    Returns:
        requests.Response 或 None（全部失败时）
    """
    import requests as _requests

    last_exception = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = func(*args, **kwargs)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", base_delay * (2 ** (attempt - 1))))
                if attempt < max_attempts:
                    logger.warning(f"API 限流(429)，{retry_after}秒后重试...")
                    time.sleep(retry_after)
                    continue
            resp.raise_for_status()
            return resp
        except (_requests.ConnectionError, _requests.Timeout, _requests.HTTPError) as e:
            last_exception = e
            if attempt < max_attempts:
                delay = min(base_delay * (2 ** (attempt - 1)), 30.0)
                logger.warning(f"请求第{attempt}次失败: {e}，{delay:.1f}秒后重试...")
                time.sleep(delay)
            else:
                logger.error(f"请求重试{max_attempts}次后仍失败: {e}")
    raise last_exception
