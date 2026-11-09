from uuid import UUID
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter
from common.response import success
from common.serializers import EnvelopeSerializer
from . import services


class StrictInput(serializers.Serializer):
    def to_internal_value(self, data):
        if isinstance(data, dict) and set(data) - set(self.fields):
            raise serializers.ValidationError(
                {field: "不支持此字段" for field in set(data) - set(self.fields)}
            )
        return super().to_internal_value(data)


class Line(StrictInput):
    sku_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    quantity = serializers.IntegerField(min_value=1, max_value=99)


class Basket(StrictInput):
    items = Line(many=True, allow_empty=False, max_length=50)

    def validate_items(self, items):
        if len(items) != len({r["sku_id"] for r in items}):
            raise serializers.ValidationError("同一规格请合并数量后提交")
        return items


class QuoteInput(Basket):
    address_id = serializers.IntegerField(min_value=1, max_value=2**63 - 1)
    user_coupon_id = serializers.IntegerField(required=False, allow_null=True)

    def validate_user_coupon_id(self, value):
        if value is not None:
            raise serializers.ValidationError("当前试算暂不支持优惠券")
        return value


class Version(StrictInput):
    expected_version = serializers.IntegerField(min_value=1)


class Update(Version):
    quantity = serializers.IntegerField(min_value=1, max_value=99, required=False)
    selected = serializers.BooleanField(required=False)

    def validate(self, data):
        if len(data) == 1:
            raise serializers.ValidationError("请指定数量或选中状态")
        return data


class Item(serializers.Serializer):
    id = serializers.CharField()
    sku_id = serializers.CharField()
    product_id = serializers.CharField()
    title = serializers.CharField()
    label = serializers.CharField()
    current_price = serializers.CharField()
    quantity = serializers.IntegerField()
    version = serializers.IntegerField()
    selected = serializers.BooleanField()
    available = serializers.BooleanField()
    available_stock = serializers.IntegerField()
    unavailable_reason = serializers.CharField()


class CartData(serializers.Serializer):
    items = Item(many=True)
    version = serializers.IntegerField()


class Rejected(serializers.Serializer):
    sku_id = serializers.CharField()
    quantity = serializers.IntegerField()
    reason = serializers.CharField()


class Merged(CartData):
    adjustments = Rejected(many=True)
    requires_confirmation = serializers.BooleanField()


class CartResponse(EnvelopeSerializer):
    data = CartData()


class ItemResponse(EnvelopeSerializer):
    data = Item()


class MergeResponse(EnvelopeSerializer):
    data = Merged()


class Deleted(EnvelopeSerializer):
    data = serializers.JSONField(allow_null=True)


class QuoteLine(serializers.Serializer):
    sku_id = serializers.CharField()
    title = serializers.CharField()
    label = serializers.CharField()
    quantity = serializers.IntegerField()
    unit_price = serializers.CharField()
    line_amount = serializers.CharField()
    discount_allocated = serializers.CharField()


class QuoteData(serializers.Serializer):
    quote_id = serializers.UUIDField()
    expires_at = serializers.DateTimeField()
    items = QuoteLine(many=True)
    goods_amount = serializers.CharField()
    freight_amount = serializers.CharField()
    discount_amount = serializers.CharField()
    payable_amount = serializers.CharField()
    currency = serializers.CharField()
    address_summary = serializers.DictField()
    selected_coupon = serializers.JSONField(allow_null=True)
    unavailable_coupons = serializers.ListField()


class QuoteResponse(EnvelopeSerializer):
    data = QuoteData()


def body(schema, request):
    form = schema(data=request.data)
    form.is_valid(raise_exception=True)
    return form.validated_data


def key(request):
    try:
        return UUID(request.headers.get("Idempotency-Key", ""))
    except ValueError as exc:
        raise serializers.ValidationError(
            {"Idempotency-Key": "请提供有效UUID"}
        ) from exc


HEADER = OpenApiParameter(
    "Idempotency-Key", UUID, OpenApiParameter.HEADER, required=True
)


class Items(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="cart_items_list", responses=CartResponse)
    def get(self, request):
        return success(services.contents(request.user))

    @extend_schema(request=Line, responses={201: ItemResponse}, parameters=[HEADER])
    def post(self, request):
        return success(
            services.add_items(
                request.user, "add", key(request), [body(Line, request)]
            ),
            http_status=201,
        )


class Detail(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=Update, responses=ItemResponse)
    def patch(self, request, pk):
        return success(services.modify(request.user, pk, body(Update, request)))

    @extend_schema(request=Version, responses={200: Deleted})
    def delete(self, request, pk):
        return success(
            services.modify(request.user, pk, body(Version, request), remove=True)
        )


class Merge(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=Basket, responses=MergeResponse, parameters=[HEADER])
    def post(self, request):
        return success(
            services.add_items(
                request.user, "merge", key(request), body(Basket, request)["items"]
            )
        )


class Checkout(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=QuoteInput, responses=QuoteResponse)
    def post(self, request):
        return success(services.quote(request.user, body(QuoteInput, request)))
