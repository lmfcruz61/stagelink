from django import template

from accounts.models import SiteAppearance

register = template.Library()


@register.simple_tag
def get_site_appearance():
    return SiteAppearance.objects.first()
