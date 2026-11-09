from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.views import APIView

from cart.api import HEADER, StrictInput, body, key
from common.response import success
from common.serializers import EnvelopeSerializer

from .permissions import CanManageRoles
from .role_services import role_data, update_roles


class RoleUpdate(StrictInput):
    expected_version = serializers.IntegerField(min_value=0)
    role_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), allow_empty=True, max_length=30
    )
    reason = serializers.CharField(min_length=1, max_length=200, trim_whitespace=True)


class RoleOption(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()


class RoleUserData(serializers.Serializer):
    id = serializers.CharField()
    username = serializers.CharField()
    roles = RoleOption(many=True)
    expected_version = serializers.IntegerField()


class RoleUserResponse(EnvelopeSerializer):
    data = RoleUserData()


class RoleUsersResponse(EnvelopeSerializer):
    data = RoleUserData(many=True)


class RoleOptionsResponse(EnvelopeSerializer):
    data = serializers.ListField(child=serializers.DictField())


class Users(APIView):
    permission_classes = [CanManageRoles]

    @extend_schema(responses=RoleUsersResponse)
    def get(self, request):
        users = get_user_model().objects.prefetch_related("groups").order_by("id")
        return success([role_data(user) for user in users])


class Options(APIView):
    permission_classes = [CanManageRoles]

    @extend_schema(responses=RoleOptionsResponse)
    def get(self, request):
        return success(
            [
                {
                    "id": str(group.pk),
                    "name": group.name,
                    "permissions": [
                        f"{permission.content_type.app_label}.{permission.codename}"
                        for permission in group.permissions.order_by("id")
                    ],
                }
                for group in Group.objects.prefetch_related("permissions").order_by(
                    "name"
                )
            ]
        )


class Update(APIView):
    permission_classes = [CanManageRoles]

    @extend_schema(request=RoleUpdate, responses=RoleUserResponse, parameters=[HEADER])
    def post(self, request, pk):
        target = get_object_or_404(get_user_model(), pk=pk)
        return success(
            update_roles(request.user, target, body(RoleUpdate, request), key(request))
        )
