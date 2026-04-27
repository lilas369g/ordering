from django.core.management.base import BaseCommand

from apps.catalog.models import Brand, Category, OptionType, OptionValue, Product, ProductOption, ProductVariant, VariantOptionValue
from apps.inventory.models import InventoryRecord


class Command(BaseCommand):
    help = "Seed a demo storefront with products, variants, and inventory"

    def handle(self, *args, **options):
        grocery, _ = Category.objects.get_or_create(name="مواد غذائية", parent=None)
        snacks, _ = Category.objects.get_or_create(name="سناك", parent=None)
        rice_brand, _ = Brand.objects.get_or_create(name="Al Baraka")
        chips_brand, _ = Brand.objects.get_or_create(name="Crunchy")

        size_type, _ = OptionType.objects.get_or_create(name="Size")
        small, _ = OptionValue.objects.get_or_create(option_type=size_type, value="Small")
        large, _ = OptionValue.objects.get_or_create(option_type=size_type, value="Large")

        rice, _ = Product.objects.get_or_create(
            name="رز بسمتي",
            defaults={
                "description": "رز بسمتي للتجربة على واجهة المتجر.",
                "category": grocery,
                "brand": rice_brand,
                "is_active": True,
            },
        )
        ProductOption.objects.get_or_create(product=rice, option_type=size_type, defaults={"is_required": True, "is_active": True})
        rice_small, _ = ProductVariant.objects.get_or_create(product=rice, sku="RICE-S", defaults={"price": "18000.00", "is_active": True})
        rice_large, _ = ProductVariant.objects.get_or_create(product=rice, sku="RICE-L", defaults={"price": "32000.00", "is_active": True})
        VariantOptionValue.objects.get_or_create(variant=rice_small, option_value=small)
        VariantOptionValue.objects.get_or_create(variant=rice_large, option_value=large)
        InventoryRecord.objects.get_or_create(variant=rice_small, defaults={"quantity_available": 20, "low_stock_threshold": 5})
        InventoryRecord.objects.get_or_create(variant=rice_large, defaults={"quantity_available": 8, "low_stock_threshold": 3})

        chips, _ = Product.objects.get_or_create(
            name="شيبس بطاطا",
            defaults={
                "description": "شيبس للتجربة على واجهة المتجر.",
                "category": snacks,
                "brand": chips_brand,
                "is_active": True,
            },
        )
        ProductOption.objects.get_or_create(product=chips, option_type=size_type, defaults={"is_required": True, "is_active": True})
        chips_small, _ = ProductVariant.objects.get_or_create(product=chips, sku="CHIPS-S", defaults={"price": "5000.00", "is_active": True})
        chips_large, _ = ProductVariant.objects.get_or_create(product=chips, sku="CHIPS-L", defaults={"price": "8500.00", "is_active": True})
        VariantOptionValue.objects.get_or_create(variant=chips_small, option_value=small)
        VariantOptionValue.objects.get_or_create(variant=chips_large, option_value=large)
        InventoryRecord.objects.get_or_create(variant=chips_small, defaults={"quantity_available": 35, "low_stock_threshold": 10})
        InventoryRecord.objects.get_or_create(variant=chips_large, defaults={"quantity_available": 15, "low_stock_threshold": 5})

        self.stdout.write(self.style.SUCCESS("Demo products created or updated successfully."))
