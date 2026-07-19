import os

from django import template

register = template.Library()

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}


@register.filter
def basename(value):
    if not value:
        return value
    return os.path.basename(str(value))


@register.filter
def is_image(value):
    if not value:
        return False
    ext = os.path.splitext(str(value))[1].lower()
    return ext in IMAGE_EXTENSIONS