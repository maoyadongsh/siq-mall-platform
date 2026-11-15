from django_filters import ChoiceFilter, FilterSet, NumberFilter, UUIDFilter

from .models import Review


class MineReviewFilter(FilterSet):
    order_no = UUIDFilter(field_name="order_item__order__order_no")

    class Meta:
        model = Review
        fields: list[str] = []


class OpsReviewFilter(FilterSet):
    status = ChoiceFilter(choices=Review.Status.choices)
    product_id = NumberFilter(min_value=1, max_value=2**63 - 1)

    class Meta:
        model = Review
        fields: list[str] = []
