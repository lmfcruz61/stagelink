from decimal import Decimal
from decimal import InvalidOperation
from datetime import datetime
from datetime import timezone as datetime_timezone
from datetime import timedelta
from urllib.parse import urlencode

import stripe
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from accounts.models import Artist, Fan, OrganizationMember
from streams.models import LiveStream, PhotoGallery, Tip

from .models import PhotoGalleryPurchase, StreamTicketPurchase, Subscription
from .pricing import split_platform_fee, stagehub_commission_percent, ticket_checkout_pricing

stripe.api_key = settings.STRIPE_SECRET_KEY


def _absolute_url(request, name, *args):
    return request.build_absolute_uri(reverse(name, args=args))


def _absolute_url_with_query(request, name, query):
    query_string = urlencode(query)
    query_string = query_string.replace('%7BCHECKOUT_SESSION_ID%7D', '{CHECKOUT_SESSION_ID}')
    return f"{request.build_absolute_uri(reverse(name))}?{query_string}"


def _absolute_static(request, path):
    return request.build_absolute_uri(static(path))


def _absolute_image_url(request, image):
    if image:
        return request.build_absolute_uri(image.url)
    return _absolute_static(request, 'img/stagehub-og-placeholder.svg')


def _stripe_object_livemode(stripe_object):
    livemode = None
    if hasattr(stripe_object, 'get'):
        livemode = stripe_object.get('livemode')
        object_id = stripe_object.get('id', '')
    else:
        livemode = getattr(stripe_object, 'livemode', None)
        object_id = getattr(stripe_object, 'id', '')
    if livemode is not None:
        return bool(livemode)
    return str(object_id).startswith('cs_live_')


def _event_public_url(request, stream):
    return request.build_absolute_uri(reverse('streams:event_detail', args=[stream.id]))


def _event_og_context(request, stream, url=None):
    event_url = url or _event_public_url(request, stream)
    if stream.is_free:
        price = 'Gratuito'
    elif stream.is_subscribers_only:
        price = 'Apenas subscritores'
    else:
        price = f'{stream.access_price} EUR'
    description = (
        f'{stream.artist.name} apresenta {stream.title} em '
        f'{timezone.localtime(stream.scheduled_at).strftime("%d/%m/%Y %H:%M")}. '
        f'Preço: {price}.'
    )
    image = stream.cover_image or stream.artist.photo
    return {
        'description': description,
        'image': _absolute_image_url(request, image),
        'title': f'{stream.title} - {stream.artist.name} | StageHub',
        'type': 'website',
        'url': event_url,
    }


def _render_ticket_success(request, stream, metadata):
    event_url = _event_public_url(request, stream)
    purchase_value = metadata.get('final_price') or str(stream.access_price)
    return render(request, 'payments/checkout_success.html', {
        'event_url': event_url,
        'og': _event_og_context(request, stream, event_url),
        'purchase_value': purchase_value,
        'share_text': f'Acabei de comprar bilhete para {stream.title}! Junta-te a mim no StageHub.',
        'share_url': event_url,
        'stream': stream,
    })


def _amount_to_cents(amount):
    return int((Decimal(amount) * 100).quantize(Decimal('1')))


def _can_manage_artist(user, artist):
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


def _connect_dashboard_url(request, artist):
    return _absolute_url(request, 'payments:stripe_connect_start', artist.id)


def _stripe_account_payload(account):
    return {
        'stripe_details_submitted': bool(account.get('details_submitted')),
        'stripe_charges_enabled': bool(account.get('charges_enabled')),
        'stripe_payouts_enabled': bool(account.get('payouts_enabled')),
    }


def _sync_artist_from_stripe_account_payload(account):
    stripe_account_id = account.get('id')
    if not stripe_account_id:
        return None
    artist = Artist.objects.filter(stripe_account_id=stripe_account_id).first()
    if not artist:
        return None
    payload = _stripe_account_payload(account)
    for field, value in payload.items():
        setattr(artist, field, value)
    artist.save(update_fields=list(payload.keys()))
    return artist


def _sync_artist_stripe_account(artist):
    if not artist.stripe_account_id:
        return artist
    account = stripe.Account.retrieve(artist.stripe_account_id)
    payload = _stripe_account_payload(account)
    for field, value in payload.items():
        setattr(artist, field, value)
    artist.save(update_fields=list(payload.keys()))
    return artist


