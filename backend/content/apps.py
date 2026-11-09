from django.apps import AppConfig
from django.db.models.signals import post_migrate


def grant_content(using, **kwargs):
    from django.contrib.auth.models import Group, Permission

    group, _ = Group.objects.using(using).get_or_create(name="content_operator")
    group.permissions.add(
        Permission.objects.using(using).get(
            content_type__app_label="content", codename="publish"
        )
    )


class ContentConfig(AppConfig):
    name = "content"

    def ready(self):
        post_migrate.connect(
            grant_content, sender=self, dispatch_uid="content.grant_content"
        )
