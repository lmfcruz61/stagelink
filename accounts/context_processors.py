from django.conf import settings

from .models import SiteAppearance


def site_appearance(request):
    appearance = SiteAppearance.objects.first()
    version = int(appearance.updated_at.timestamp()) if appearance and appearance.updated_at else ''
    return {
        'facebook_pixel_id': settings.FACEBOOK_PIXEL_ID,
        'site_appearance': appearance,
        'site_appearance_version': version,
    }
