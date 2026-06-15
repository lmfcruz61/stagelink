from django.urls import path

from . import views

app_name = 'payments'

urlpatterns = [
    path('artistas/<int:artist_id>/stripe/ligar/', views.stripe_connect_start, name='stripe_connect_start'),
    path('artistas/<int:artist_id>/stripe/refresh/', views.stripe_connect_refresh, name='stripe_connect_refresh'),
    path('artistas/<int:artist_id>/stripe/return/', views.stripe_connect_return, name='stripe_connect_return'),
    path('artistas/<int:artist_id>/subscrever/', views.subscribe_artist, name='subscribe_artist'),
    path('streams/<int:stream_id>/bilhete/', views.buy_ticket, name='buy_ticket'),
    path('streams/<int:stream_id>/gorjeta/', views.create_tip, name='create_tip'),
    path('stripe/sucesso/', views.checkout_success, name='checkout_success'),
    path('stripe/cancelado/', views.checkout_cancel, name='checkout_cancel'),
    path('stripe/webhook/', views.stripe_webhook, name='stripe_webhook'),
]
