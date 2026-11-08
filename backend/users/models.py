from django.conf import settings
from django.db import models


class Address(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses"
    )
    recipient = models.CharField("收件人", max_length=50)
    phone = models.CharField("联系电话", max_length=20)
    province = models.CharField("省份", max_length=50)
    city = models.CharField("城市", max_length=50)
    district = models.CharField("区县", max_length=50)
    region_code = models.CharField("地区码", max_length=12)
    detail = models.CharField("详细地址", max_length=200)
    is_default = models.BooleanField("默认地址", default=False)
    version = models.PositiveIntegerField("版本", default=1)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        db_table = "users_address"
        indexes = [models.Index(fields=["user", "is_default"])]
