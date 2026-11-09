from django.apps import AppConfig
from django.db.models.signals import post_migrate


def grant_fulfillment(using, **kwargs):
    from django.contrib.auth.models import Group, Permission

    group, _ = Group.objects.using(using).get_or_create(name="order_operator")
    group.permissions.add(
        Permission.objects.using(using).get(
            content_type__app_label="orders", codename="fulfill"
        )
    )


class OrdersConfig(AppConfig):
    name = "orders"

    def ready(self):
        post_migrate.connect(
            grant_fulfillment, sender=self, dispatch_uid="orders.grant_fulfill"
        )
