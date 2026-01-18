# analytics_filters.py
from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def multiply(value, arg):
    try:
        return Decimal(str(value)) * Decimal(str(arg))
    except:
        return value

@register.filter
def divide(value, arg):
    try:
        if Decimal(str(arg)) != 0:
            return Decimal(str(value)) / Decimal(str(arg))
        return 0
    except:
        return 0

@register.filter
def subtract(value, arg):
    try:
        return Decimal(str(value)) - Decimal(str(arg))
    except:
        return value

@register.filter
def percentage(value, total):
    try:
        if total > 0:
            return (value / total * 100)
        return 0
    except:
        return 0