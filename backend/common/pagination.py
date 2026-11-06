"""分页（架构文档 §5.3）：统一 page / page_size / count / total_pages / results。"""

from rest_framework.pagination import PageNumberPagination

from common.response import api_response


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100  # 上限 100，超出自动钳制

    def get_paginated_response(self, data):
        return api_response(
            data={
                "count": self.page.paginator.count,
                "page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "total_pages": self.page.paginator.num_pages,
                "results": data,
            }
        )
