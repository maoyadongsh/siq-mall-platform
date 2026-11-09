from django.db import models


class ContentAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [("publish", "发布CMS内容与通知模板")]
