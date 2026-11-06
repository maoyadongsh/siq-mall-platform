"""基础接口的 OpenAPI 契约，与统一响应保持一致。"""

from rest_framework import serializers


class DependencySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["ok", "fail"])
    latency_ms = serializers.FloatField()
    detail = serializers.CharField(allow_blank=True)


class ChecksSerializer(serializers.Serializer):
    database = DependencySerializer()
    redis = DependencySerializer()


class HealthDataSerializer(serializers.Serializer):
    service = serializers.CharField()
    version = serializers.CharField()
    environment = serializers.CharField()
    status = serializers.ChoiceField(choices=["ok", "degraded"])
    checks = ChecksSerializer()
    server_time = serializers.DateTimeField()


class EnvelopeSerializer(serializers.Serializer):
    code = serializers.IntegerField()
    message = serializers.CharField()
    request_id = serializers.CharField()
    timestamp = serializers.DateTimeField()


class HealthResponseSerializer(EnvelopeSerializer):
    data = HealthDataSerializer()


class RefreshDataSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()


class RefreshResponseSerializer(EnvelopeSerializer):
    data = RefreshDataSerializer()


class ErrorResponseSerializer(EnvelopeSerializer):
    data = serializers.JSONField(allow_null=True)
    errors = serializers.ListField(child=serializers.DictField(), required=False)
