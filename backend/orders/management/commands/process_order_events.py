import logging
import time

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone

from content.models import ContentEvent
from notifications.models import NotificationConsumption
from notifications.services import (
    CONSUMER,
    deliver_content_event,
    deliver_order_event,
    deliver_review_action,
)
from orders.models import Event, Order
from orders.services import deliver_one, expire_one
from promotions.models import Coupon
from reviews.models import ReviewAction

logger = logging.getLogger("mall")


class Command(BaseCommand):
    help = "关闭超时订单，投递履约动态和站内通知；--watch 每5秒重复扫描"

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            Coupon.objects.filter(status="unused", end_at__lte=timezone.now()).update(
                status="expired"
            )
            consumed = NotificationConsumption.objects.filter(consumer=CONSUMER).values(
                "event_id"
            )
            failures = 0
            for rows, handler in (
                (
                    Order.objects.filter(
                        status="pending", expires_at__lte=timezone.now()
                    ).order_by("expires_at", "pk"),
                    expire_one,
                ),
                (
                    Event.objects.filter(delivered_at__isnull=True).order_by("pk"),
                    deliver_one,
                ),
                (
                    Event.objects.exclude(event_id__in=consumed).order_by("pk"),
                    deliver_order_event,
                ),
                (
                    ReviewAction.objects.filter(
                        operation="moderate", event_id__isnull=False
                    )
                    .exclude(event_id__in=consumed)
                    .order_by("pk"),
                    deliver_review_action,
                ),
                (
                    ContentEvent.objects.exclude(event_id__in=consumed).order_by("pk"),
                    deliver_content_event,
                ),
            ):
                count = 0
                for pk in rows.values_list("pk", flat=True).iterator(chunk_size=100):
                    try:
                        count += handler(pk)
                    except Exception:
                        failures += 1
                        logger.exception(
                            "订单/通知任务 %s 对象 %s 处理失败", handler.__name__, pk
                        )
                self.stdout.write(f"{handler.__name__}={count}")
            if not options["watch"]:
                if failures:
                    raise CommandError(f"{failures} 项失败，已保留供下次重试")
                return
            time.sleep(5)
