from django.contrib import admin

from .models import Artist, ArtistPhoto, Fan, Organization, OrganizationMember, Profile, SiteAppearance

admin.site.register(Profile)
admin.site.register(Artist)
admin.site.register(ArtistPhoto)
admin.site.register(Fan)
admin.site.register(Organization)
admin.site.register(OrganizationMember)


@admin.register(SiteAppearance)
class SiteAppearanceAdmin(admin.ModelAdmin):
    fields = ('name', 'logo', 'background_image', 'background_overlay')
    list_display = ('name', 'logo', 'background_image', 'background_overlay', 'updated_at')

    def has_add_permission(self, request):
        return not SiteAppearance.objects.exists()
