from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.forms import (
    ArtistGalleryUploadForm,
    ArtistProfileForm,
    ManagedArtistForm,
    OrganizationForm,
    OrganizationMemberForm,
)
from accounts.models import Artist, ArtistPhoto, Organization, OrganizationMember
from payments.models import Subscription

from .forms import LiveStreamForm
from .models import LiveStream


def home(request):
    artists = Artist.objects.all().order_by('name')
    live_streams = LiveStream.objects.filter(is_active=True).select_related('artist')[:8]
    favorite_artist_ids = set()
    favorite_artists = Artist.objects.none()

    if request.user.is_authenticated and hasattr(request.user, 'fan_profile'):
        favorite_artists = request.user.fan_profile.favorite_artists.all().order_by('name')
        favorite_artist_ids = set(favorite_artists.values_list('id', flat=True))

    return render(request, 'streams/home.html', {
        'artists': artists,
        'favorite_artists': favorite_artists,
        'favorite_artist_ids': favorite_artist_ids,
        'live_streams': live_streams,
    })


def artist_detail(request, artist_id):
    artist = get_object_or_404(Artist.objects.prefetch_related('gallery_photos'), pk=artist_id)
    streams = artist.streams.all()
    now = timezone.now()
    upcoming_streams = streams.filter(scheduled_at__gte=now).order_by('scheduled_at')
    past_streams = streams.filter(scheduled_at__lt=now).order_by('-scheduled_at')
    is_favorite = False
    if request.user.is_authenticated and hasattr(request.user, 'fan_profile'):
        is_favorite = request.user.fan_profile.favorite_artists.filter(pk=artist.pk).exists()

    return render(request, 'streams/artist_detail.html', {
        'artist': artist,
        'gallery_photos': artist.gallery_photos.all(),
        'featured_stream': upcoming_streams.first(),
        'is_favorite': is_favorite,
        'upcoming_streams': upcoming_streams,
        'past_streams': past_streams,
    })


@login_required
def favorite_artist_toggle(request, artist_id):
    if request.method != 'POST':
        return redirect('streams:artist_detail', artist_id=artist_id)

    fan = getattr(request.user, 'fan_profile', None)
    if not fan:
        messages.error(request, 'Apenas fas podem guardar artistas favoritos.')
        return redirect('streams:artist_detail', artist_id=artist_id)

    artist = get_object_or_404(Artist, pk=artist_id)
    if fan.favorite_artists.filter(pk=artist.pk).exists():
        fan.favorite_artists.remove(artist)
        messages.success(request, f'{artist.name} removido dos favoritos.')
    else:
        fan.favorite_artists.add(artist)
        messages.success(request, f'{artist.name} adicionado aos favoritos.')

    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('streams:artist_detail', artist_id=artist_id)


def editable_artists_for(user):
    if user.is_staff or user.is_superuser:
        return Artist.objects.all().select_related('organization')

    organization_ids = OrganizationMember.objects.filter(
        user=user,
        role__in=OrganizationMember.EDIT_ROLES,
    ).values_list('organization_id', flat=True)

    artist_ids = set(Artist.objects.filter(user=user).values_list('id', flat=True))
    artist_ids.update(Artist.objects.filter(organization_id__in=organization_ids).values_list('id', flat=True))
    return Artist.objects.filter(id__in=artist_ids).select_related('organization')


def can_manage_artist(user, artist):
    if user.is_staff or user.is_superuser:
        return True
    if artist.user_id == user.id:
        return True
    if artist.organization_id:
        return OrganizationMember.objects.filter(
            organization=artist.organization,
            user=user,
            role__in=OrganizationMember.EDIT_ROLES,
        ).exists()
    return False


def can_access_dashboard(user):
    if user.is_staff or user.is_superuser:
        return True
    if Artist.objects.filter(user=user).exists():
        return True
    return OrganizationMember.objects.filter(user=user).exists()