def _payment_artist_or_redirect(request, artist):
    if not artist.stripe_account_id:
        messages.error(request, 'Este artista ainda nao tem pagamentos Stripe Connect ligados.')
        return None
    try:
        _sync_artist_stripe_account(artist)
    except stripe.error.StripeError:
        messages.error(request, 'Nao foi possivel confirmar a conta Stripe Connect deste artista.')
        return None
    if not artist.stripe_connect_ready:
        messages.error(request, 'Este artista ainda nao terminou a ativacao Stripe para receber pagamentos.')
        return None
    return artist


def _connect_payment_intent_data(artist, amount):
    fee_split = split_platform_fee(amount, artist=artist)
    return fee_split, {
        'application_fee_amount': _amount_to_cents(fee_split['platform_fee_amount']),
        'transfer_data': {
            'destination': artist.stripe_account_id,
        },
    }


def _subscription_tier_from_request(request):
    tier = request.GET.get('tier') or request.POST.get('tier') or Subscription.SUBSCRIBER
    if tier not in dict(Subscription.TIER_CHOICES):
        return Subscription.SUBSCRIBER
    return tier


@login_required
def stripe_connect_start(request, artist_id):
    artist = get_object_or_404(Artist, pk=artist_id)
    if not _can_manage_artist(request.user, artist):
        messages.error(request, 'Nao tens permissao para ligar pagamentos deste artista.')
        return redirect('streams:dashboard')
    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Configura STRIPE_SECRET_KEY para ativar Stripe Connect.')
        return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist.id}")

    try:
        if not artist.stripe_account_id:
            account = stripe.Account.create(
                type='express',
                country='PT',
                email=(artist.user.email if artist.user else request.user.email) or '',
                capabilities={
                    'card_payments': {'requested': True},
                    'transfers': {'requested': True},
                },
                business_profile={
                    'name': artist.name,
                    'product_description': 'Venda de bilhetes, subscricoes e gorjetas na StageHub.',
                },
                metadata={
                    'artist_id': str(artist.id),
                    'artist_name': artist.name,
                },
            )
            artist.stripe_account_id = account.id
            payload = _stripe_account_payload(account)
            for field, value in payload.items():
                setattr(artist, field, value)
            artist.save(update_fields=['stripe_account_id', *payload.keys()])

        if artist.stripe_connect_ready:
            login_link = stripe.Account.create_login_link(artist.stripe_account_id)
            return redirect(login_link.url)

        account_link = stripe.AccountLink.create(
            account=artist.stripe_account_id,
            refresh_url=_absolute_url(request, 'payments:stripe_connect_refresh', artist.id),
            return_url=_absolute_url(request, 'payments:stripe_connect_return', artist.id),
            type='account_onboarding',
        )
    except stripe.error.StripeError as error:
        messages.error(request, f'Nao foi possivel iniciar Stripe Connect: {error}')
        return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist.id}")

    return redirect(account_link.url)


@login_required
def stripe_connect_refresh(request, artist_id):
    return stripe_connect_start(request, artist_id)


@login_required
def stripe_connect_return(request, artist_id):
    artist = get_object_or_404(Artist, pk=artist_id)
    if not _can_manage_artist(request.user, artist):
        messages.error(request, 'Nao tens permissao para consultar pagamentos deste artista.')
        return redirect('streams:dashboard')
    if artist.stripe_account_id and settings.STRIPE_SECRET_KEY:
        try:
            _sync_artist_stripe_account(artist)
        except stripe.error.StripeError as error:
            messages.error(request, f'Nao foi possivel confirmar Stripe Connect: {error}')
            return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist.id}")
    if artist.stripe_connect_ready:
        messages.success(request, 'Stripe Connect ligado. Este artista ja pode receber pagamentos.')
    else:
        messages.info(request, 'Stripe Connect guardado. Completa os dados em falta para ativar pagamentos.')
    return redirect(f"{reverse('streams:artist_profile_edit')}?artist={artist.id}")


