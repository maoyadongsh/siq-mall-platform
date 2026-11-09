"""业务异常与全局异常处理（架构文档 §5.2 / §5.4 / §8.2）。"""

import logging

from django.http import JsonResponse
from rest_framework.exceptions import ValidationError
from rest_framework.views import exception_handler as drf_exception_handler

from common.constants import ErrorCode
from common.response import api_response, error_body

logger = logging.getLogger("mall")

_STATUS_CODE_MAP = {
    400: ErrorCode.INVALID_PARAM,
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.PERMISSION_DENIED,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.METHOD_NOT_ALLOWED,
    429: ErrorCode.THROTTLED,
}

_STATUS_MESSAGE_MAP = {
    400: "参数校验失败",
    401: "未认证或登录已过期",
    403: "无权限访问该资源",
    404: "资源不存在",
    405: "请求方法不允许",
    409: "请求与当前资源状态冲突",
    429: "请求过于频繁，请稍后再试",
}


class BusinessError(Exception):
    """业务异常：由 service 层抛出，全局处理器转统一响应。

    :param code: 业务错误码（common.constants.ErrorCode）
    :param message: 面向用户的可读文案（不得包含堆栈/SQL）
    :param http_status: 对应的 HTTP 状态码
    :param errors: 字段级错误明细
    """

    def __init__(
        self,
        code: int,
        message: str,
        http_status: int = 400,
        errors: list[dict] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.errors = errors


def _extract_errors(exc: Exception) -> list[dict] | None:
    if not isinstance(exc, ValidationError) or not isinstance(exc.detail, dict):
        return None
    items: list[dict] = []
    for field, detail in exc.detail.items():
        text = (
            "; ".join(str(item) for item in detail)
            if isinstance(detail, (list, tuple))
            else str(detail)
        )
        items.append({"field": field, "detail": text})
    return items


def api_exception_handler(exc, context):
    """DRF 全局异常处理器：所有异常输出统一结构，5xx 只记录日志不暴露细节。"""
    if isinstance(exc, BusinessError):
        logger.info("业务异常 code=%s message=%s", exc.code, exc.message)
        response = api_response(
            code=exc.code,
            message=exc.message,
            errors=exc.errors,
            http_status=exc.http_status,
        )

        if exc.code == ErrorCode.OPERATION_BUSY:
            response["Retry-After"] = "1"
        return response

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.exception("未处理异常：%s", exc)
        return api_response(
            code=ErrorCode.SERVER_ERROR,
            message="服务内部错误，请稍后重试",
            http_status=500,
        )

    status_code = response.status_code
    code = _STATUS_CODE_MAP.get(status_code, ErrorCode.SERVER_ERROR)
    message = _STATUS_MESSAGE_MAP.get(status_code, "请求失败")
    errors = _extract_errors(exc)
    if status_code == 400 and errors:
        message = "参数校验失败"
    result = api_response(
        code=code, message=message, errors=errors, http_status=status_code
    )
    for header in ("WWW-Authenticate", "Retry-After"):
        if header in response:
            result[header] = response[header]
    return result


def handler404(request, exception):
    """未匹配路由：Django 层 404 也返回统一 JSON（DEBUG=False 生效）。"""
    return JsonResponse(error_body(ErrorCode.NOT_FOUND, "资源不存在"), status=404)


def handler500(request):
    return JsonResponse(
        error_body(ErrorCode.SERVER_ERROR, "服务内部错误，请稍后重试"), status=500
    )
