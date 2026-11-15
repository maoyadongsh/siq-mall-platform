from django_filters import ChoiceFilter, FilterSet, IsoDateTimeFilter, UUIDFilter

from .models import Order


class OrderFilter(FilterSet):
    status = ChoiceFilter(
        choices=[
            ("pending", "pending"),
            ("paid", "paid"),
            ("shipped", "shipped"),
            ("completed", "completed"),
            ("canceled", "canceled"),
        ]
    )
    created_before = IsoDateTimeFilter(field_name="created_at", lookup_expr="lte")
    created_after = IsoDateTimeFilter(field_name="created_at", lookup_expr="gte")
    order_no = UUIDFilter()

    class Meta:
        model = Order
        fields: list[str] = []
