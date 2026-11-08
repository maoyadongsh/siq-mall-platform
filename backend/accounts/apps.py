from django.apps import AppConfig
from django.db.models.signals import post_migrate


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        from . import openapi  # noqa: F401

        post_migrate.connect(
            ensure_roles, sender=self, dispatch_uid="accounts.ensure_roles"
        )


def ensure_roles(**kwargs):
    from django.contrib.auth.models import Group, Permission

    permission = Permission.objects.get(codename="manage_roles")
    access_admin, _ = Group.objects.get_or_create(name="access_admin")
    access_admin.permissions.add(permission)
    for name in (
        "buyer",
        "support_agent",
        "catalog_operator",
        "order_operator",
        "content_operator",
    ):
        Group.objects.get_or_create(name=name)
