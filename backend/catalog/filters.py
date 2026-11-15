from django.shortcuts import get_object_or_404
from django_filters import CharFilter, FilterSet, NumberFilter

from .category_services import descendants
from .models import Category, Product


class ProductFilter(FilterSet):
    q = CharFilter(method="filter_q")
    category = NumberFilter(
        method="filter_category", error_messages={"invalid": "请输入有效分类"}
    )
    min_price = NumberFilter(
        field_name="min_price",
        lookup_expr="gte",
        min_value=0,
        error_messages={"invalid": "请输入非负金额"},
    )
    max_price = NumberFilter(
        field_name="min_price",
        lookup_expr="lte",
        min_value=0,
        error_messages={"invalid": "请输入非负金额"},
    )

    class Meta:
        model = Product
        fields: list[str] = []

    def filter_q(self, queryset, name, value):
        return queryset.filter(title__icontains=value[:120])

    def filter_category(self, queryset, name, value):
        category = get_object_or_404(Category, pk=value, enabled=True)
        return queryset.filter(category_id__in=descendants(category))