def _complete_checkout_session(session):
    metadata = session.get('metadata', {}) or {}
    session_id = session.get('id', '')
    payment_status = session.get('payment_status', '')
    checkout_type = metadata.get('type')
    livemode = _stripe_object_livemode(session)

    if checkout_type in {'ticket', 'tip', 'photo_gallery'} and payment_status != 'paid':
        return checkout_type, False

    if checkout_type == 'ticket':
        final_price = Decimal(metadata.get('final_price') or '0')
        platform_fee = Decimal(metadata.get('platform_fee_amount') or '0')
        artist_net = Decimal(metadata.get('artist_net_amount') or '0')
        StreamTicketPurchase.objects.update_or_create(
            fan_id=metadata['fan_id'],
            stream_id=metadata['stream_id'],
            defaults={
                'amount': final_price,
                'artist_net_amount': artist_net,
                'commission_percent': Decimal(metadata.get('commission_percent') or '0'),
                'platform_fee_amount': platform_fee,
                'stripe_connected_account_id': metadata.get('stripe_connected_account_id', ''),
                'stripe_livemode': livemode,
                'stripe_payment_intent': session.get('payment_intent') or '',
                'stripe_session_id': session_id,
                'paid': True,
            },
        )
        return checkout_type, True

    if checkout_type == 'photo_gallery':
        amount = Decimal(metadata.get('amount') or '0')
        platform_fee = Decimal(metadata.get('platform_fee_amount') or '0')
        artist_net = Decimal(metadata.get('artist_net_amount') or '0')
        PhotoGalleryPurchase.objects.update_or_create(
            fan_id=metadata['fan_id'],
            gallery_id=metadata['gallery_id'],
            defaults={
                'stripe_session_id': session_id,
                'stripe_payment_intent': session.get('payment_intent') or '',
                'stripe_connected_account_id': metadata.get('stripe_connected_account_id', ''),
                'stripe_livemode': livemode,
                'amount': amount,
                'platform_fee_amount': platform_fee,
                'artist_net_amount': artist_net,
                'commission_percent': Decimal(metadata.get('commission_percent') or '0'),
                'paid': True,
            },
        )
        return checkout_type, True

    if checkout_type == 'tip':
        payment_intent = session.get('payment_intent') or session_id
        amount = Decimal(metadata['amount'])
        platform_fee = Decimal(metadata.get('platform_fee_amount') or '0')
        artist_net = Decimal(metadata.get('artist_net_amount') or '0')
        if not Tip.objects.filter(stripe_payment_intent=payment_intent).exists():
            Tip.objects.create(
                fan_id=metadata['fan_id'],
                artist_id=metadata['artist_id'],
                stream_id=metadata['stream_id'],
                amount=amount,
                artist_net_amount=artist_net,
                commission_percent=Decimal(metadata.get('commission_percent') or '0'),
                platform_fee_amount=platform_fee,
                message=metadata.get('message', ''),
                stripe_connected_account_id=metadata.get('stripe_connected_account_id', ''),
                stripe_payment_intent=payment_intent,
                stripe_livemode=livemode,
            )
        return checkout_type, True

    if checkout_type == 'subscription':
        Subscription.objects.update_or_create(
            fan_id=metadata['fan_id'],
            artist_id=metadata['artist_id'],
            defaults={
                'stripe_subscription_id': session.get('subscription', ''),
                'stripe_customer_id': session.get('customer', ''),
                'stripe_connected_account_id': metadata.get('stripe_connected_account_id', ''),
                'stripe_livemode': livemode,
                'commission_percent': Decimal(metadata.get('commission_percent') or '0'),
                'status': Subscription.ACTIVE,
                'tier': metadata.get('tier', Subscription.SUBSCRIBER),
                'cancel_at_period_end': False,
                # Valor inicial conservador; eventos invoice/subscription podem refiná-lo.
                'current_period_end': timezone.now() + timedelta(days=31),
            },
        )
        return checkout_type, True

    return checkout_type, False


