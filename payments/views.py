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
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from accounts.models import Artist, Fan
from streams.models import LiveStream, Tip

from .models import StreamTicketPurchase, Subscription
from .pricing import ticket_checkout_pricing

stripe.api_key = settings.STRIPE_SECRET_KEY


def _absolute_url(request, name, *args):
    return request.build_absolute_uri(reverse(name, args=args))


def _absolute_url_with_query(request, name, query):
    query_string = urlencode(query)
    query_string = query_string.replace('%7BCHECKOUT_SESSION_ID%7D', '{CHECKOUT_SESSION_ID}')
    return f"{request.build_absolute_uri(reverse(name))}?{query_string}"


def _amount_to_cents(amount):
    return int((Decimal(amount) * 100).quantize(Decimal('1')))


def _subscription_tier_from_request(request):
    tier = request.GET.get('tier') or request.POST.get('tier') or Subscription.SUBSCRIBER
    if tier not in dict(Subscription.TIER_CHOICES):
        return Subscription.SUBSCRIBER
    return tier


def _complete_checkout_session(session):
    metadata = session.get('metadata', {}) or {}
    session_id = session.get('id', '')
    payment_status = session.get('payment_status', '')
    checkout_type = metadata.get('type')

    if checkout_type in {'ticket', 'tip'} and payment_status != 'paid':
        return checkout_type, False

    if checkout_type == 'ticket':
        StreamTicketPurchase.objects.update_or_create(
            fan_id=metadata['fan_id'],
            stream_id=metadata['stream_id'],
            defaults={'stripe_session_id': session_id, 'paid': True},
        )
        return checkout_type, True

    if checkout_type == 'tip':
        payment_intent = session.get('payment_intent') or session_id
        if not Tip.objects.filter(stripe_payment_intent=payment_intent).exists():
            Tip.objects.create(
                fan_id=metadata['fan_id'],
                artist_id=metadata['artist_id'],
                stream_id=metadata['stream_id'],
                amount=Decimal(metadata['amount']),
                message=metadata.get('message', ''),
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

    tier = _subscription_tier_from_request(request)
    tier_label = Subscription.label_for_tier(tier)
    tier_price = Subscription.price_for_tier(tier)

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
        metadata={'type': 'subscription', 'fan_id': fan.id, 'artist_id': artist.id, 'tier': tier},
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
        StreamTicketPurchase.objects.update_or_create(fan=fan, stream=stream, defaults={'paid': True})
        return redirect('streams:room', stream_id=stream.id)

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Configura STRIPE_SECRET_KEY para ativar venda de bilhetes.')
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
                messages.success(request, 'Bilhete confirmado. Ja podes entrar no espetaculo.')
                return redirect('streams:room', stream_id=stream.id)

    pricing = ticket_checkout_pricing(stream, fan)
    product_name = f'Bilhete - {stream.title}'
    if pricing['has_discount']:
        product_name = f'Bilhete Pro 50% - {stream.title}'

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
        metadata={
            'type': 'ticket',
            'fan_id': fan.id,
            'stream_id': stream.id,
            'original_price': str(pricing['original_price']),
            'final_price': str(pricing['final_price']),
            'discount_percent': str(pricing['discount_percent']),
        },
    )
    StreamTicketPurchase.objects.update_or_create(
        fan=fan,
        stream=stream,
        defaults={'stripe_session_id': session.id, 'paid': False},
    )
    return redirect(session.url)


@login_required
def create_tip(request, stream_id):
    stream = get_object_or_404(LiveStream.objects.select_related('artist'), pk=stream_id)
    if stream.access_price <= 0:
        messages.error(request, 'Espetaculos gratuitos nao recebem gorjetas na plataforma.')
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
        metadata={
            'type': 'tip',
            'fan_id': fan.id,
            'artist_id': stream.artist_id,
            'stream_id': stream.id,
            'amount': str(amount),
            'message': message,
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
                            messages.success(request, 'Bilhete confirmado. Ja podes entrar no espetaculo.')
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
            messages.success(request, 'Bilhete confirmado. Ja podes entrar no espetaculo.')
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
