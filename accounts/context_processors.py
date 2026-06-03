from .models import SiteAppearance


def site_appearance(request):
    return {
        'site_appearance': SiteAppearance.objects.first(),
    }