@login_required
def subscribe_artist(request, artist_id):
    artist = get_object_or_404(Artist, pk=artist_id)
    if not artist.allows_subscriptions:
        messages.error(request, 'Este artista escolheu vender apenas material pago, sem subscricao ativa.')
        return redirect('streams:artist_detail', artist_id=artist.id)
    fan = getattr(request.user, 'fan_profile', None)
    if fan is None:
        messages.error(request, 'Só contas de público podem subscrever artistas.')
        return redirect('streams:artist_detail', artist_id=artist.id)

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Configura STRIPE_SECRET_KEY para ativar subscrições.')
        return redirect('streams:artist_detail', artist_id=artist.id)
    if not _payment_artist_or_redirect(request, artist):
        return redirect('streams:artist_detail', artist_id=artist.id)

    tier = _subscription_tier_from_request(request)
    tier_label = Subscription.label_for_tier(tier)
    tier_price = Subscription.price_for_tier(tier)
    commission_percent = stagehub_commission_percent(artist)

    session = stripe.checkout.Session.create(
        mode='subscription',
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': f'{tier_label} mensal - {artist.name}'},
                'recurring': {'interval': 'month'},
                'unit_amount': _amount_to_cents(tier_price),
            },
            'quantity': 1,
        }],
        success_url=_absolute_url_with_query(request, 'payments:checkout_success', {
            'session_id': '{CHECKOUT_SESSION_ID}',
            'artist_id': artist.id,
        }),
        cancel_url=_absolute_url_with_query(request, 'payments:checkout_cancel', {
            'artist_id': artist.id,
        }),
        subscription_data={
            'application_fee_percent': float(commission_percent),
            'transfer_data': {
                'destination': artist.stripe_account_id,
            },
        },
        metadata={
            'type': 'subscription',
            'fan_id': fan.id,
            'artist_id': artist.id,
            'tier': tier,
            'commission_percent': str(commission_percent),
            'stripe_connected_account_id': artist.stripe_account_id,
        },
    )
    return redirect(session.url)


@login_required
@require_POST
def cancel_subscription(request, subscription_id):
    fan = getattr(request.user, 'fan_profile', None)
    if fan is None:
        messages.error(request, 'Só contas de público podem gerir subscrições.')
        return redirect('accounts:profile')

    subscription = get_object_or_404(
        Subscription.objects.select_related('artist'),
        pk=subscription_id,
        fan=fan,
    )
    if subscription.status != Subscription.ACTIVE or not subscription.is_current:
        messages.info(request, 'Esta subscrição já não está ativa.')
        return redirect('accounts:profile')
    if subscription.cancel_at_period_end:
        messages.info(request, 'A anulação desta subscrição já está agendada.')
        return redirect('accounts:profile')
    if not subscription.stripe_subscription_id:
        messages.error(request, 'Não foi possível identificar esta subscrição na Stripe. Contacta o suporte.')
        return redirect('accounts:profile')
    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'A Stripe não está configurada. Tenta novamente mais tarde.')
        return redirect('accounts:profile')

    try:
        stripe_subscription = stripe.Subscription.modify(
            subscription.stripe_subscription_id,
            cancel_at_period_end=True,
        )
    except stripe.error.StripeError:
        messages.error(request, 'Não foi possível anular a subscrição na Stripe. Tenta novamente.')
        return redirect('accounts:profile')

    subscription.cancel_at_period_end = bool(stripe_subscription.get('cancel_at_period_end', True))
    update_fields = ['cancel_at_period_end']
    period_end = stripe_subscription.get('current_period_end')
    if period_end:
        subscription.current_period_end = datetime.fromtimestamp(
            period_end,
            tz=datetime_timezone.utc,
        )
        update_fields.append('current_period_end')
    subscription.save(update_fields=update_fields)

    messages.success(
        request,
        f'Subscrição de {subscription.artist.name} anulada. '
        f'Manténs o acesso até {timezone.localtime(subscription.current_period_end):%d/%m/%Y}.',
    )
    return redirect('accounts:profile')


