from django.db import models
from apps.common.models import TimeStampedModel


class InventoryRecord(TimeStampedModel):
    variant = models.OneToOneField('catalog.ProductVariant', on_delete=models.CASCADE, related_name='inventory_record')
    quantity_available = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=0)
    version = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity_available__gte=0),
                name='prevent_negative_stock' # منع المخزون السالب على مستوى الداتابيز
            )
        ]

    def __str__(self) -> str:
        return f'{self.variant.sku}: {self.quantity_available}'


class StockMovementType(models.TextChoices):
    RESERVE = 'reserve', 'Reserve'
    RELEASE = 'release', 'Release'
    SALE = 'sale', 'Sale'
    ADJUSTMENT = 'adjustment', 'Adjustment'
    DAILY_PROCESSING = 'daily_processing', 'Daily Sales Processing'


class StockMovement(TimeStampedModel):
    variant = models.ForeignKey('catalog.ProductVariant', on_delete=models.CASCADE, related_name='stock_movements')
    movement_type = models.CharField(max_length=30, choices=StockMovementType.choices)
    quantity = models.IntegerField()
    note = models.CharField(max_length=255, blank=True)


class ProcessingStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    FAILED = 'failed', 'Failed'


class DailySalesProcessing(TimeStampedModel):
    """
    Tracks the status of daily sales inventory processing batches.
    Ensures idempotency: if a date is already processed, we skip it.
    Enables checkpointing: track which chunks succeeded/failed.
    """
    processing_date = models.DateField(unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=ProcessingStatus.choices, default=ProcessingStatus.PENDING)
    total_chunks = models.IntegerField(default=0)
    processed_chunks = models.IntegerField(default=0)
    failed_chunks = models.IntegerField(default=0)
    last_processed_order_id = models.IntegerField(default=0)
    error_log = models.TextField(blank=True, help_text="JSON-formatted list of failed chunks")

    class Meta:
        db_table = 'daily_sales_processing'
        ordering = ['-processing_date']

    def __str__(self):
        return f"DailySalesProcessing({self.processing_date}, {self.status})"
