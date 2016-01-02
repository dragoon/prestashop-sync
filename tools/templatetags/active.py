from django import template
from django.core.urlresolvers import reverse

register = template.Library()

@register.simple_tag(takes_context = True)
def active(context, view_name):
    """Tag returning 'active' string for urls in site menu"""
    if view_name=='main':
        if context['request'].path!='/':
            return ''
    if context['request'].path.startswith(reverse(view_name)):
        return 'active'
    return ''