@login_required
def buy_ticket(request, stream_id):
    stream = get_object_or_404(LiveStream, pk=stream_id)
    if stream.is_free:
        return redirect('streams:room', stream_id=stream.id)
    if stream.is_subscribers_only:
        if stream.active_subscription_for_user(request.user):
            return redirect('streams:room', stream_id=stream.id)
        messages.error(request, 'Este conteúdo está disponível apenas para subscritores ativos.')
        return redirect('streams:artist_detail', artist_id=stream.artist_id)
    if not stream.artist.allows_paid_content:
        messages.error(request, 'Este artista disponibiliza conteudo atraves de subscricao, sem compra avulsa.')
        return redirect('streams:event_detail', stream_id=stream.id)
    fan = getattr(request.user, 'fan_profile', None)
    if fan is None:
        messages.error(request, 'Só contas de público podem comprar bilhetes.')
        return redirect('streams:event_detail', stream_id=stream.id)

    access = stream.log_access_decision(request.user, 'buy_ticket')
    if access['allowed']:
        return redirect('streams:room', stream_id=stream.id)

    if stream.artist.paid_content_requires_subscription and not stream.active_subscription_for_user(request.user):
        messages.error(request, 'Este conteudo pago e exclusivo para subscritores ativos deste artista.')
        return redirect('streams:artist_detail', artist_id=stream.artist_id)

    if stream.access_price < Decimal('2.00'):
        messages.error(request, 'O preco minimo de bilhete na StageHub e 2 EUR.')
        return redirect('streams:event_detail', stream_id=stream.id)

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Configura STRIPE_SECRET_KEY para ativar venda de bilhetes.')
        return redirect('streams:event_detail', stream_id=stream.id)
    if not _payment_artist_or_redirect(request, stream.artist):
        return redirect('streams:event_detail', stream_id=stream.id)

    pending_purchase = StreamTicketPurchase.objects.filter(
        fan=fan,
        stream=stream,
        paid=False,
    ).exclude(stripe_session_id='').first()
    if pending_purchase:
        try:
            pending_session = stripe.checkout.Session.retrieve(pending_purchase.stripe_session_id)
        except stripe.error.StripeError:
            pending_session = None
        if pending_session:
            checkout_type, completed = _complete_checkout_session(pending_session)
            if checkout_type == 'ticket' and completed:
                messages.success(request, 'Bilhete confirmado. Ja podes entrar no evento.')
                return redirect('streams:room', stream_id=stream.id)

    pricing = ticket_checkout_pricing(stream, fan)
    product_name = f'Bilhete - {stream.title}'
    if pricing['has_discount']:
        product_name = f'Bilhete Pro 50% - {stream.title}'
    fee_split, payment_intent_data = _connect_payment_intent_data(stream.artist, pricing['final_price'])

    session = stripe.checkout.Session.create(
        mode='payment',
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': product_name},
                'unit_amount': _amount_to_cents(pricing['final_price']),
            },
            'quantity': 1,
        }],
        success_url=_absolute_url_with_query(request, 'payments:checkout_success', {
            'session_id': '{CHECKOUT_SESSION_ID}',
            'stream_id': stream.id,
            'artist_id': stream.artist_id,
        }),
        cancel_url=_absolute_url_with_query(request, 'payments:checkout_cancel', {
            'stream_id': stream.id,
            'artist_id': stream.artist_id,
        }),
        payment_intent_data=payment_intent_data,
        metadata={
            'type': 'ticket',
            'fan_id': fan.id,
            'stream_id': stream.id,
            'original_price': str(pricing['original_price']),
            'final_price': str(pricing['final_price']),
            'discount_percent': str(pricing['discount_percent']),
            'artist_net_amount': str(fee_split['artist_net_amount']),
            'commission_percent': str(fee_split['commission_percent']),
            'platform_fee_amount': str(fee_split['platform_fee_amount']),
            'stripe_connected_account_id': stream.artist.stripe_account_id,
        },
    )
    StreamTicketPurchase.objects.update_or_create(
        fan=fan,
        stream=stream,
        defaults={
            'amount': pricing['final_price'],
            'artist_net_amount': fee_split['artist_net_amount'],
            'commission_percent': fee_split['commission_percent'],
            'platform_fee_amount': fee_split['platform_fee_amount'],
            'stripe_connected_account_id': stream.artist.stripe_account_id,
            'stripe_livemode': _stripe_object_livemode(session),
            'stripe_session_id': session.id,
            'paid': False,
        },
    )
    return redirect(session.url)


