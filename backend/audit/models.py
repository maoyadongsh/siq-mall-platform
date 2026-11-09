from django.db import models


class AuditAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [("view", "查看运营审计")]
