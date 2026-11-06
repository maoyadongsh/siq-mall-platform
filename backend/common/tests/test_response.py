from common.response import api_response, error_body


def test_success_response_structure():
    body = api_response(data={"a": 1}).data
    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["data"] == {"a": 1}
    assert set(body) == {"code", "message", "data", "request_id", "timestamp"}


def test_error_body_contains_errors():
    body = error_body(
        10001, "参数校验失败", [{"field": "phone", "detail": "格式不正确"}]
    )
    assert body["code"] == 10001
    assert body["data"] is None
    assert body["errors"][0]["field"] == "phone"