@login_required
def buy_photo_gallery(request, gallery_id):
    gallery = get_object_or_404(PhotoGallery.objects.select_related('artist'), pk=gallery_id)
    if gallery.is_free:
        return redirect('streams:photo_gallery_detail', gallery_id=gallery.id)
    if gallery.is_subscribers_only:
        fan = getattr(request.user, 'fan_profile', None)
        has_subscription = bool(
            fan and Subscription.objects.filter(
                fan=fan,
                artist=gallery.artist,
                status=Subscription.ACTIVE,
                current_period_end__gte=timezone.now(),
            ).exists()
        )
        if has_subscription:
            return redirect('streams:photo_gallery_detail', gallery_id=gallery.id)
        messages.error(request, 'Esta galeria está disponível apenas para subscritores ativos.')
        return redirect('streams:artist_detail', artist_id=gallery.artist_id)
    if not gallery.artist.allows_paid_content:
        messages.error(request, 'Este artista disponibiliza galerias atraves de subscricao, sem compra avulsa.')
        return redirect('streams:photo_gallery_detail', gallery_id=gallery.id)
    fan = getattr(request.user, 'fan_profile', None)
    if fan is None:
        messages.error(request, 'So contas de publico podem comprar galerias.')
        return redirect('streams:photo_gallery_detail', gallery_id=gallery.id)

    if gallery.user_has_access(request.user):
        return redirect('streams:photo_gallery_detail', gallery_id=gallery.id)

    if gallery.artist.paid_content_requires_subscription and not Subscription.objects.filter(
        fan=fan,
        artist=gallery.artist,
        status=Subscription.ACTIVE,
        current_period_end__gte=timezone.now(),
    ).exists():
        messages.error(request, 'Esta galeria paga e exclusiva para subscritores ativos deste artista.')
        return redirect('streams:artist_detail', artist_id=gallery.artist_id)

    if not gallery.is_publicly_available:
        messages.error(request, 'Esta galeria ainda nao esta disponivel para compra.')
        return redirect('streams:photo_gallery_detail', gallery_id=gallery.id)

    if gallery.access_price < Decimal('2.00'):
        messages.error(request, 'O preco minimo de acesso a galerias na StageHub e 2 EUR.')
        return redirect('streams:photo_gallery_detail', gallery_id=gallery.id)

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Configura STRIPE_SECRET_KEY para ativar venda de galerias.')
        return redirect('streams:photo_gallery_detail', gallery_id=gallery.id)

    if not _payment_artist_or_redirect(request, gallery.artist):
        return redirect('streams:photo_gallery_detail', gallery_id=gallery.id)

    fee_split, payment_intent_data = _connect_payment_intent_data(gallery.artist, gallery.access_price)
    session = stripe.checkout.Session.create(
        mode='payment',
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'unit_amount': int(gallery.access_price * 100),
                'product_data': {'name': f'Galeria - {gallery.title}'},
            },
            'quantity': 1,
        }],
        success_url=_absolute_url_with_query(request, 'payments:checkout_success', {
            'session_id': '{CHECKOUT_SESSION_ID}',
            'gallery_id': gallery.id,
            'artist_id': gallery.artist_id,
        }),
        cancel_url=_absolute_url_with_query(request, 'payments:checkout_cancel', {
            'gallery_id': gallery.id,
            'artist_id': gallery.artist_id,
        }),
        payment_intent_data=payment_intent_data,
        metadata={
            'type': 'photo_gallery',
            'fan_id': fan.id,
            'artist_id': gallery.artist_id,
            'gallery_id': gallery.id,
            'amount': str(gallery.access_price),
            'platform_fee_amount': str(fee_split['platform_fee_amount']),
            'artist_net_amount': str(fee_split['artist_net_amount']),
            'commission_percent': str(fee_split['commission_percent']),
            'stripe_connected_account_id': gallery.artist.stripe_account_id,
        },
    )
    PhotoGalleryPurchase.objects.update_or_create(
        fan=fan,
        gallery=gallery,
        defaults={
            'stripe_session_id': session.id,
            'stripe_connected_account_id': gallery.artist.stripe_account_id,
            'stripe_livemode': _stripe_object_livemode(session),
            'amount': gallery.access_price,
            'platform_fee_amount': fee_split['platform_fee_amount'],
            'artist_net_amount': fee_split['artist_net_amount'],
            'commission_percent': fee_split['commission_percent'],
            'paid': False,
        },
    )
    return redirect(session.url)


