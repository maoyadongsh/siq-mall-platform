from django.apps import AppConfig
from django.db.models.signals import post_migrate


def grant_audit(using, **kwargs):
    from django.contrib.auth.models import Group, Permission

    group, _ = Group.objects.using(using).get_or_create(name="audit_viewer")
    group.permissions.add(
        Permission.objects.using(using).get(
            content_type__app_label="audit", codename="view"
        )
    )


class AuditConfig(AppConfig):
    name = "audit"

    def ready(self):
        post_migrate.connect(grant_audit, sender=self, dispatch_uid="audit.grant_audit")
