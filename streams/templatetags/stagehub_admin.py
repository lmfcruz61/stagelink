from django import template

from streams.models import PhotoGallery


register = template.Library()


@register.simple_tag
def stagehub_pending_approvals():
    return {
        'photo_galleries': PhotoGallery.objects.filter(
            moderation_status=PhotoGallery.PENDING,
        ).count(),
    }
