from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Case, IntegerField, Prefetch, Q, Sum, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone

from accounts.forms import (
    ArtistGalleryUploadForm,
    ArtistProfileForm,
    ManagedArtistForm,
    NewsletterSubscriberForm,
    OrganizationForm,
    OrganizationMemberForm,
)
from accounts.models import Artist, ArtistPhoto, Organization, OrganizationMember
from payments.models import Subscription
from payments.pricing import ticket_checkout_pricing

from .cloudflare import CloudflareStreamError, create_live_input_for_artist
from .forms import LiveStreamForm
from .models import LiveStream


def absolute_static(request, path):
    return request.build_absolute_uri(static(path))


def absolute_image_url(request, image):
    if image:
        return request.build_absolute_uri(image.url)
    return absolute_static(request, 'img/stagehub-og-placeholder.svg')


def event_public_url(request, stream):
    return request.build_absolute_uri(reverse('streams:event_detail', args=[stream.id]))


def event_og_context(request, stream, url=None):
    event_url = url or event_public_url(request, stream)
    price = f'{stream.access_price} EUR' if stream.access_price > 0 else 'Gratuito'
    description = (
        f'{stream.artist.name} apresenta {stream.title} em '
        f'{timezone.localtime(stream.scheduled_at).strftime("%d/%m/%Y %H:%M")}. '
        f'Preço: {price}.'
    )
    image = stream.cover_image or stream.artist.photo
    return {
        'description': description,
        'image': absolute_image_url(request, image),
        'title': f'{stream.title} - {stream.artist.name} | StageHub',
        'type': 'website',
        'url': event_url,
    }


def artist_public_url(request, artist):
    return request.build_absolute_uri(reverse('streams:artist_detail', args=[artist.id]))


def artist_og_context(request, artist, url=None):
    artist_url = url or artist_public_url(request, artist)
    description = artist.headline or artist.bio or f'Conhece {artist.name} na StageHub.'
    image = artist.hero_image or artist.photo
    return {
        'description': description[:260],
        'image': absolute_image_url(request, image),
        'title': f'{artist.name} | StageHub',
        'type': 'profile',
        'url': artist_url,
    }