@login_required
def stream_room(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if not stream.user_has_access(request.user):
        messages.warning(request, 'Precisas de uma subscricao ativa ou bilhete para entrar nesta sala.')
        return render(request, 'streams/access_required.html', {'stream': stream})
    return render(request, 'streams/room.html', {'stream': stream})


@login_required
def dashboard(request):
    if not can_access_dashboard(request.user):
        messages.info(request, 'A tua conta de fa nao tem dashboard de gestao. Usa a homepage para seguir artistas, entrar em streams e gerir o teu perfil.')
        return redirect('streams:home')

    artists = editable_artists_for(request.user).order_by('name')
    artist_id = request.GET.get('artist')
    artist = get_object_or_404(artists, pk=artist_id) if artist_id else artists.first()
    organizations = Organization.objects.filter(members__user=request.user).prefetch_related('members', 'artists')

    if not artist:
        messages.info(request, 'Cria uma equipa ou um perfil de artista para comecar a gerir streams.')
        return render(request, 'dashboard/index.html', {
            'artist': None,
            'artists': artists,
            'organizations': organizations,
            'streams': [],
            'subscribers': [],
            'tips_total': 0,
        })

    streams = artist.streams.all()
    subscribers = Subscription.objects.filter(artist=artist, status=Subscription.ACTIVE).select_related('fan__user')
    tips_total = artist.tips.aggregate(total=Sum('amount'))['total'] or 0
    return render(request, 'dashboard/index.html', {
        'artist': artist,
        'artists': artists,
        'organizations': organizations,
        'streams': streams,
        'subscribers': subscribers,
        'tips_total': tips_total,
    })


@login_required
def organization_create(request):
    if not request.user.is_staff and getattr(getattr(request.user, 'profile', None), 'role', '') == 'fan':
        messages.error(request, 'Contas de fa nao podem criar equipas. Cria uma conta Manager / equipa para gerir artistas.')
        return redirect('streams:home')

    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES)
        if form.is_valid():
            organization = form.save(commit=False)
            organization.created_by = request.user
            organization.save()
            OrganizationMember.objects.create(
                organization=organization,
                user=request.user,
                role=OrganizationMember.OWNER,
            )
            messages.success(request, 'Equipa criada. Agora podes adicionar artistas e membros.')
            return redirect('streams:dashboard')
    else:
        form = OrganizationForm()
    return render(request, 'dashboard/organization_form.html', {'form': form})


@login_required
def organization_update(request, organization_id):
    membership = get_object_or_404(
        OrganizationMember,
        organization_id=organization_id,
        user=request.user,
        role__in=(OrganizationMember.OWNER, OrganizationMember.MANAGER),
    )
    organization = membership.organization

    if request.method == 'POST':
        form = OrganizationForm(request.POST, request.FILES, instance=organization)
        member_form = OrganizationMemberForm(request.POST)
        action = request.POST.get('action')

        if action == 'save_organization' and form.is_valid():
            form.save()
            messages.success(request, 'Equipa atualizada.')
            return redirect('streams:organization_update', organization_id=organization.id)

        if action == 'add_member' and member_form.is_valid():
            username = member_form.cleaned_data['username']
            member_user = get_object_or_404(User, username=username)
            OrganizationMember.objects.update_or_create(
                organization=organization,
                user=member_user,
                defaults={'role': member_form.cleaned_data['role']},
            )
            messages.success(request, 'Membro adicionado ou atualizado.')
            return redirect('streams:organization_update', organization_id=organization.id)
    else:
        form = OrganizationForm(instance=organization)
        member_form = OrganizationMemberForm()

    return render(request, 'dashboard/organization_form.html', {
        'form': form,
        'member_form': member_form,
        'organization': organization,
        'members': organization.members.select_related('user'),
    })


