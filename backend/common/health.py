"""健康检查：数据库与 Redis 连通性探测（架构文档 T01-07）。

探测不在事务内、不做缓存，任一依赖不通即返回 degraded。
"""

import time
import uuid
from dataclasses import dataclass

from django.core.cache import cache
from django.db import connection


@dataclass
class CheckResult:
    status: str  # ok / fail
    latency_ms: float
    detail: str = ""

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "latency_ms": round(self.latency_ms, 2),
            "detail": self.detail,
        }


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000


def check_database() -> CheckResult:
    started_at = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception as exc:  # 边界：外部依赖不可用属预期情况
        return CheckResult("fail", _elapsed_ms(started_at), type(exc).__name__)
    return CheckResult("ok", _elapsed_ms(started_at))


def check_cache() -> CheckResult:
    started_at = time.perf_counter()
    probe_key = f"health:probe:{uuid.uuid4().hex}"
    try:
        cache.set(probe_key, "1", timeout=5)
        if cache.get(probe_key) != "1":
            raise RuntimeError("缓存读写结果不一致")
        cache.delete(probe_key)
    except Exception as exc:  # 边界：外部依赖不可用属预期情况
        return CheckResult("fail", _elapsed_ms(started_at), type(exc).__name__)
    return CheckResult("ok", _elapsed_ms(started_at))
