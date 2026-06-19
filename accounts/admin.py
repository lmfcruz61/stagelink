import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import (
    Artist,
    ArtistPhoto,
    Fan,
    NewsletterSubscriber,
    Profile,
    SiteAppearance,
)

admin.site.register(Profile)
@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'cloudflare_live_input_uid', 'stripe_account_id', 'stripe_charges_enabled', 'stripe_payouts_enabled')
    search_fields = ('name', 'user__username', 'cloudflare_live_input_uid', 'stripe_account_id')
    readonly_fields = ('cloudflare_rtmps_url', 'cloudflare_stream_key')


admin.site.register(ArtistPhoto)
admin.site.register(Fan)


@admin.action(description='Exportar selecionados para CSV')
def export_newsletter_csv(modeladmin, request, queryset):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="newsletter-subscritores.csv"'
    writer = csv.writer(response)
    writer.writerow(['Nome', 'Email', 'Tipo de interesse', 'Ativo', 'Subscrito em'])
    for subscriber in queryset:
        writer.writerow([
            subscriber.name,
            subscriber.email,
            subscriber.get_interest_type_display(),
            'sim' if subscriber.is_active else 'nao',
            subscriber.subscribed_at.isoformat(),
        ])
    return response


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'name', 'interest_type', 'is_active', 'subscribed_at')
    list_filter = ('interest_type', 'is_active')
    search_fields = ('email', 'name')
    ordering = ('-subscribed_at',)
    actions = (export_newsletter_csv,)


@admin.register(SiteAppearance)
class SiteAppearanceAdmin(admin.ModelAdmin):
    fields = ('name', 'logo', 'background_image', 'background_overlay')
    list_display = ('name', 'logo', 'background_image', 'background_overlay', 'updated_at')

    def has_add_permission(self, request):
        return not SiteAppearance.objects.exists()
