import os
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Category, Product, Sku


class Command(BaseCommand):
    help = "仅在显式允许的演示库生成商品规模数据"

    def add_arguments(self, parser):
        parser.add_argument("--products", type=int, default=1000)
        parser.add_argument("--skus", type=int, default=1)
        parser.add_argument("--prefix", default="scale")

    def handle(self, *args, **options):
        if os.environ.get("MALL_ALLOW_SCALE_SEED") != "1":
            raise CommandError("仅在临时演示库设置 MALL_ALLOW_SCALE_SEED=1 后运行")
        total = options["products"]
        sku_count = options["skus"]
        prefix = options["prefix"]
        if total < 1 or total > 100000 or sku_count < 1 or sku_count > 3:
            raise CommandError("商品数1–100000，每商品SKU数1–3")
        if Product.objects.filter(title__startswith=prefix + "-").exists():
            raise CommandError("该前缀已有规模数据，请使用新前缀，避免重复写入")
        with transaction.atomic():
            root = Category.objects.create(name=prefix + "-root", sort_order=10000)
            children = [
                Category.objects.create(
                    name=f"{prefix}-category-{index}", parent=root, sort_order=index
                )
                for index in range(10)
            ]
            products = []
            for index in range(total):
                products.append(
                    Product(
                        category=children[index % 10],
                        title=f"{prefix}-{index + 1:06d}",
                        description="隔离规模测试数据",
                        status="on_sale",
                        min_price=Decimal("10.00") + Decimal(index % 10000) / 100,
                    )
                )
                if len(products) == 1000:
                    self.insert(products, sku_count)
                    products.clear()
            if products:
                self.insert(products, sku_count)
        self.stdout.write(
            self.style.SUCCESS(
                f"created_products={total}, skus_per_product={sku_count}"
            )
        )

    @staticmethod
    def insert(products, sku_count):
        created = Product.objects.bulk_create(products)
        skus = []
        for product in created:
            for index in range(sku_count):
                skus.append(
                    Sku(
                        product=product,
                        label=f"规格{index + 1}",
                        price=Decimal("10.00") + Decimal(product.pk % 10000) / 100,
                        available_stock=10,
                    )
                )
        Sku.objects.bulk_create(skus, batch_size=2000)
