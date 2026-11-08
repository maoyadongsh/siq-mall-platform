import hmac

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from accounts.models import VerificationChallenge
from accounts.services import consume_challenge, digest, user_summary
from common.constants import ErrorCode
from common.exceptions import BusinessError
from common.response import success

from .models import Address
from .serializers import (
    REGIONS,
    RegionResponseSerializer,
    AddressDeleteSerializer,
    AddressInputSerializer,
    AddressListResponseSerializer,
    AddressResponseSerializer,
    AddressWriteSerializer,
    EmptyResponseSerializer,
    PhoneBindSerializer,
    ProfileResponseSerializer,
    ProfileUpdateSerializer,
)
from .services import create_address, delete_address, make_default, update_address


class ProfileAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["用户资料"], responses={200: ProfileResponseSerializer})
    def get(self, request):
        return success(data=user_summary(request.user))

    @extend_schema(
        tags=["用户资料"],
        request=ProfileUpdateSerializer,
        responses={200: ProfileResponseSerializer},
    )
    def patch(self, request):
        serializer = ProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.profile.nickname = serializer.validated_data["nickname"]
        request.user.profile.save(update_fields=["nickname", "updated_at"])
        return success(data=user_summary(request.user))


class PhoneBindAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["用户资料"],
        request=PhoneBindSerializer,
        responses={200: ProfileResponseSerializer, 409: EmptyResponseSerializer},
    )
    def post(self, request):
        serializer = PhoneBindSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        candidate = VerificationChallenge.objects.filter(
            challenge_id=data["challenge_id"],
            purpose="phone_bind",
            consumed_at__isnull=True,
        ).first()
        if (
            candidate is None
            or candidate.user_id != request.user.id
            or not hmac.compare_digest(
                candidate.target_digest, digest(data["phone"].lower())
            )
        ):
            raise BusinessError(
                ErrorCode.PERMISSION_DENIED, "验证挑战与当前操作不匹配", http_status=403
            )
        challenge = consume_challenge(data["challenge_id"], "phone_bind", data["code"])
        profile = request.user.profile
        if (
            profile.phone != data["phone"]
            and type(profile)
            .objects.filter(phone=data["phone"])
            .exclude(user=request.user)
            .exists()
        ):
            raise BusinessError(
                ErrorCode.PHONE_CONFLICT, "手机号已被其他账号绑定", http_status=409
            )
        try:
            profile.phone = data["phone"]
            profile.phone_verified_at = challenge.consumed_at
            profile.save(update_fields=["phone", "phone_verified_at", "updated_at"])
        except IntegrityError as exc:
            raise BusinessError(
                ErrorCode.PHONE_CONFLICT, "手机号已被其他账号绑定", http_status=409
            ) from exc
        return success(data=user_summary(request.user))


class RegionDirectoryAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["地址"], responses={200: RegionResponseSerializer})
    def get(self, request):
        return success(data=REGIONS)


class AddressListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["地址"], responses={200: AddressListResponseSerializer})
    def get(self, request):
        addresses = Address.objects.filter(user=request.user).order_by(
            "-is_default", "-updated_at", "-id"
        )
        return success(data=[address_to_dict(address) for address in addresses])

    @extend_schema(
        tags=["地址"],
        request=AddressInputSerializer,
        responses={201: AddressResponseSerializer, 409: EmptyResponseSerializer},
    )
    def post(self, request):
        serializer = AddressInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = create_address(request.user, serializer.validated_data)
        return success(data=address_to_dict(address), http_status=201)


def address_to_dict(address):
    return {
        "id": str(address.id),
        "recipient": address.recipient,
        "phone": address.phone,
        "province": address.province,
        "city": address.city,
        "district": address.district,
        "region_code": address.region_code,
        "detail": address.detail,
        "is_default": address.is_default,
        "version": address.version,
        "created_at": address.created_at,
        "updated_at": address.updated_at,
    }


class AddressDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["地址"],
        request=AddressWriteSerializer,
        responses={
            200: AddressResponseSerializer,
            404: EmptyResponseSerializer,
            409: EmptyResponseSerializer,
        },
    )
    def patch(self, request, address_id):
        serializer = AddressWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        address = update_address(request.user, address_id, serializer.validated_data)
        return success(data=address_to_dict(address))

    @extend_schema(
        tags=["地址"],
        request=AddressDeleteSerializer,
        responses={
            200: EmptyResponseSerializer,
            404: EmptyResponseSerializer,
            409: EmptyResponseSerializer,
        },
    )
    def delete(self, request, address_id):
        serializer = AddressDeleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delete_address(
            request.user, address_id, serializer.validated_data["expected_version"]
        )
        return success(data=None)


class AddressDefaultAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["地址"],
        request=None,
        responses={200: AddressResponseSerializer, 404: EmptyResponseSerializer},
    )
    def post(self, request, address_id):
        address = make_default(request.user, address_id)
        return success(data=address_to_dict(address))
