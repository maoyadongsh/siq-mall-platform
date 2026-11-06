"""请求 ID 中间件：生成/透传 X-Request-Id，并输出结构化访问日志（架构文档 §5.2 / §9）。"""

import logging
import re
import time
import uuid

from common.response import set_request_id

logger = logging.getLogger("mall.access")

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


class RequestIdMiddleware:
    """为每个请求建立可追踪链路。

    外部传入的 X-Request-Id 只在符合"1-64 位字母数字/下划线/短横线"时复用，
    避免把任意字符串写进日志（日志注入）。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-Id", "")
        request_id = (
            incoming if _REQUEST_ID_PATTERN.match(incoming) else uuid.uuid4().hex[:16]
        )
        request.request_id = request_id
        set_request_id(request_id)

        started_at = time.perf_counter()
        response = None
        try:
            response = self.get_response(request)
            return response
        finally:
            status_code = (
                getattr(response, "status_code", 500) if response is not None else 500
            )
            logger.info(
                "access",
                extra={
                    "path": request.path,
                    "method": request.method,
                    "status": status_code,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
            if response is not None:
                response["X-Request-Id"] = request_id
            set_request_id("")
