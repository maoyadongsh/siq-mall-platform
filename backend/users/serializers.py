import json
from pathlib import Path

from rest_framework import serializers

from accounts.serializers import (
    EmptyResponseSerializer as EmptyResponseSerializer,
    MeResponseSerializer,
)
from common.serializers import EnvelopeSerializer


REGIONS = json.loads(
    (Path(__file__).parent / "data" / "regions-v2.2.0.json").read_text(encoding="utf-8")
)


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

    def validate(self, attrs):
        code = attrs["region_code"]
        for field, table, key in (
            ("province", "province_list", code[:2] + "0000"),
            ("city", "city_list", code[:4] + "00"),
            ("district", "county_list", code),
        ):
            if REGIONS[table].get(key) != attrs[field]:
                raise serializers.ValidationError({field: "请重新选择收货地区"})
        return attrs


class RegionDirectorySerializer(serializers.Serializer):
    province_list = serializers.DictField(child=serializers.CharField())
    city_list = serializers.DictField(child=serializers.CharField())
    county_list = serializers.DictField(child=serializers.CharField())


class RegionResponseSerializer(EnvelopeSerializer):
    data = RegionDirectorySerializer()


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
