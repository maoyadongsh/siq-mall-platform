from django.apps import AppConfig
from django.db.models.signals import post_migrate


def grant(using, **kwargs):
    from django.contrib.auth.models import Group, Permission

    group, _ = Group.objects.using(using).get_or_create(name="promotion_operator")
    group.permissions.add(
        Permission.objects.using(using).get(
            content_type__app_label="promotions", codename="manage"
        )
    )


class PromotionsConfig(AppConfig):
    name = "promotions"

    def ready(self):
        post_migrate.connect(grant, sender=self, dispatch_uid="promotions.grant")
