from rest_framework import serializers

from accounts.serializers import (
    EmptyResponseSerializer as EmptyResponseSerializer,
    MeResponseSerializer,
)
from common.serializers import EnvelopeSerializer


class ProfileUpdateSerializer(serializers.Serializer):
    nickname = serializers.CharField(max_length=50, trim_whitespace=True)


class ProfileResponseSerializer(MeResponseSerializer):
    pass


class PhoneBindSerializer(serializers.Serializer):
    challenge_id = serializers.UUIDField()
    code = serializers.CharField(write_only=True)
    phone = serializers.RegexField(r"^\+?[0-9][0-9\- ]{6,18}$")


class AddressInputSerializer(serializers.Serializer):
    recipient = serializers.CharField(max_length=50, trim_whitespace=True)
    phone = serializers.RegexField(r"^\+?[0-9][0-9\- ]{6,18}$")
    province = serializers.CharField(max_length=50, trim_whitespace=True)
    city = serializers.CharField(max_length=50, trim_whitespace=True)
    district = serializers.CharField(max_length=50, trim_whitespace=True)
    region_code = serializers.RegexField(r"^[0-9]{6,12}$")
    detail = serializers.CharField(max_length=200, trim_whitespace=True)
    is_default = serializers.BooleanField(required=False, default=False)


class AddressWriteSerializer(AddressInputSerializer):
    expected_version = serializers.IntegerField(min_value=1)


class AddressSerializer(AddressInputSerializer):
    id = serializers.CharField()
    version = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()


class AddressResponseSerializer(EnvelopeSerializer):
    data = AddressSerializer()


class AddressListResponseSerializer(EnvelopeSerializer):
    data = AddressSerializer(many=True)


class AddressDeleteSerializer(serializers.Serializer):
    expected_version = serializers.IntegerField(min_value=1)
