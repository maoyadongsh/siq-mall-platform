from django.apps import AppConfig
from django.db.models.signals import post_migrate


DEFAULT_TEMPLATES = {
    "order.created": (
        "订单已创建",
        "订单 {order_no} 已创建，请在付款期限内完成演示支付。",
    ),
    "order.paid": ("演示支付成功", "订单 {order_no} 已完成模拟支付，等待运营发货。"),
    "order.canceled": (
        "订单已取消",
        "订单 {order_no} 已取消，相关库存与优惠券已按规则处理。",
    ),
    "order.shipped": ("订单已发货", "订单 {order_no} 已发货，请查看履约动态。"),
    "order.completed": ("订单已完成", "订单 {order_no} 已确认收货，感谢你的选购。"),
    "review.moderated": (
        "评价审核结果已更新",
        "你的评价审核结果为{review_status}，可查看详细说明。",
    ),
    "support.message_created": ("客服已回复", "你的客服会话有新回复，请打开会话查看。"),
    "cms.announcement_published": ("商城公告", "{announcement_title}"),
}


def seed_templates(using, **kwargs):
    from .models import NotificationTemplate, NotificationTemplatePointer

    for event_type, (title, body) in DEFAULT_TEMPLATES.items():
        template, _ = NotificationTemplate.objects.using(using).get_or_create(
            event_type=event_type,
            channel="inbox",
            version=1,
            defaults={
                "title": title,
                "body": body,
                "variables": sorted(set(TEMPLATE_VARIABLES[event_type])),
                "enabled": True,
            },
        )
        NotificationTemplatePointer.objects.using(using).get_or_create(
            event_type=event_type,
            channel="inbox",
            defaults={"template": template},
        )


TEMPLATE_VARIABLES = {
    "order.created": {"order_no"},
    "order.paid": {"order_no"},
    "order.canceled": {"order_no"},
    "order.shipped": {"order_no"},
    "order.completed": {"order_no"},
    "review.moderated": {"review_status"},
    "support.message_created": set(),
    "cms.announcement_published": {"announcement_title"},
}


class NotificationsConfig(AppConfig):
    name = "notifications"

    def ready(self):
        post_migrate.connect(
            seed_templates, sender=self, dispatch_uid="notifications.seed_templates"
        )
