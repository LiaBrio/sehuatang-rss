import time
from app.config import CACHE_TTL

_cache: dict = {}


def cache_get(key: str):
    """获取缓存，未过期则返回数据，过期或不存在返回 None"""
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL:
            return data
        del _cache[key]
    return None


def cache_set(key: str, data):
    """设置缓存"""
    _cache[key] = (time.time(), data)


def cache_clear():
    """清空缓存"""
    _cache.clear()