@login_required
def create_tip(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if stream.is_free:
        messages.error(request, 'Este conteúdo gratuito não está disponível para pagamentos.')
        return redirect('streams:room', stream_id=stream.id)
    if stream.artist.paid_content_requires_subscription and not stream.active_subscription_for_user(request.user):
        messages.error(request, 'As gorjetas neste artista estao disponiveis apenas para subscritores ativos.')
        return redirect('streams:room', stream_id=stream.id)
    if stream.access_price <= 0:
        messages.error(request, 'Este evento nao esta disponivel para gorjetas.')
        return redirect('streams:room', stream_id=stream.id)

    fan = getattr(request.user, 'fan_profile', None)
    if fan is None:
        messages.error(request, 'Só contas de público podem enviar gorjetas.')
        return redirect('streams:room', stream_id=stream.id)

    try:
        amount = Decimal(request.POST.get('amount', '0'))
    except InvalidOperation:
        amount = Decimal('0')
    message = request.POST.get('message', '')[:240]
    if amount < Decimal('1.00'):
        messages.error(request, 'A gorjeta mínima é 1 EUR.')
        return redirect('streams:room', stream_id=stream.id)

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Configura STRIPE_SECRET_KEY para ativar gorjetas.')
        return redirect('streams:room', stream_id=stream.id)
    if not _payment_artist_or_redirect(request, stream.artist):
        return redirect('streams:room', stream_id=stream.id)
    fee_split, payment_intent_data = _connect_payment_intent_data(stream.artist, amount)

    session = stripe.checkout.Session.create(
        mode='payment',
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': f'Gorjeta para {stream.artist.name}'},
                'unit_amount': _amount_to_cents(amount),
            },
            'quantity': 1,
        }],
        success_url=_absolute_url_with_query(request, 'payments:checkout_success', {
            'session_id': '{CHECKOUT_SESSION_ID}',
            'stream_id': stream.id,
        }),
        cancel_url=_absolute_url_with_query(request, 'payments:checkout_cancel', {
            'stream_id': stream.id,
        }),
        payment_intent_data=payment_intent_data,
        metadata={
            'type': 'tip',
            'fan_id': fan.id,
            'artist_id': stream.artist_id,
            'stream_id': stream.id,
            'amount': str(amount),
            'artist_net_amount': str(fee_split['artist_net_amount']),
            'commission_percent': str(fee_split['commission_percent']),
            'message': message,
            'platform_fee_amount': str(fee_split['platform_fee_amount']),
            'stripe_connected_account_id': stream.artist.stripe_account_id,
        },
    )
    return redirect(session.url)


