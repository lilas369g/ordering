from django.db import models
from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    name = models.CharField(max_length=120)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='children')

    def __str__(self) -> str:
        return self.name


class Brand(TimeStampedModel):
    name = models.CharField(max_length=120, unique=True)

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name='products')
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class OptionType(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self) -> str:
        return self.name


class OptionValue(TimeStampedModel):
    option_type = models.ForeignKey(OptionType, on_delete=models.CASCADE, related_name='values')
    value = models.CharField(max_length=100)

    class Meta:
        unique_together = ('option_type', 'value')

    def __str__(self) -> str:
        return f'{self.option_type.name}: {self.value}'


class ProductOption(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_options')
    option_type = models.ForeignKey(OptionType, on_delete=models.PROTECT, related_name='product_options')
    is_required = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('product', 'option_type')


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=64, unique=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.sku


class VariantOptionValue(TimeStampedModel):
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='variant_values')
    option_value = models.ForeignKey(OptionValue, on_delete=models.PROTECT, related_name='variant_values')

    class Meta:
        unique_together = ('variant', 'option_value')
