from django.apps import AppConfig
from django.db.models.signals import post_migrate


def grant_catalog_permission(using, **kwargs):
    from django.contrib.auth.models import Group, Permission

    perm = Permission.objects.using(using).get(
        content_type__app_label="catalog", codename="manage_catalog"
    )
    group, _ = Group.objects.using(using).get_or_create(name="catalog_operator")
    group.permissions.add(perm)


class CatalogConfig(AppConfig):
    name = "catalog"

    def ready(self):
        post_migrate.connect(
            grant_catalog_permission, sender=self, dispatch_uid="catalog.grant_operator"
        )
