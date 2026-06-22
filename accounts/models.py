from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


class Profile(models.Model):
    MUSICIAN = 'musician'
    FAN = 'fan'
    MANAGER = 'manager'
    ROLE_CHOICES = (
        (MUSICIAN, 'Artista'),
        (FAN, 'Público'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'


class Organization(models.Model):
    name = models.CharField(max_length=140)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    logo = models.ImageField(upload_to='organizations/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_organizations')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class OrganizationMember(models.Model):
    OWNER = 'owner'
    MANAGER = 'manager'
    EDITOR = 'editor'
    VIEWER = 'viewer'
    ROLE_CHOICES = (
        (OWNER, 'Dono'),
        (MANAGER, 'Manager'),
        (EDITOR, 'Editor'),
        (VIEWER, 'Leitor'),
    )
    EDIT_ROLES = (OWNER, MANAGER, EDITOR)

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='organization_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=MANAGER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('organization', 'user')
        ordering = ['organization__name', 'user__username']

    def __str__(self):
        return f'{self.user.username} - {self.organization.name}'

    @property
    def can_edit(self):
        return self.role in self.EDIT_ROLES


class Artist(models.Model):
    SUBSCRIPTION_ONLY = 'subscription_only'
    SUBSCRIPTION_AND_PAID_EXCLUSIVE = 'subscription_paid_exclusive'
    PAID_CONTENT_ONLY = 'paid_content_only'
    MONETIZATION_MODE_CHOICES = (
        (SUBSCRIPTION_ONLY, 'Somente subscricao'),
        (SUBSCRIPTION_AND_PAID_EXCLUSIVE, 'Subscricao e material pago exclusivo'),
        (PAID_CONTENT_ONLY, 'Somente material pago'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='artist_profile', blank=True, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, related_name='artists', blank=True, null=True)
    name = models.CharField(max_length=120)
    headline = models.CharField(max_length=180, blank=True)
    bio = models.TextField(blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    photo = models.ImageField(upload_to='artists/', blank=True, null=True)
    hero_image = models.ImageField(upload_to='artists/heroes/', blank=True, null=True)
    youtube_link = models.URLField(blank=True)
    instagram_link = models.URLField(blank=True)
    spotify_link = models.URLField(blank=True)
    website_link = models.URLField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    cloudflare_live_input_uid = models.CharField(
        max_length=120,
        blank=True,
        help_text='Live Input UID principal do artista no Cloudflare Stream.',
    )
    cloudflare_rtmps_url = models.URLField(blank=True)
    cloudflare_stream_key = models.CharField(max_length=240, blank=True)
    stripe_account_id = models.CharField(
        max_length=120,
        blank=True,
        help_text='ID da conta Stripe Connect do artista.',
    )
    stripe_details_submitted = models.BooleanField(default=False)
    stripe_charges_enabled = models.BooleanField(default=False)
    stripe_payouts_enabled = models.BooleanField(default=False)
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('20.00'),
        validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
        help_text='Percentagem da comissao StageHub aplicada as vendas deste artista.',
    )
    monetization_mode = models.CharField(
        max_length=40,
        choices=MONETIZATION_MODE_CHOICES,
        default=PAID_CONTENT_ONLY,
        help_text='Define se o artista usa subscricao, material pago exclusivo para subscritores ou material pago aberto a todos.',
    )

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if self.pk and self.monetization_mode == self.PAID_CONTENT_ONLY:
            previous_mode = type(self).objects.filter(pk=self.pk).values_list('monetization_mode', flat=True).first()
            if previous_mode == self.PAID_CONTENT_ONLY:
                return
            from payments.models import Subscription

            has_active_subscriptions = Subscription.objects.filter(
                artist=self,
                status=Subscription.ACTIVE,
                current_period_end__gte=timezone.now(),
            ).exists()
            if has_active_subscriptions:
                raise ValidationError({
                    'monetization_mode': (
                        'Este artista tem subscricoes ativas. Cancela ou deixa terminar as subscricoes '
                        'antes de mudar para somente material pago.'
                    ),
                })

    @property
    def stripe_connect_ready(self):
        return bool(self.stripe_account_id and self.stripe_charges_enabled and self.stripe_payouts_enabled)

    @property
    def allows_subscriptions(self):
        return self.monetization_mode in {
            self.SUBSCRIPTION_ONLY,
            self.SUBSCRIPTION_AND_PAID_EXCLUSIVE,
        }

    @property
    def allows_paid_content(self):
        return self.monetization_mode in {
            self.SUBSCRIPTION_AND_PAID_EXCLUSIVE,
            self.PAID_CONTENT_ONLY,
        }

    @property
    def paid_content_requires_subscription(self):
        return self.monetization_mode == self.SUBSCRIPTION_AND_PAID_EXCLUSIVE

    @property
    def paid_content_is_open_to_all(self):
        return self.monetization_mode == self.PAID_CONTENT_ONLY

    @property
    def subscription_includes_content(self):
        return self.monetization_mode == self.SUBSCRIPTION_ONLY


class ArtistPhoto(models.Model):
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name='gallery_photos')
    image = models.ImageField(upload_to='artists/gallery/')
    caption = models.CharField(max_length=140, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Foto de {self.artist.name}'


class Fan(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='fan_profile')
    display_name = models.CharField(max_length=120)
    photo = models.ImageField(upload_to='fans/', blank=True, null=True)
    social_avatar_url = models.URLField(blank=True)
    favorite_artists = models.ManyToManyField(Artist, blank=True, related_name='fans_who_favorited')

    def __str__(self):
        return self.display_name


class NewsletterSubscriber(models.Model):
    FAN = 'fan'
    ARTIST = 'artist'
    BOTH = 'both'
    INTEREST_CHOICES = (
        (FAN, 'Fã'),
        (ARTIST, 'Artista'),
        (BOTH, 'Ambos'),
    )

    name = models.CharField(max_length=120, blank=True)
    email = models.EmailField(unique=True)
    interest_type = models.CharField(max_length=20, choices=INTEREST_CHOICES, default=FAN)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-subscribed_at']
        verbose_name = 'Subscritor da newsletter'
        verbose_name_plural = 'Subscritores da newsletter'

    def __str__(self):
        return self.email


class ContactMessage(models.Model):
    GENERAL = 'general'
    FINANCE = 'finance'
    TECHNICAL = 'technical'
    CONTACT_TYPE_CHOICES = (
        (GENERAL, 'Geral'),
        (FINANCE, 'Financeiro'),
        (TECHNICAL, 'Tecnico'),
    )

    NEW = 'new'
    IN_REVIEW = 'in_review'
    RESOLVED = 'resolved'
    STATUS_CHOICES = (
        (NEW, 'Novo'),
        (IN_REVIEW, 'Em analise'),
        (RESOLVED, 'Resolvido'),
    )

    name = models.CharField(max_length=120)
    email = models.EmailField()
    contact_type = models.CharField(max_length=20, choices=CONTACT_TYPE_CHOICES)
    subject = models.CharField(max_length=160)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=NEW)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Mensagem de contacto'
        verbose_name_plural = 'Mensagens de contacto'

    def __str__(self):
        return f'{self.get_contact_type_display()} - {self.subject}'


class SiteAppearance(models.Model):
    name = models.CharField(max_length=80, default='StageHub')
    logo = models.ImageField(
        upload_to='site/',
        blank=True,
        null=True,
        help_text='Recomendado: PNG transparente horizontal, cerca de 600x180 px.',
    )
    background_image = models.ImageField(upload_to='site/', blank=True, null=True)
    background_overlay = models.PositiveSmallIntegerField(default=75)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Aparencia do site'
        verbose_name_plural = 'Aparencia do site'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Mantem apenas uma configuracao global no admin.
        self.pk = 1
        super().save(*args, **kwargs)
