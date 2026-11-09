import logging
import time
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone
from promotions.models import Coupon
from orders.models import Order, Event
from orders.services import expire_one, deliver_one

logger = logging.getLogger("mall")


class Command(BaseCommand):
    help = "关闭超时订单并投递待处理事件；--watch 每30秒重复扫描"

    def add_arguments(self, parser):
        parser.add_argument("--watch", action="store_true")

    def handle(self, *args, **options):
        while True:
            close_old_connections()
            Coupon.objects.filter(status="unused", end_at__lte=timezone.now()).update(
                status="expired"
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
            ):
                count = 0
                for pk in rows.values_list("pk", flat=True).iterator(chunk_size=100):
                    try:
                        count += handler(pk)
                    except Exception:
                        failures += 1
                        logger.exception(
                            "订单任务 %s 对象 %s 处理失败", handler.__name__, pk
                        )
                self.stdout.write(f"{handler.__name__}={count}")
            if not options["watch"]:
                if failures:
                    raise CommandError(f"{failures} 项失败，已保留供下次重试")
                return
            time.sleep(30)
