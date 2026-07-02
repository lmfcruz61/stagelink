import csv

from django.contrib import admin
from django.http import HttpResponse

from .models import (
    ActivityLog,
    Artist,
    ArtistPhoto,
    ContactMessage,
    Fan,
    NewsletterSubscriber,
    Profile,
    SiteAppearance,
)

admin.site.register(Profile)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        'created_at',
        'action',
        'username',
        'method',
        'path',
        'status_code',
        'duration_ms',
        'ip_address',
    )
    list_filter = ('action', 'method', 'status_code', 'created_at')
    search_fields = ('username', 'path', 'query_string', 'ip_address', 'user_agent', 'referrer', 'view_name')
    readonly_fields = (
        'user',
        'username',
        'action',
        'method',
        'path',
        'query_string',
        'status_code',
        'duration_ms',
        'ip_address',
        'user_agent',
        'referrer',
        'view_name',
        'created_at',
    )
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 50

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Artist)
class ArtistAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'user',
        'is_institutional',
        'monetization_mode',
        'commission_rate',
        'cloudflare_live_input_uid',
        'stripe_account_id',
        'stripe_charges_enabled',
        'stripe_payouts_enabled',
    )
    list_filter = ('is_institutional', 'monetization_mode', 'stripe_charges_enabled', 'stripe_payouts_enabled')
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


@admin.action(description='Marcar como em analise')
def mark_contact_in_review(modeladmin, request, queryset):
    queryset.update(status=ContactMessage.IN_REVIEW)


@admin.action(description='Marcar como resolvido')
def mark_contact_resolved(modeladmin, request, queryset):
    queryset.update(status=ContactMessage.RESOLVED)


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'name', 'email', 'contact_type', 'status', 'created_at')
    list_filter = ('contact_type', 'status', 'created_at')
    search_fields = ('name', 'email', 'subject', 'message')
    readonly_fields = ('name', 'email', 'contact_type', 'subject', 'message', 'ip_address', 'user_agent', 'created_at', 'updated_at')
    ordering = ('-created_at',)
    actions = (mark_contact_in_review, mark_contact_resolved)


@admin.register(SiteAppearance)
class SiteAppearanceAdmin(admin.ModelAdmin):
    fields = ('name', 'logo', 'background_image', 'background_overlay')
    list_display = ('name', 'logo', 'background_image', 'background_overlay', 'updated_at')

    def has_add_permission(self, request):
        return not SiteAppearance.objects.exists()
