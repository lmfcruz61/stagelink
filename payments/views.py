from decimal import Decimal
from decimal import InvalidOperation
from datetime import timedelta

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

stripe.api_key = settings.STRIPE_SECRET_KEY


def _absolute_url(request, name, *args):
    return request.build_absolute_uri(reverse(name, args=args))


def _amount_to_cents(amount):
    return int((Decimal(amount) * 100).quantize(Decimal('1')))


@login_required
def subscribe_artist(request, artist_id):
    artist = get_object_or_404(Artist, pk=artist_id)
    fan = getattr(request.user, 'fan_profile', None)
    if fan is None:
        messages.error(request, 'Só contas de fã podem subscrever artistas.')
        return redirect('streams:artist_detail', artist_id=artist.id)

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Configura STRIPE_SECRET_KEY para ativar subscrições.')
        return redirect('streams:artist_detail', artist_id=artist.id)

    session = stripe.checkout.Session.create(
        mode='subscription',
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': f'Subscrição mensal - {artist.name}'},
                'recurring': {'interval': 'month'},
                'unit_amount': _amount_to_cents(settings.STRIPE_MONTHLY_PRICE_EUR),
            },
            'quantity': 1,
        }],
        success_url=_absolute_url(request, 'streams:artist_detail', artist.id),
        cancel_url=_absolute_url(request, 'streams:artist_detail', artist.id),
        metadata={'type': 'subscription', 'fan_id': fan.id, 'artist_id': artist.id},
    )
    return redirect(session.url)


@login_required
def buy_ticket(request, stream_id):
    stream = get_object_or_404(LiveStream, pk=stream_id)
    fan = getattr(request.user, 'fan_profile', None)
    if fan is None:
        messages.error(request, 'Só contas de fã podem comprar bilhetes.')
        return redirect('streams:room', stream_id=stream.id)

    if stream.access_price <= 0:
        StreamTicketPurchase.objects.update_or_create(fan=fan, stream=stream, defaults={'paid': True})
        return redirect('streams:room', stream_id=stream.id)

    if not settings.STRIPE_SECRET_KEY:
        messages.error(request, 'Configura STRIPE_SECRET_KEY para ativar venda de bilhetes.')
        return redirect('streams:artist_detail', artist_id=stream.artist_id)

    session = stripe.checkout.Session.create(
        mode='payment',
        payment_method_types=['card'],
        line_items=[{
            'price_data': {
                'currency': 'eur',
                'product_data': {'name': f'Bilhete - {stream.title}'},
                'unit_amount': _amount_to_cents(stream.access_price),
            },
            'quantity': 1,
        }],
        success_url=_absolute_url(request, 'streams:room', stream.id),
        cancel_url=_absolute_url(request, 'streams:artist_detail', stream.artist_id),
        metadata={'type': 'ticket', 'fan_id': fan.id, 'stream_id': stream.id},
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
    fan = getattr(request.user, 'fan_profile', None)
    if fan is None:
        messages.error(request, 'Só contas de fã podem enviar gorjetas.')
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
        success_url=_absolute_url(request, 'streams:room', stream.id),
        cancel_url=_absolute_url(request, 'streams:room', stream.id),
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
                    # Valor inicial conservador; eventos invoice/subscription podem refiná-lo.
                    'current_period_end': timezone.now() + timedelta(days=31),
                },
            )

    return HttpResponse(status=200)