def home(request):
    now = timezone.now()
    query = request.GET.get('q', '').strip()
    newsletter_form = NewsletterSubscriberForm()

    if request.method == 'POST' and request.POST.get('newsletter_submit'):
        newsletter_form = NewsletterSubscriberForm(request.POST)
        if newsletter_form.is_valid():
            newsletter_form.save()
            messages.success(request, 'Subscricao efetuada com sucesso. Obrigado pelo interesse no StageHub!')
            return redirect('streams:home')
        messages.warning(request, 'Nao foi possivel subscrever a newsletter. Confirma os dados abaixo.')

    visible_streams_filter = Q(is_active=True) | Q(scheduled_at__gte=now)
    visible_artist_streams = Prefetch(
        'streams',
        queryset=LiveStream.objects.filter(visible_streams_filter).order_by('-is_active', 'scheduled_at'),
        to_attr='homepage_streams',
    )
    favorite_artist_ids = set()
    favorite_artists = Artist.objects.none().prefetch_related(visible_artist_streams)

    if request.user.is_authenticated and hasattr(request.user, 'fan_profile'):
        favorite_artists = request.user.fan_profile.favorite_artists.prefetch_related(
            visible_artist_streams,
        ).order_by('name')
        favorite_artist_ids = set(favorite_artists.values_list('id', flat=True))

    artists = Artist.objects.prefetch_related(visible_artist_streams)
    concert_streams = LiveStream.objects.filter(visible_streams_filter).select_related('artist')

    if query:
        artist_filter = (
            Q(name__icontains=query)
            | Q(bio__icontains=query)
            | Q(headline__icontains=query)
            | Q(location__icontains=query)
        )
        stream_filter = (
            Q(title__icontains=query)
            | Q(artist__name__icontains=query)
            | Q(artist__bio__icontains=query)
            | Q(artist__headline__icontains=query)
            | Q(artist__location__icontains=query)
        )
        artists = artists.filter(artist_filter)
        concert_streams = concert_streams.filter(stream_filter)

    if favorite_artist_ids:
        artists = artists.annotate(
            favorite_rank=Case(
                When(id__in=favorite_artist_ids, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
        ).order_by('favorite_rank', 'name')
        concert_streams = concert_streams.annotate(
            favorite_rank=Case(
                When(artist_id__in=favorite_artist_ids, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
        )
    else:
        artists = artists.order_by('name')
        concert_streams = concert_streams.annotate(
            favorite_rank=Value(1, output_field=IntegerField()),
        )

    concert_streams = concert_streams.annotate(
        active_rank=Case(
            When(is_active=True, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
    ).order_by('favorite_rank', 'active_rank', 'scheduled_at')

    return render(request, 'streams/home.html', {
        'artists': artists,
        'concert_streams': concert_streams,
        'favorite_artists': favorite_artists,
        'favorite_artist_ids': favorite_artist_ids,
        'newsletter_form': newsletter_form,
        'search_query': query,
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
    artist_url = artist_public_url(request, artist)

    return render(request, 'streams/artist_detail.html', {
        'artist': artist,
        'artist_url': artist_url,
        'gallery_photos': artist.gallery_photos.all(),
        'featured_stream': upcoming_streams.first(),
        'is_favorite': is_favorite,
        'og': artist_og_context(request, artist, artist_url),
        'share_text': f'Descobre {artist.name} na StageHub.',
        'share_url': artist_url,
        'upcoming_streams': upcoming_streams,
        'past_streams': past_streams,
    })


def stream_detail(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    now = timezone.now()
    event_path = reverse('streams:event_detail', args=[stream.id])
    event_url = request.build_absolute_uri(event_path)
    access = None
    has_access = False
    ticket_pricing = None
    if request.user.is_authenticated:
        access = stream.access_decision(request.user)
        has_access = access['allowed']
        fan = getattr(request.user, 'fan_profile', None)
        if fan:
            ticket_pricing = ticket_checkout_pricing(stream, fan)

    return render(request, 'streams/event_detail.html', {
        'access': access,
        'event_path': event_path,
        'event_url': event_url,
        'has_access': has_access,
        'og': event_og_context(request, stream, event_url),
        'scheduled_at_iso': stream.scheduled_at.isoformat(),
        'server_now_iso': now.isoformat(),
        'share_text': f'Junta-te a mim em {stream.title} na StageHub.',
        'share_url': event_url,
        'stream': stream,
        'ticket_pricing': ticket_pricing,
    })


@login_required
def favorite_artist_toggle(request, artist_id):
    if request.method != 'POST':
        return redirect('streams:artist_detail', artist_id=artist_id)

    fan = getattr(request.user, 'fan_profile', None)
    if not fan:
        messages.error(request, 'Apenas contas de pÃºblico podem guardar artistas favoritos.')
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


def can_manage_organizations(user):
    if user.is_staff or user.is_superuser:
        return True
    if getattr(getattr(user, 'profile', None), 'role', '') == 'manager':
        return True
    return OrganizationMember.objects.filter(user=user, role__in=OrganizationMember.EDIT_ROLES).exists()


@login_required
def stream_room(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    access = stream.log_access_decision(request.user, 'stream_room')
    video_locked = False
    if not access['allowed'] and stream.user_can_chat(request.user):
        video_locked = True
        messages.info(request, 'A tua subscricao permite participar no chat. Para ver esta live paga, compra o bilhete.')
    elif not access['allowed']:
        messages.warning(request, 'Precisas de bilhete, acesso gratuito ou arquivo recente por subscricao para entrar nesta sala.')
        return render(request, 'streams/access_required.html', {'stream': stream})
    now = timezone.now()
    event_url = event_public_url(request, stream)
    return render(request, 'streams/room.html', {
        'event_url': event_url,
        'is_stream_started': stream.scheduled_at <= now,
        'og': event_og_context(request, stream, event_url),
        'scheduled_at_iso': stream.scheduled_at.isoformat(),
        'server_now_iso': now.isoformat(),
        'share_text': f'Estou a ver {stream.title} na StageHub. Junta-te a mim.',
        'share_url': event_url,
        'stream': stream,
        'video_locked': video_locked,
    })


@login_required
def dashboard(request):
    if not can_access_dashboard(request.user):
        messages.info(request, 'A tua conta de pÃºblico nao tem dashboard de gestao. Usa a homepage para seguir artistas, entrar em espetÃ¡culos e gerir o teu perfil.')
        return redirect('streams:home')

    artists = editable_artists_for(request.user).order_by('name')
    artist_id = request.GET.get('artist')
    artist = get_object_or_404(artists, pk=artist_id) if artist_id else artists.first()
    organizations = Organization.objects.filter(members__user=request.user).prefetch_related('members', 'artists')
    can_manage_orgs = can_manage_organizations(request.user)

    if not artist:
        messages.info(request, 'Cria uma equipa ou um perfil de artista para comecar a gerir espetÃ¡culos.')
        return render(request, 'dashboard/index.html', {
            'artist': None,
            'artists': artists,
            'can_manage_organizations': can_manage_orgs,
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
        'can_manage_organizations': can_manage_orgs,
        'organizations': organizations,
        'streams': streams,
        'subscribers': subscribers,
        'tips_total': tips_total,
    })


@login_required
def organization_create(request):
    if not can_manage_organizations(request.user):
        messages.error(request, 'Esta area e para managers, equipas ou administradores.')
        return redirect('streams:dashboard')

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

        if action == 'create_cloudflare_live_input':
            if artist.cloudflare_live_input_uid:
                messages.info(request, 'Este artista ja tem um Live Input Cloudflare configurado.')
                return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist.id}")
            try:
                live_input = create_live_input_for_artist(artist)
            except CloudflareStreamError as error:
                messages.error(request, str(error))
                return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist.id}")
            artist.cloudflare_live_input_uid = live_input['uid']
            artist.cloudflare_rtmps_url = live_input['rtmps_url']
            artist.cloudflare_stream_key = live_input['stream_key']
            artist.save(update_fields=[
                'cloudflare_live_input_uid',
                'cloudflare_rtmps_url',
                'cloudflare_stream_key',
            ])
            messages.success(request, 'Live Input Cloudflare criado na conta StageHub e guardado no artista.')
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
        messages.error(request, 'Precisas de um artista ou equipa para criar espetÃ¡culos.')
        return redirect('streams:home')

    if request.method == 'POST':
        form = LiveStreamForm(request.POST, request.FILES)
        artist = get_object_or_404(artists, pk=request.POST.get('artist'))
        if form.is_valid():
            live_stream = form.save(commit=False)
            live_stream.artist = artist
            live_stream.save()
            messages.success(request, 'EspetÃ¡culo criado com sucesso.')
            return redirect(f"{reverse('streams:dashboard')}?artist={artist.id}")
    else:
        form = LiveStreamForm()

    return render(request, 'dashboard/stream_form.html', {'form': form, 'artists': artists})


@login_required
def stream_update(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if not can_manage_artist(request.user, stream.artist):
        messages.error(request, 'Nao tens permissao para gerir este espetÃ¡culo.')
        return redirect('streams:dashboard')

    if request.method == 'POST':
        form = LiveStreamForm(request.POST, request.FILES, instance=stream, artist=stream.artist)
        if form.is_valid():
            form.save()
            messages.success(request, 'EspetÃ¡culo atualizado.')
            return redirect(f"{reverse('streams:dashboard')}?artist={stream.artist_id}")
    else:
        form = LiveStreamForm(instance=stream, artist=stream.artist)
    return render(request, 'dashboard/stream_form.html', {'form': form, 'stream': stream})


@login_required
def stream_toggle_active(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if not can_manage_artist(request.user, stream.artist):
        messages.error(request, 'Nao tens permissao para gerir este espetaculo.')
        return redirect('streams:dashboard')
    if request.method == 'POST':
        stream.is_active = not stream.is_active
        stream.save(update_fields=['is_active'])
        if stream.is_active:
            messages.success(request, 'Stream ativado.')
        else:
            messages.success(request, 'Stream desativado.')
    return redirect('streams:stream_update', stream_id=stream.id)


@login_required
def stream_delete(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if not can_manage_artist(request.user, stream.artist):
        messages.error(request, 'Nao tens permissao para apagar este espetÃ¡culo.')
        return redirect('streams:dashboard')

    artist_id = stream.artist_id
    if request.method == 'POST':
        stream.delete()
        messages.success(request, 'EspetÃ¡culo apagado.')
        return redirect(f"{reverse('streams:dashboard')}?artist={artist_id}")

    return redirect(f"{reverse('streams:stream_update', args=[stream.id])}")

