from django import template

register = template.Library()


@register.filter
def choice_letter(value):
    """Convert a 0-based integer to a capital letter: 0→A, 1→B, 2→C …"""
    try:
        return chr(65 + int(value))
    except (TypeError, ValueError):
        return value