@login_required
def checkout_success(request):
    session_id = request.GET.get('session_id', '').strip()
    stream_id = request.GET.get('stream_id')
    artist_id = request.GET.get('artist_id')
    gallery_id = request.GET.get('gallery_id')
    if not session_id:
        messages.error(request, 'Nao foi possivel confirmar o pagamento.')
        return redirect('streams:home')

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Stripe nao esta configurado.')
        return redirect('streams:home')

    try:
        session = stripe.checkout.Session.retrieve(session_id)
    except stripe.error.StripeError:
        fan = getattr(request.user, 'fan_profile', None)
        if fan and stream_id:
            pending_purchase = StreamTicketPurchase.objects.filter(
                fan=fan,
                stream_id=stream_id,
                paid=False,
            ).exclude(stripe_session_id='').first()
            if pending_purchase:
                try:
                    pending_session = stripe.checkout.Session.retrieve(pending_purchase.stripe_session_id)
                except stripe.error.StripeError:
                    pending_session = None
                if pending_session:
                    checkout_type, completed = _complete_checkout_session(pending_session)
                    if checkout_type == 'ticket':
                        if completed:
                            messages.success(request, 'Bilhete confirmado. Ja podes entrar no evento.')
                            stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
                            return _render_ticket_success(request, stream, pending_session.get('metadata', {}) or {})
                        else:
                            messages.warning(request, 'O pagamento ainda nao foi confirmado pelo Stripe.')
                        return redirect('streams:room', stream_id=stream_id)
        messages.error(request, 'Nao foi possivel confirmar o pagamento no Stripe.')
        if stream_id:
            return redirect('streams:room', stream_id=stream_id)
        if artist_id:
            return redirect('streams:artist_detail', artist_id=artist_id)
        return redirect('streams:home')

    checkout_type, completed = _complete_checkout_session(session)
    metadata = session.get('metadata', {}) or {}

    if checkout_type == 'ticket':
        stream_id = metadata.get('stream_id')
        if completed:
            messages.success(request, 'Bilhete confirmado. Ja podes entrar no evento.')
            stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
            return _render_ticket_success(request, stream, metadata)
        else:
            messages.warning(request, 'O pagamento ainda nao foi confirmado pelo Stripe.')
        return redirect('streams:room', stream_id=stream_id)

    if checkout_type == 'tip':
        stream_id = metadata.get('stream_id')
        if completed:
            messages.success(request, 'Gorjeta enviada com sucesso. Obrigado pelo apoio!')
        else:
            messages.warning(request, 'A gorjeta ainda nao foi confirmada pelo Stripe.')
        return redirect('streams:room', stream_id=stream_id)

    if checkout_type == 'photo_gallery':
        gallery_id = metadata.get('gallery_id')
        if completed:
            messages.success(request, 'Acesso a galeria confirmado.')
        else:
            messages.warning(request, 'O pagamento da galeria ainda nao foi confirmado pelo Stripe.')
        return redirect('streams:photo_gallery_detail', gallery_id=gallery_id)

    if checkout_type == 'subscription':
        artist_id = metadata.get('artist_id')
        if completed:
            messages.success(request, 'Subscricao confirmada.')
        else:
            messages.warning(request, 'A subscricao ainda nao foi confirmada pelo Stripe.')
        return redirect('streams:artist_detail', artist_id=artist_id)

    messages.error(request, 'Tipo de pagamento desconhecido.')
    return redirect('streams:home')


@login_required
def checkout_cancel(request):
    messages.info(request, 'Pagamento cancelado. Podes tentar novamente quando quiseres.')
    stream_id = request.GET.get('stream_id')
    gallery_id = request.GET.get('gallery_id')
    artist_id = request.GET.get('artist_id')
    if stream_id:
        return redirect('streams:event_detail', stream_id=stream_id)
    if gallery_id:
        return redirect('streams:photo_gallery_detail', gallery_id=gallery_id)
    if artist_id:
        return redirect('streams:artist_detail', artist_id=artist_id)
    return redirect('streams:home')


@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    signature = request.META.get('HTTP_STRIPE_SIGNATURE')
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError):
        return HttpResponseBadRequest('Webhook inválido')

    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        _complete_checkout_session(session)
        return HttpResponse(status=200)
        metadata = session.get('metadata', {})
        if metadata.get('type') == 'ticket':
            StreamTicketPurchase.objects.update_or_create(
                fan_id=metadata['fan_id'],
                stream_id=metadata['stream_id'],
                defaults={'stripe_session_id': session['id'], 'paid': True},
            )
        elif metadata.get('type') == 'tip':
            Tip.objects.create(
                fan_id=metadata['fan_id'],
                artist_id=metadata['artist_id'],
                stream_id=metadata['stream_id'],
                amount=Decimal(metadata['amount']),
                message=metadata.get('message', ''),
                stripe_payment_intent=session.get('payment_intent', ''),
            )
        elif metadata.get('type') == 'subscription':
            Subscription.objects.update_or_create(
                fan_id=metadata['fan_id'],
                artist_id=metadata['artist_id'],
                defaults={
                    'stripe_subscription_id': session.get('subscription', ''),
                    'stripe_customer_id': session.get('customer', ''),
                    'status': Subscription.ACTIVE,
                    'tier': metadata.get('tier', Subscription.SUBSCRIBER),
                    # Valor inicial conservador; eventos invoice/subscription podem refiná-lo.
                    'current_period_end': timezone.now() + timedelta(days=31),
                },
            )

    if event['type'] == 'account.updated':
        account = event['data']['object']
        _sync_artist_from_stripe_account_payload(account)
        return HttpResponse(status=200)

    return HttpResponse(status=200)
