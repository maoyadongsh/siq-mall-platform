from django.apps import AppConfig
from django.db.models.signals import post_migrate


def grant_support(using, **kwargs):
    from django.contrib.auth.models import Group, Permission

    permissions = Permission.objects.using(using).filter(
        content_type__app_label="support", codename__in=["reply", "assign"]
    )
    reply = permissions.get(codename="reply")
    assign = permissions.get(codename="assign")
    agent, _ = Group.objects.using(using).get_or_create(name="support_agent")
    agent.permissions.add(reply)
    supervisor, _ = Group.objects.using(using).get_or_create(name="support_supervisor")
    supervisor.permissions.add(reply, assign)


class SupportConfig(AppConfig):
    name = "support"

    def ready(self):
        post_migrate.connect(
            grant_support, sender=self, dispatch_uid="support.grant_support"
        )
