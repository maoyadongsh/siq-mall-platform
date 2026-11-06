"""通用基础模型（架构文档 §7.1）：所有业务表必须继承 BaseModel。"""

from django.db import models


class BaseModel(models.Model):
    created_at = models.DateTimeField("创建时间", auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)
    is_deleted = models.BooleanField("是否删除", default=False, db_index=True)

    class Meta:
        abstract = True
