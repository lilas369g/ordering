from django.db import models
from apps.common.models import TimeStampedModel


class InventoryRecord(TimeStampedModel):
    variant = models.OneToOneField('catalog.ProductVariant', on_delete=models.CASCADE, related_name='inventory_record')
    quantity_available = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=0)

    def __str__(self) -> str:
        return f'{self.variant.sku}: {self.quantity_available}'


class StockMovementType(models.TextChoices):
    RESERVE = 'reserve', 'Reserve'
    RELEASE = 'release', 'Release'
    SALE = 'sale', 'Sale'
    ADJUSTMENT = 'adjustment', 'Adjustment'


class StockMovement(TimeStampedModel):
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=30, choices=StockMovementType.choices)
    quantity = models.IntegerField()
    note = models.CharField(max_length=255, blank=True)
