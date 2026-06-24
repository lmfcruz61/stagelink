from datetime import timezone as datetime_timezone
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.mail import EmailMessage
from django.http import JsonResponse
from django.db.models import Case, Count, IntegerField, Prefetch, Q, Sum, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from accounts.forms import (
    ArtistGalleryUploadForm,
    ContactForm,
    ArtistProfileForm,
    ManagedArtistForm,
    NewsletterSubscriberForm,
    OrganizationForm,
    OrganizationMemberForm,
)
from accounts.models import Artist, ArtistPhoto, Organization, OrganizationMember
from payments.models import PhotoGalleryPurchase, StreamTicketPurchase, Subscription
from payments.pricing import ticket_checkout_pricing

from .cloudflare import CloudflareStreamError, create_direct_upload_for_stream, create_live_input_for_artist
from .forms import LiveStreamForm
from .forms import PhotoGalleryForm, PhotoGalleryImageUploadForm
from .models import LiveStream, PhotoGallery, PhotoGalleryImage


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
    price = f'{stream.access_price} EUR'
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


def photo_gallery_public_url(request, gallery):
    return request.build_absolute_uri(reverse('streams:photo_gallery_detail', args=[gallery.id]))


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

    visible_streams_filter = (Q(is_active=True) | Q(scheduled_at__gte=now)) & Q(access_price__gt=0)
    purchased_stream_ids = set()
    purchased_gallery_ids = set()
    if request.user.is_authenticated and hasattr(request.user, 'fan_profile'):
        purchased_stream_ids = set(
            StreamTicketPurchase.objects.filter(
                fan=request.user.fan_profile,
                paid=True,
            ).values_list('stream_id', flat=True),
        )
        purchased_gallery_ids = set(
            PhotoGalleryPurchase.objects.filter(
                fan=request.user.fan_profile,
                paid=True,
            ).values_list('gallery_id', flat=True),
        )
        if purchased_stream_ids:
            visible_streams_filter |= Q(id__in=purchased_stream_ids)
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
    public_photo_galleries = PhotoGallery.objects.filter(
        (
            Q(is_active=True)
            & Q(moderation_status=PhotoGallery.APPROVED)
            & Q(access_price__gte=PhotoGallery.MIN_PRICE)
        ) | Q(id__in=purchased_gallery_ids),
    ).select_related('artist')

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
        public_photo_galleries = public_photo_galleries.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(artist__name__icontains=query)
            | Q(artist__bio__icontains=query)
            | Q(artist__headline__icontains=query)
            | Q(artist__location__icontains=query)
        )

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
        public_photo_galleries = public_photo_galleries.annotate(
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
        public_photo_galleries = public_photo_galleries.annotate(
            favorite_rank=Value(1, output_field=IntegerField()),
        )

    concert_streams = concert_streams.annotate(
        active_rank=Case(
            When(is_active=True, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
    ).order_by('favorite_rank', 'active_rank', 'scheduled_at')
    public_photo_galleries = public_photo_galleries.order_by('favorite_rank', '-created_at')

    return render(request, 'streams/home.html', {
        'artists': artists,
        'concert_streams': concert_streams,
        'favorite_artists': favorite_artists,
        'favorite_artist_ids': favorite_artist_ids,
        'newsletter_form': newsletter_form,
        'public_photo_galleries': public_photo_galleries,
        'purchased_stream_ids': purchased_stream_ids,
        'purchased_gallery_ids': purchased_gallery_ids,
        'search_query': query,
    })


def privacy_policy(request):
    return render(request, 'legal/privacy_policy.html')


def cookie_policy(request):
    return render(request, 'legal/cookie_policy.html')


def terms_conditions(request):
    return render(request, 'legal/terms_conditions.html')


def client_ip_address(request):
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR') or None


def contact_email_subject(contact_message):
    prefixes = {
        'general': 'GERAL',
        'finance': 'FINANCEIRO',
        'technical': 'TÉCNICO',
    }
    prefix = prefixes.get(contact_message.contact_type, contact_message.get_contact_type_display().upper())
    return f'[STAGEHUB - {prefix}] {contact_message.subject}'


def contact_email_body(contact_message):
    return (
        f'Nome:\n{contact_message.name}\n\n'
        f'Email:\n{contact_message.email}\n\n'
        f'Tipo de Contacto:\n{contact_message.get_contact_type_display()}\n\n'
        f'Assunto:\n{contact_message.subject}\n\n'
        f'Mensagem:\n{contact_message.message}\n\n'
        f'Data:\n{timezone.localtime(contact_message.created_at).strftime("%d/%m/%Y %H:%M")}\n\n'
        f'IP:\n{contact_message.ip_address or "Nao disponivel"}\n'
    )


def contact(request):
    form = ContactForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            contact_message = form.save(commit=False)
            contact_message.ip_address = client_ip_address(request)
            contact_message.user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
            contact_message.save()

            email = EmailMessage(
                subject=contact_email_subject(contact_message),
                body=contact_email_body(contact_message),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                to=['stagehub.platform@gmail.com'],
                reply_to=[contact_message.email],
            )
            try:
                email.send(fail_silently=False)
            except Exception:
                messages.error(request, 'A mensagem foi guardada, mas nao foi possivel enviar o email agora. Vamos rever o pedido no painel interno.')
            else:
                messages.success(request, 'Mensagem enviada com sucesso. Obrigado por contactares a StageHub.')
            return redirect('streams:contact')
        messages.error(request, 'Nao foi possivel enviar a mensagem. Confirma os campos assinalados.')

    return render(request, 'contact/contact.html', {'form': form})


def artist_detail(request, artist_id):
    artist = get_object_or_404(Artist.objects.prefetch_related('gallery_photos'), pk=artist_id)
    now = timezone.now()
    can_manage_current_artist = request.user.is_authenticated and can_manage_artist(request.user, artist)
    streams = artist.streams.all()
    photo_galleries = artist.photo_galleries.all()
    if not can_manage_current_artist:
        streams = streams.filter(Q(is_active=True) | Q(scheduled_at__gte=now), access_price__gt=0)
        photo_galleries = photo_galleries.filter(
            is_active=True,
            moderation_status=PhotoGallery.APPROVED,
            access_price__gte=PhotoGallery.MIN_PRICE,
        )
    upcoming_streams = streams.filter(scheduled_at__gte=now).order_by('scheduled_at')
    video_library_streams = streams.filter(
        event_type__in=(LiveStream.RECORDED, LiveStream.REPLAY),
        scheduled_at__lt=now,
    ).order_by('-scheduled_at')
    past_streams = streams.filter(
        scheduled_at__lt=now,
    ).exclude(
        event_type__in=(LiveStream.RECORDED, LiveStream.REPLAY),
    ).order_by('-scheduled_at')
    is_favorite = False
    has_active_subscription = False
    if request.user.is_authenticated and hasattr(request.user, 'fan_profile'):
        is_favorite = request.user.fan_profile.favorite_artists.filter(pk=artist.pk).exists()
        has_active_subscription = Subscription.objects.filter(
            fan=request.user.fan_profile,
            artist=artist,
            status=Subscription.ACTIVE,
            current_period_end__gte=timezone.now(),
        ).exists()
    artist_url = artist_public_url(request, artist)

    return render(request, 'streams/artist_detail.html', {
        'artist': artist,
        'artist_url': artist_url,
        'can_manage_current_artist': can_manage_current_artist,
        'gallery_photos': artist.gallery_photos.all(),
        'featured_stream': upcoming_streams.first(),
        'is_favorite': is_favorite,
        'has_active_subscription': has_active_subscription,
        'og': artist_og_context(request, artist, artist_url),
        'share_text': f'Descobre {artist.name} na StageHub.',
        'share_url': artist_url,
        'upcoming_streams': upcoming_streams,
        'video_library_streams': video_library_streams,
        'past_streams': past_streams,
        'photo_galleries': photo_galleries.order_by('-created_at'),
    })


def stream_detail(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    now = timezone.now()
    event_path = reverse('streams:event_detail', args=[stream.id])
    event_url = request.build_absolute_uri(event_path)
    access = None
    has_access = False
    has_active_subscription = False
    ticket_pricing = None
    if request.user.is_authenticated:
        access = stream.access_decision(request.user)
        has_access = access['allowed']
        fan = getattr(request.user, 'fan_profile', None)
        if fan:
            ticket_pricing = ticket_checkout_pricing(stream, fan)
            has_active_subscription = bool(stream.active_subscription_for_user(request.user))
    can_buy_ticket = (
        request.user.is_authenticated
        and hasattr(request.user, 'fan_profile')
        and stream.artist.allows_paid_content
        and (not stream.artist.paid_content_requires_subscription or has_active_subscription)
    )

    return render(request, 'streams/event_detail.html', {
        'access': access,
        'can_buy_ticket': can_buy_ticket,
        'event_path': event_path,
        'event_url': event_url,
        'has_access': has_access,
        'has_active_subscription': has_active_subscription,
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
        messages.error(request, 'Apenas contas de público podem guardar artistas favoritos.')
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
    return False


def ensure_artist_live_input(artist):
    if artist.cloudflare_live_input_uid:
        return False
    live_input = create_live_input_for_artist(artist)
    artist.cloudflare_live_input_uid = live_input['uid']
    artist.cloudflare_rtmps_url = live_input['rtmps_url']
    artist.cloudflare_stream_key = live_input['stream_key']
    artist.save(update_fields=[
        'cloudflare_live_input_uid',
        'cloudflare_rtmps_url',
        'cloudflare_stream_key',
    ])
    return True


def sync_stream_live_input(stream):
    if stream.event_type not in {LiveStream.LIVE, LiveStream.PREMIERE}:
        return False
    if not stream.artist.cloudflare_live_input_uid:
        return False
    if stream.cloudflare_live_input_uid == stream.artist.cloudflare_live_input_uid and not stream.cloudflare_video_uid:
        return False
    stream.cloudflare_live_input_uid = stream.artist.cloudflare_live_input_uid
    stream.cloudflare_video_uid = ''
    stream.cloudflare_upload_status = LiveStream.UPLOAD_NOT_REQUESTED
    stream.save(update_fields=[
        'cloudflare_live_input_uid',
        'cloudflare_video_uid',
        'cloudflare_upload_status',
    ])
    return True


def prepare_cloudflare_direct_upload(stream):
    upload = create_direct_upload_for_stream(stream)
    stream.cloudflare_video_uid = upload['uid']
    stream.cloudflare_live_input_uid = ''
    stream.cloudflare_upload_url = upload['upload_url']
    stream.cloudflare_upload_status = LiveStream.UPLOAD_PENDING
    expires_at = parse_datetime(upload.get('expires') or '')
    if expires_at and timezone.is_naive(expires_at):
        expires_at = timezone.make_aware(expires_at, timezone=datetime_timezone.utc)
    stream.cloudflare_upload_expires_at = expires_at
    stream.save(update_fields=[
        'cloudflare_video_uid',
        'cloudflare_live_input_uid',
        'cloudflare_upload_url',
        'cloudflare_upload_status',
        'cloudflare_upload_expires_at',
    ])


def can_manage_organizations(user):
    return False


def artist_payment_summary(artist, subscribers):
    ticket_sales = StreamTicketPurchase.objects.filter(
        stream__artist=artist,
        paid=True,
        stripe_livemode=True,
    ).exclude(stripe_session_id='')
    gallery_sales = PhotoGalleryPurchase.objects.filter(
        gallery__artist=artist,
        paid=True,
        stripe_livemode=True,
    ).exclude(stripe_session_id='')
    tips = artist.tips.filter(stripe_livemode=True)

    ticket_totals = ticket_sales.aggregate(
        count=Count('id'),
        gross=Sum('amount'),
        platform_fee=Sum('platform_fee_amount'),
        artist_net=Sum('artist_net_amount'),
    )
    gallery_totals = gallery_sales.aggregate(
        count=Count('id'),
        gross=Sum('amount'),
        platform_fee=Sum('platform_fee_amount'),
        artist_net=Sum('artist_net_amount'),
    )
    tip_totals = tips.aggregate(
        count=Count('id'),
        gross=Sum('amount'),
        platform_fee=Sum('platform_fee_amount'),
        artist_net=Sum('artist_net_amount'),
    )

    live_subscribers = [
        subscription for subscription in subscribers
        if subscription.stripe_livemode
    ]

    subscriber_monthly_gross = sum(
        Subscription.price_for_tier(subscription.tier)
        for subscription in live_subscribers
    )
    subscriber_monthly_fee = sum(
        Subscription.price_for_tier(subscription.tier)
        * artist_commission_decimal(subscription.commission_percent)
        for subscription in live_subscribers
    )
    subscriber_monthly_net = subscriber_monthly_gross - subscriber_monthly_fee

    total_gross = (
        (ticket_totals['gross'] or 0)
        + (gallery_totals['gross'] or 0)
        + (tip_totals['gross'] or 0)
        + subscriber_monthly_gross
    )
    total_platform_fee = (
        (ticket_totals['platform_fee'] or 0)
        + (gallery_totals['platform_fee'] or 0)
        + (tip_totals['platform_fee'] or 0)
        + subscriber_monthly_fee
    )
    total_artist_net = (
        (ticket_totals['artist_net'] or 0)
        + (gallery_totals['artist_net'] or 0)
        + (tip_totals['artist_net'] or 0)
        + subscriber_monthly_net
    )

    return {
        'ticket_count': ticket_totals['count'] or 0,
        'ticket_gross': money(ticket_totals['gross']),
        'gallery_count': gallery_totals['count'] or 0,
        'gallery_gross': money(gallery_totals['gross']),
        'tip_count': tip_totals['count'] or 0,
        'tip_gross': money(tip_totals['gross']),
        'subscriber_count': len(live_subscribers),
        'subscriber_monthly_gross': money(subscriber_monthly_gross),
        'total_gross': money(total_gross),
        'total_platform_fee': money(total_platform_fee),
        'total_artist_net': money(total_artist_net),
    }


def artist_commission_decimal(commission_rate=None):
    if commission_rate is None:
        commission_rate = getattr(settings, 'STAGEHUB_COMMISSION_PERCENT', '20.00')
    return Decimal(str(commission_rate)) / Decimal('100')


def money(value):
    return Decimal(value or 0).quantize(Decimal('0.01'))


@login_required
def stream_room(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    access = stream.log_access_decision(request.user, 'stream_room')
    video_locked = False
    if not access['allowed'] and stream.user_can_chat(request.user):
        video_locked = True
        messages.info(request, 'A tua subscricao permite participar no chat. Para ver esta live paga, compra o bilhete.')
    elif not access['allowed']:
        messages.warning(request, 'Precisas de bilhete ou arquivo recente por subscricao para entrar nesta sala.')
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
        messages.info(request, 'A tua conta de público nao tem dashboard de gestao. Usa a homepage para seguir artistas, entrar em eventos e gerir o teu perfil.')
        return redirect('streams:home')

    artists = editable_artists_for(request.user).order_by('name')
    artist_id = request.GET.get('artist')
    artist = get_object_or_404(artists, pk=artist_id) if artist_id else artists.first()
    organizations = Organization.objects.filter(members__user=request.user).prefetch_related('members', 'artists')
    can_manage_orgs = can_manage_organizations(request.user)

    if not artist:
        messages.info(request, 'Cria um perfil de artista para comecar a gerir eventos.')
        return render(request, 'dashboard/index.html', {
            'artist': None,
            'artists': artists,
            'can_manage_organizations': can_manage_orgs,
            'organizations': organizations,
            'streams': [],
            'subscribers': [],
            'payment_summary': {},
            'tips_total': 0,
        })

    streams = artist.streams.all()
    photo_galleries = artist.photo_galleries.all()
    subscribers = Subscription.objects.filter(artist=artist, status=Subscription.ACTIVE).select_related('fan__user')
    tips_total = artist.tips.aggregate(total=Sum('amount'))['total'] or 0
    payment_summary = artist_payment_summary(artist, list(subscribers))
    return render(request, 'dashboard/index.html', {
        'artist': artist,
        'artists': artists,
        'can_manage_organizations': can_manage_orgs,
        'organizations': organizations,
        'streams': streams,
        'photo_galleries': photo_galleries,
        'subscribers': subscribers,
        'payment_summary': payment_summary,
        'tips_total': tips_total,
    })


@login_required
def organization_create(request):
    if not can_manage_organizations(request.user):
        messages.error(request, 'Esta area esta indisponivel nesta fase.')
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
            messages.success(request, 'Area criada.')
            return redirect('streams:dashboard')
    else:
        form = OrganizationForm()
    return render(request, 'dashboard/organization_form.html', {'form': form})


@login_required
def organization_update(request, organization_id):
    if not can_manage_organizations(request.user):
        messages.error(request, 'Esta area esta indisponivel nesta fase.')
        return redirect('streams:dashboard')

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
            messages.success(request, 'Area atualizada.')
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
    messages.error(request, 'Esta area esta indisponivel nesta fase.')
    return redirect('streams:dashboard')

    organizations = Organization.objects.filter(
        members__user=request.user,
        members__role__in=OrganizationMember.EDIT_ROLES,
    ).distinct()
    if request.user.is_staff or request.user.is_superuser:
        organizations = Organization.objects.all()

    if not organizations.exists():
        messages.error(request, 'Esta area esta indisponivel nesta fase.')
        return redirect('streams:dashboard')

    if request.method == 'POST':
        form = ManagedArtistForm(request.POST, request.FILES)
        organization = get_object_or_404(organizations, pk=request.POST.get('organization'))
        if form.is_valid():
            artist = form.save(commit=False)
            artist.organization = organization
            artist.save()
            messages.success(request, 'Artista criado.')
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
                messages.info(request, 'Este artista ja tem um canal de transmissao ao vivo configurado.')
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
            messages.success(request, 'Canal de transmissao ao vivo criado e guardado no artista.')
            return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist.id}")

        if action == 'add_photo' and gallery_form.is_valid():
            caption = gallery_form.cleaned_data.get('caption', '')
            for image in gallery_form.cleaned_data['images']:
                ArtistPhoto.objects.create(artist=artist, image=image, caption=caption)
            messages.success(request, 'Foto adicionada a galeria.')
            return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist.id}")
        if action == 'add_photo':
            messages.error(request, 'Nao foi possivel carregar as fotos. Confirma formato, quantidade e tamanho dos ficheiros.')
    else:
        profile_form = ArtistProfileForm(instance=artist)
        gallery_form = ArtistGalleryUploadForm()

    return render(request, 'dashboard/artist_profile_form.html', {
        'artist': artist,
        'artists': artists,
        'profile_form': profile_form,
        'gallery_form': gallery_form,
        'gallery_photos': artist.gallery_photos.all(),
        'artist_gallery_max_upload_images': ArtistGalleryUploadForm.MAX_UPLOAD_IMAGES,
        'artist_gallery_max_upload_image_size': ArtistGalleryUploadForm.MAX_IMAGE_SIZE,
        'artist_gallery_max_upload_total_size': ArtistGalleryUploadForm.MAX_TOTAL_SIZE,
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


def can_view_photo_gallery(request, gallery):
    if gallery.is_publicly_available:
        return True
    if gallery.user_has_access(request.user):
        return True
    return request.user.is_authenticated and can_manage_artist(request.user, gallery.artist)


def sensitive_gallery_confirmed(request):
    return bool(request.session.get('sensitive_gallery_confirmed'))


def photo_gallery_detail(request, gallery_id):
    gallery = get_object_or_404(PhotoGallery.objects.select_related('artist'), pk=gallery_id)
    if not can_view_photo_gallery(request, gallery):
        messages.warning(request, 'Esta galeria ainda nao esta disponivel.')
        return redirect('streams:artist_detail', artist_id=gallery.artist_id)
    can_manage_current_artist = request.user.is_authenticated and can_manage_artist(request.user, gallery.artist)
    if gallery.is_sensitive and not can_manage_current_artist and not sensitive_gallery_confirmed(request):
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'confirm_sensitive_content':
                request.session['sensitive_gallery_confirmed'] = True
                return redirect('streams:photo_gallery_detail', gallery_id=gallery.id)
            messages.info(request, 'Podes continuar a explorar outros conteudos StageHub.')
            return redirect('streams:home')
        return render(request, 'streams/photo_gallery_age_gate.html', {
            'gallery': gallery,
        })
    has_access = gallery.user_has_access(request.user)
    has_active_subscription = False
    if request.user.is_authenticated and hasattr(request.user, 'fan_profile'):
        has_active_subscription = Subscription.objects.filter(
            fan=request.user.fan_profile,
            artist=gallery.artist,
            status=Subscription.ACTIVE,
            current_period_end__gte=timezone.now(),
        ).exists()
    can_buy_gallery = (
        request.user.is_authenticated
        and hasattr(request.user, 'fan_profile')
        and gallery.artist.allows_paid_content
        and (not gallery.artist.paid_content_requires_subscription or has_active_subscription)
    )
    gallery_url = photo_gallery_public_url(request, gallery)
    return render(request, 'streams/photo_gallery_detail.html', {
        'gallery': gallery,
        'gallery_url': gallery_url,
        'has_access': has_access,
        'has_active_subscription': has_active_subscription,
        'can_buy_gallery': can_buy_gallery,
        'share_text': f'Descobre {gallery.title} de {gallery.artist.name} na StageHub.',
        'share_url': gallery_url,
    })


@login_required
def photo_gallery_create(request):
    artists = editable_artists_for(request.user).order_by('name')
    if not artists.exists():
        messages.error(request, 'Precisas de um artista para criar galerias.')
        return redirect('streams:home')

    selected_artist_id = request.GET.get('artist') or request.POST.get('artist')
    selected_artist = get_object_or_404(artists, pk=selected_artist_id) if selected_artist_id else artists.first()

    if request.method == 'POST':
        artist = selected_artist or get_object_or_404(artists, pk=request.POST.get('artist'))
        form = PhotoGalleryForm(request.POST, request.FILES)
        if form.is_valid():
            gallery = form.save(commit=False)
            gallery.artist = artist
            gallery.moderation_status = PhotoGallery.DRAFT
            gallery.save()
            messages.success(request, 'Galeria criada. Adiciona fotos e envia para validacao.')
            return redirect('streams:photo_gallery_update', gallery_id=gallery.id)
        messages.error(request, 'Nao foi possivel criar a galeria. Confirma os campos assinalados.')
    else:
        form = PhotoGalleryForm(initial={'access_price': PhotoGallery.MIN_PRICE})

    return render(request, 'dashboard/photo_gallery_form.html', {
        'artists': artists,
        'form': form,
        'gallery': None,
        'image_form': None,
        'selected_artist_id': selected_artist.id if selected_artist else None,
        'max_gallery_images': PhotoGallery.MAX_IMAGES,
        'max_upload_images': PhotoGalleryImageUploadForm.MAX_UPLOAD_IMAGES,
        'max_upload_image_size': PhotoGalleryImageUploadForm.MAX_IMAGE_SIZE,
        'max_upload_total_size': PhotoGalleryImageUploadForm.MAX_TOTAL_SIZE,
        'remaining_image_slots': PhotoGallery.MAX_IMAGES,
    })


@login_required
def photo_gallery_update(request, gallery_id):
    gallery = get_object_or_404(PhotoGallery.objects.select_related('artist'), pk=gallery_id)
    if not can_manage_artist(request.user, gallery.artist):
        messages.error(request, 'Nao tens permissao para gerir esta galeria.')
        return redirect('streams:dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'save_gallery':
            form = PhotoGalleryForm(request.POST, request.FILES, instance=gallery)
            image_form = PhotoGalleryImageUploadForm(gallery=gallery)
            if form.is_valid():
                gallery = form.save(commit=False)
                if form.has_changed() and gallery.moderation_status == PhotoGallery.APPROVED:
                    gallery.moderation_status = PhotoGallery.DRAFT
                    gallery.is_active = False
                    gallery.rejection_reason = ''
                    gallery.save()
                    messages.success(request, 'Galeria atualizada. Envia novamente para validacao antes de voltar a ficar publica.')
                    return redirect('streams:photo_gallery_update', gallery_id=gallery.id)
                if gallery.moderation_status not in {PhotoGallery.APPROVED, PhotoGallery.SUSPENDED}:
                    gallery.moderation_status = PhotoGallery.DRAFT
                    gallery.rejection_reason = ''
                gallery.save()
                messages.success(request, 'Galeria atualizada.')
                return redirect('streams:photo_gallery_update', gallery_id=gallery.id)
            messages.error(request, 'Nao foi possivel guardar a galeria.')
        elif action == 'add_images':
            form = PhotoGalleryForm(instance=gallery)
            image_form = PhotoGalleryImageUploadForm(request.POST, request.FILES, gallery=gallery)
            if image_form.is_valid():
                start_position = gallery.images.count()
                for index, image in enumerate(image_form.cleaned_data['images'], start=start_position):
                    PhotoGalleryImage.objects.create(gallery=gallery, image=image, position=index)
                if gallery.moderation_status in {PhotoGallery.APPROVED, PhotoGallery.REJECTED}:
                    gallery.moderation_status = PhotoGallery.DRAFT
                    gallery.is_active = False
                    gallery.rejection_reason = ''
                    gallery.save(update_fields=['moderation_status', 'is_active', 'rejection_reason'])
                    messages.success(request, 'Fotos adicionadas. Envia novamente para validacao antes de voltar a ficar publica.')
                    return redirect('streams:photo_gallery_update', gallery_id=gallery.id)
                messages.success(request, 'Fotos adicionadas a galeria.')
                return redirect('streams:photo_gallery_update', gallery_id=gallery.id)
            messages.error(request, 'Nao foi possivel adicionar as fotos.')
        elif action == 'submit_review':
            if not gallery.images.exists():
                messages.error(request, 'Adiciona pelo menos uma foto antes de enviar para validacao.')
            elif gallery.access_price < PhotoGallery.MIN_PRICE:
                messages.error(request, 'O preco minimo de acesso a galerias na StageHub e 2 EUR.')
            else:
                gallery.moderation_status = PhotoGallery.PENDING
                gallery.is_active = False
                gallery.rejection_reason = ''
                gallery.save(update_fields=['moderation_status', 'is_active', 'rejection_reason'])
                messages.success(request, 'Galeria enviada para validacao StageHub.')
            return redirect('streams:photo_gallery_update', gallery_id=gallery.id)
    else:
        form = PhotoGalleryForm(instance=gallery)
        image_form = PhotoGalleryImageUploadForm(gallery=gallery)

    return render(request, 'dashboard/photo_gallery_form.html', {
        'form': form,
        'gallery': gallery,
        'image_form': image_form,
        'max_gallery_images': PhotoGallery.MAX_IMAGES,
        'max_upload_images': PhotoGalleryImageUploadForm.MAX_UPLOAD_IMAGES,
        'max_upload_image_size': PhotoGalleryImageUploadForm.MAX_IMAGE_SIZE,
        'max_upload_total_size': PhotoGalleryImageUploadForm.MAX_TOTAL_SIZE,
        'remaining_image_slots': max(PhotoGallery.MAX_IMAGES - gallery.images.count(), 0),
    })


@login_required
@require_POST
def photo_gallery_image_delete(request, image_id):
    image = get_object_or_404(PhotoGalleryImage.objects.select_related('gallery__artist'), pk=image_id)
    gallery = image.gallery
    if not can_manage_artist(request.user, gallery.artist):
        messages.error(request, 'Nao tens permissao para gerir esta galeria.')
        return redirect('streams:dashboard')
    if gallery.has_paid_purchases:
        messages.error(request, 'Esta galeria ja teve compras. As fotos privadas nao podem ser removidas para proteger quem comprou acesso.')
        return redirect('streams:photo_gallery_update', gallery_id=gallery.id)
    image.delete()
    if gallery.moderation_status == PhotoGallery.REJECTED:
        gallery.moderation_status = PhotoGallery.DRAFT
        gallery.rejection_reason = ''
        gallery.save(update_fields=['moderation_status', 'rejection_reason'])
    messages.success(request, 'Foto removida.')
    return redirect('streams:photo_gallery_update', gallery_id=gallery.id)


@login_required
def photo_gallery_delete(request, gallery_id):
    gallery = get_object_or_404(PhotoGallery.objects.select_related('artist'), pk=gallery_id)
    if not can_manage_artist(request.user, gallery.artist):
        messages.error(request, 'Nao tens permissao para apagar esta galeria.')
        return redirect('streams:dashboard')
    artist_id = gallery.artist_id
    if request.method == 'POST':
        if gallery.has_paid_purchases:
            gallery.is_active = False
            gallery.save(update_fields=['is_active'])
            messages.success(request, 'Galeria retirada de venda. Quem ja comprou continua com acesso.')
            return redirect(f"{reverse('streams:dashboard')}?artist={artist_id}")
        gallery.delete()
        messages.success(request, 'Galeria apagada.')
        return redirect(f"{reverse('streams:dashboard')}?artist={artist_id}")
    return redirect('streams:photo_gallery_update', gallery_id=gallery.id)


@login_required
def stream_create(request):
    artists = editable_artists_for(request.user).order_by('name')
    if not artists.exists():
        messages.error(request, 'Precisas de um artista para criar eventos.')
        return redirect('streams:home')

    selected_artist_id = request.GET.get('artist') or request.POST.get('artist')
    selected_artist = None
    if selected_artist_id:
        selected_artist = get_object_or_404(artists, pk=selected_artist_id)

    if request.method == 'POST':
        artist = selected_artist or get_object_or_404(artists, pk=request.POST.get('artist'))
        form = LiveStreamForm(request.POST, request.FILES, artist=artist)
        if form.is_valid():
            live_stream = form.save(commit=False)
            live_stream.artist = artist
            if live_stream.event_type in {LiveStream.LIVE, LiveStream.PREMIERE}:
                try:
                    created_live_input = ensure_artist_live_input(artist)
                except CloudflareStreamError as error:
                    messages.error(request, str(error))
                    return redirect(f"{reverse('streams:dashboard')}?artist={artist.id}")
                live_stream.cloudflare_live_input_uid = artist.cloudflare_live_input_uid
                live_stream.cloudflare_video_uid = ''
                live_stream.cloudflare_upload_status = LiveStream.UPLOAD_NOT_REQUESTED
            live_stream.save()
            if form.cleaned_data.get('create_upload_url') and live_stream.event_type in {LiveStream.RECORDED, LiveStream.REPLAY}:
                try:
                    prepare_cloudflare_direct_upload(live_stream)
                    messages.success(request, 'Video criado. Envia agora o ficheiro para a biblioteca StageHub.')
                    return redirect('streams:stream_update', stream_id=live_stream.id)
                except CloudflareStreamError as error:
                    messages.error(request, str(error))
                    return redirect('streams:stream_update', stream_id=live_stream.id)
            if live_stream.event_type in {LiveStream.LIVE, LiveStream.PREMIERE}:
                if created_live_input:
                    messages.success(request, 'Live criada e dados OBS preparados.')
                else:
                    messages.success(request, 'Live criada com os dados OBS do artista.')
                return redirect('streams:stream_update', stream_id=live_stream.id)
            messages.success(request, 'Evento criado com sucesso.')
            return redirect(f"{reverse('streams:dashboard')}?artist={artist.id}")
        messages.error(request, 'Nao foi possivel criar o evento. Confirma os campos assinalados.')
    else:
        initial = {}
        if request.GET.get('type') == 'live':
            initial = {
                'event_type': LiveStream.LIVE,
                'video_provider': LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
                'scheduled_at': timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M'),
                'create_upload_url': False,
            }
        elif request.GET.get('type') == 'recorded':
            initial = {
                'event_type': LiveStream.RECORDED,
                'video_provider': LiveStream.VIDEO_PROVIDER_CLOUDFLARE,
                'scheduled_at': timezone.localtime(timezone.now()).strftime('%Y-%m-%dT%H:%M'),
                'create_upload_url': True,
            }
        form = LiveStreamForm(artist=selected_artist, initial=initial)

    current_event_type = form.data.get('event_type') or form.initial.get('event_type')
    return render(request, 'dashboard/stream_form.html', {
        'artists': artists,
        'form': form,
        'selected_artist_id': selected_artist.id if selected_artist else None,
        'is_live_form': current_event_type in {LiveStream.LIVE, LiveStream.PREMIERE},
    })


@login_required
def stream_update(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if not can_manage_artist(request.user, stream.artist):
        messages.error(request, 'Nao tens permissao para gerir este evento.')
        return redirect('streams:dashboard')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'prepare_obs':
            try:
                created_live_input = ensure_artist_live_input(stream.artist)
                sync_stream_live_input(stream)
            except CloudflareStreamError as error:
                messages.error(request, str(error))
                return redirect('streams:stream_update', stream_id=stream.id)
            if created_live_input:
                messages.success(request, 'Dados OBS preparados para esta live.')
            else:
                messages.success(request, 'Live ligada aos dados OBS do artista.')
            return redirect('streams:stream_update', stream_id=stream.id)

        form = LiveStreamForm(request.POST, request.FILES, instance=stream, artist=stream.artist)
        if form.is_valid():
            updated_stream = form.save()
            if updated_stream.event_type in {LiveStream.LIVE, LiveStream.PREMIERE}:
                try:
                    created_live_input = ensure_artist_live_input(updated_stream.artist)
                except CloudflareStreamError as error:
                    messages.error(request, str(error))
                    return redirect('streams:stream_update', stream_id=updated_stream.id)
                sync_stream_live_input(updated_stream)
                if created_live_input:
                    messages.success(request, 'Live atualizada e dados OBS preparados.')
                else:
                    messages.success(request, 'Live atualizada.')
                return redirect('streams:stream_update', stream_id=updated_stream.id)
            if (
                form.cleaned_data.get('create_upload_url')
                and updated_stream.event_type in {LiveStream.RECORDED, LiveStream.REPLAY}
                and not updated_stream.has_pending_direct_upload
            ):
                try:
                    prepare_cloudflare_direct_upload(updated_stream)
                    messages.success(request, 'Upload preparado. Envia o ficheiro abaixo.')
                    return redirect('streams:stream_update', stream_id=updated_stream.id)
                except CloudflareStreamError as error:
                    messages.error(request, str(error))
                    return redirect('streams:stream_update', stream_id=updated_stream.id)
            messages.success(request, 'Evento atualizado.')
            return redirect(f"{reverse('streams:dashboard')}?artist={stream.artist_id}")
        messages.error(request, 'Nao foi possivel atualizar o evento. Confirma os campos assinalados.')
    else:
        sync_stream_live_input(stream)
        form = LiveStreamForm(instance=stream, artist=stream.artist)
    return render(request, 'dashboard/stream_form.html', {
        'form': form,
        'stream': stream,
        'is_live_form': stream.event_type in {LiveStream.LIVE, LiveStream.PREMIERE},
    })


@login_required
def stream_toggle_active(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if not can_manage_artist(request.user, stream.artist):
        messages.error(request, 'Nao tens permissao para gerir este evento.')
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
@require_POST
def stream_mark_upload_complete(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if not can_manage_artist(request.user, stream.artist):
        return JsonResponse({'ok': False, 'error': 'permission_denied'}, status=403)
    if not stream.is_recorded_video:
        return JsonResponse({'ok': False, 'error': 'not_recorded_video'}, status=400)

    stream.cloudflare_upload_status = LiveStream.UPLOAD_UPLOADED
    stream.uploaded_at = timezone.now()
    stream.save(update_fields=['cloudflare_upload_status', 'uploaded_at'])
    return JsonResponse({'ok': True})


@login_required
def stream_delete(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if not can_manage_artist(request.user, stream.artist):
        messages.error(request, 'Nao tens permissao para apagar este evento.')
        return redirect('streams:dashboard')

    artist_id = stream.artist_id
    if request.method == 'POST':
        if stream.has_paid_tickets:
            stream.is_active = False
            stream.save(update_fields=['is_active'])
            messages.success(request, 'Evento arquivado e retirado de venda. Quem ja comprou continua com acesso.')
            return redirect(f"{reverse('streams:dashboard')}?artist={artist_id}")
        stream.delete()
        messages.success(request, 'Evento apagado.')
        return redirect(f"{reverse('streams:dashboard')}?artist={artist_id}")

    return redirect(f"{reverse('streams:stream_update', args=[stream.id])}")

