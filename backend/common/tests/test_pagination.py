from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from common.pagination import StandardPagination


class _FakeView:
    pass


factory = APIRequestFactory()


def _drf_request(url: str) -> Request:
    return Request(factory.get(url))


def test_page_size_is_clamped_to_100():
    request = _drf_request("/api/v1/items/?page_size=500")
    paginator = StandardPagination()
    page = paginator.paginate_queryset(list(range(200)), request, view=_FakeView())

    assert paginator.get_page_size(request) == 100
    assert len(page) == 100


def test_default_page_size_is_20():
    request = _drf_request("/api/v1/items/")
    paginator = StandardPagination()
    page = paginator.paginate_queryset(list(range(200)), request, view=_FakeView())

    assert paginator.get_page_size(request) == 20
    assert len(page) == 20
