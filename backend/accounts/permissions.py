from rest_framework.permissions import BasePermission


class CanManageRoles(BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.has_perm("accounts.manage_roles")
        )