@login_required
def managed_artist_create(request):
    organizations = Organization.objects.filter(
        members__user=request.user,
        members__role__in=OrganizationMember.EDIT_ROLES,
    ).distinct()
    if request.user.is_staff or request.user.is_superuser:
        organizations = Organization.objects.all()

    if not organizations.exists():
        messages.error(request, 'Cria primeiro uma equipa para adicionar artistas geridos.')
        return redirect('streams:organization_create')

    if request.method == 'POST':
        form = ManagedArtistForm(request.POST, request.FILES)
        organization = get_object_or_404(organizations, pk=request.POST.get('organization'))
        if form.is_valid():
            artist = form.save(commit=False)
            artist.organization = organization
            artist.save()
            messages.success(request, 'Artista adicionado a equipa.')
            return redirect(f"{reverse('streams:dashboard')}?artist={artist.id}")
    else:
        form = ManagedArtistForm()

    return render(request, 'dashboard/managed_artist_form.html', {
        'form': form,
        'organizations': organizations,
    })


@login_required
def artist_profile_edit(request):
    artists = editable_artists_for(request.user).order_by('name')
    artist_id = request.GET.get('artist')
    artist = get_object_or_404(artists, pk=artist_id) if artist_id else artists.first()
    if not artist:
        messages.error(request, 'Nao tens artistas para editar.')
        return redirect('streams:home')

    if request.method == 'POST':
        profile_form = ArtistProfileForm(request.POST, request.FILES, instance=artist)
        gallery_form = ArtistGalleryUploadForm(request.POST, request.FILES)
        action = request.POST.get('action')

        if action == 'save_profile' and profile_form.is_valid():
            profile_form.save()
            messages.success(request, 'Perfil atualizado.')
            return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist.id}")

        if action == 'add_photo' and gallery_form.is_valid():
            caption = gallery_form.cleaned_data.get('caption', '')
            for image in gallery_form.cleaned_data['images']:
                ArtistPhoto.objects.create(artist=artist, image=image, caption=caption)
            messages.success(request, 'Foto adicionada a galeria.')
            return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist.id}")
    else:
        profile_form = ArtistProfileForm(instance=artist)
        gallery_form = ArtistGalleryUploadForm()

    return render(request, 'dashboard/artist_profile_form.html', {
        'artist': artist,
        'artists': artists,
        'profile_form': profile_form,
        'gallery_form': gallery_form,
        'gallery_photos': artist.gallery_photos.all(),
    })


@login_required
def artist_photo_delete(request, photo_id):
    photo = get_object_or_404(ArtistPhoto, pk=photo_id)
    artist_id = photo.artist_id
    if not can_manage_artist(request.user, photo.artist):
        messages.error(request, 'Nao tens permissao para gerir esta galeria.')
        return redirect('streams:dashboard')
    if request.method == 'POST':
        photo.delete()
        messages.success(request, 'Foto removida.')
    return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist_id}")


@login_required
def stream_create(request):
    artists = editable_artists_for(request.user).order_by('name')
    if not artists.exists():
        messages.error(request, 'Precisas de um artista ou equipa para criar streams.')
        return redirect('streams:home')

    if request.method == 'POST':
        form = LiveStreamForm(request.POST, request.FILES)
        artist = get_object_or_404(artists, pk=request.POST.get('artist'))
        if form.is_valid():
            live_stream = form.save(commit=False)
            live_stream.artist = artist
            live_stream.save()
            messages.success(request, 'Stream criado com sucesso.')
            return redirect(f"{reverse('streams:dashboard')}?artist={artist.id}")
    else:
        form = LiveStreamForm()

    return render(request, 'dashboard/stream_form.html', {'form': form, 'artists': artists})


@login_required
def stream_update(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if not can_manage_artist(request.user, stream.artist):
        messages.error(request, 'Nao tens permissao para gerir este stream.')
        return redirect('streams:dashboard')

    if request.method == 'POST':
        form = LiveStreamForm(request.POST, request.FILES, instance=stream)
        if form.is_valid():
            form.save()
            messages.success(request, 'Stream atualizado.')
            return redirect(f"{reverse('streams:dashboard')}?artist={stream.artist_id}")
    else:
        form = LiveStreamForm(instance=stream)
    return render(request, 'dashboard/stream_form.html', {'form': form, 'stream': stream})
