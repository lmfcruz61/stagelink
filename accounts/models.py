from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    MUSICIAN = 'musician'
    FAN = 'fan'
    MANAGER = 'manager'
    ROLE_CHOICES = (
        (MUSICIAN, 'Músico'),
        (FAN, 'Público'),
        (MANAGER, 'Manager / equipa'),
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
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='artist_profile', blank=True, null=True)
    organization = models.ForeignKey(Organization, on_delete=models.SET_NULL, related_name='artists', blank=True, null=True)
    name = models.CharField(max_length=120)
    headline = models.CharField(max_length=180, blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='artists/', blank=True, null=True)
    hero_image = models.ImageField(upload_to='artists/heroes/', blank=True, null=True)
    youtube_link = models.URLField(blank=True)
    instagram_link = models.URLField(blank=True)
    spotify_link = models.URLField(blank=True)
    website_link = models.URLField(blank=True)
    location = models.CharField(max_length=120, blank=True)

    def __str__(self):
        return self.name


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


class SiteAppearance(models.Model):
    name = models.CharField(max_length=80, default='StageLink')
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
