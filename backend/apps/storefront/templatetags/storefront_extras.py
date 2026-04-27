from decimal import Decimal
from django import template

register = template.Library()


@register.filter
def mul(value, arg):
    try:
        return Decimal(value) * Decimal(arg)
    except Exception:
        return "0.00"
