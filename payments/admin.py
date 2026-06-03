from django.contrib import admin

from .models import StreamTicketPurchase, Subscription

admin.site.register(Subscription)
admin.site.register(StreamTicketPurchase)
