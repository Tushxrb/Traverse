from django import template

register = template.Library()

@register.filter
def lookup(dictionary, key):
    """
    Template filter to look up a key in a dictionary
    Usage: {{ dict|lookup:key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, None)
    return None