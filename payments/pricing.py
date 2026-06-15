from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.utils import timezone

from .models import Subscription


PRO_TICKET_DISCOUNT_PERCENT = 50


def stagehub_commission_percent():
    try:
        value = Decimal(str(settings.STAGEHUB_COMMISSION_PERCENT))
    except (InvalidOperation, TypeError):
        value = Decimal('20.00')
    return min(max(value, Decimal('0.00')), Decimal('100.00')).quantize(Decimal('0.01'))


def split_platform_fee(amount):
    amount = Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    percent = stagehub_commission_percent()
    platform_fee = (amount * percent / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    artist_net = (amount - platform_fee).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        'artist_net_amount': artist_net,
        'commission_percent': percent,
        'platform_fee_amount': platform_fee,
    }


def get_active_subscription(fan, artist):
    if not fan:
        return None
    return Subscription.objects.filter(
        fan=fan,
        artist=artist,
        status=Subscription.ACTIVE,
        current_period_end__gte=timezone.now(),
    ).first()


def ticket_checkout_pricing(stream, fan):
    original_price = Decimal(stream.access_price)
    final_price = original_price
    discount_percent = 0
    subscription = get_active_subscription(fan, stream.artist)

    if (
        subscription
        and subscription.is_pro
        and stream.event_type == stream.LIVE
        and original_price > 0
    ):
        discount_percent = PRO_TICKET_DISCOUNT_PERCENT
        final_price = (original_price * Decimal('0.50')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return {
        'discount_percent': discount_percent,
        'final_price': final_price,
        'has_discount': discount_percent > 0,
        'original_price': original_price,
        'subscription': subscription,
    }
