from decimal import Decimal
from decimal import InvalidOperation
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

from accounts.models import Artist, Fan, OrganizationMember
from streams.models import LiveStream, Tip

from .models import StreamTicketPurchase, Subscription
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


def _event_public_url(request, stream):
    return request.build_absolute_uri(reverse('streams:event_detail', args=[stream.id]))


def _event_og_context(request, stream, url=None):
    event_url = url or _event_public_url(request, stream)
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
    fee_split = split_platform_fee(amount)
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

    if checkout_type in {'ticket', 'tip'} and payment_status != 'paid':
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
                'stripe_payment_intent': session.get('payment_intent') or '',
                'stripe_session_id': session_id,
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
                'commission_percent': Decimal(metadata.get('commission_percent') or '0'),
                'status': Subscription.ACTIVE,
                'tier': metadata.get('tier', Subscription.SUBSCRIBER),
                # Valor inicial conservador; eventos invoice/subscription podem refiná-lo.
                'current_period_end': timezone.now() + timedelta(days=31),
            },
        )
        return checkout_type, True

    return checkout_type, False


@login_required
def subscribe_artist(request, artist_id):
    artist = get_object_or_404(Artist, pk=artist_id)
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
    commission_percent = stagehub_commission_percent()

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
def buy_ticket(request, stream_id):
    stream = get_object_or_404(LiveStream, pk=stream_id)
    fan = getattr(request.user, 'fan_profile', None)
    if fan is None:
        messages.error(request, 'Só contas de público podem comprar bilhetes.')
        return redirect('streams:event_detail', stream_id=stream.id)

    access = stream.log_access_decision(request.user, 'buy_ticket')
    if access['allowed']:
        return redirect('streams:room', stream_id=stream.id)

    if stream.access_price <= 0:
        messages.error(request, 'Eventos gratuitos ja nao estao disponiveis na StageHub.')
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
            'stripe_session_id': session.id,
            'paid': False,
        },
    )
    return redirect(session.url)


@login_required
def create_tip(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
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
    artist_id = request.GET.get('artist_id')
    if stream_id:
        return redirect('streams:event_detail', stream_id=stream_id)
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

    return HttpResponse(status=200)
