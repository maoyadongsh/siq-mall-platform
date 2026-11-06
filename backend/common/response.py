"""统一响应结构（架构文档 §5.2）。

成功：{"code":0,"message":"ok","data":{},"request_id":"...","timestamp":"..."}
失败：额外包含 "errors": [{"field": "...", "detail": "..."}]
"""

from contextvars import ContextVar
from datetime import datetime
from zoneinfo import ZoneInfo

from rest_framework.response import Response

TIMEZONE_SHANGHAI = ZoneInfo("Asia/Shanghai")

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def set_request_id(value: str) -> None:
    _request_id_ctx.set(value)


def get_request_id() -> str:
    return _request_id_ctx.get()


def now_iso() -> str:
    """接口统一输出带时区的本地时间（UTC 存储，输出 +08:00）。"""
    return datetime.now(TIMEZONE_SHANGHAI).isoformat(timespec="seconds")


def error_body(code: int, message: str, errors: list[dict] | None = None) -> dict:
    body: dict = {
        "code": code,
        "message": message,
        "data": None,
        "request_id": get_request_id(),
        "timestamp": now_iso(),
    }
    if errors:
        body["errors"] = errors
    return body


def api_response(
    data=None,
    code: int = 0,
    message: str = "ok",
    errors: list[dict] | None = None,
    http_status: int = 200,
) -> Response:
    body: dict = {
        "code": code,
        "message": message,
        "data": data,
        "request_id": get_request_id(),
        "timestamp": now_iso(),
    }
    if errors:
        body["errors"] = errors
    return Response(body, status=http_status)


def success(data=None, message: str = "ok", http_status: int = 200) -> Response:
    return api_response(data=data, code=0, message=message, http_status=http_status)
