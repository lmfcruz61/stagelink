from django.urls import path

from . import views

app_name = 'streams'

urlpatterns = [
    path('', views.home, name='home'),
    path('politica-privacidade/', views.privacy_policy, name='privacy_policy'),
    path('politica-cookies/', views.cookie_policy, name='cookie_policy'),
    path('termos-condicoes/', views.terms_conditions, name='terms_conditions'),
    path('artistas/<int:artist_id>/', views.artist_detail, name='artist_detail'),
    path('artistas/<int:artist_id>/favorito/', views.favorite_artist_toggle, name='favorite_artist_toggle'),
    path('galerias/<int:gallery_id>/', views.photo_gallery_detail, name='photo_gallery_detail'),
    path('eventos/<int:stream_id>/', views.stream_detail, name='event_detail'),
    path('streams/<int:stream_id>/', views.stream_room, name='room'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/equipas/nova/', views.organization_create, name='organization_create'),
    path('dashboard/equipas/<int:organization_id>/', views.organization_update, name='organization_update'),
    path('dashboard/artistas/novo/', views.managed_artist_create, name='managed_artist_create'),
    path('dashboard/perfil/', views.artist_profile_edit, name='artist_profile_edit'),
    path('dashboard/galeria/<int:photo_id>/remover/', views.artist_photo_delete, name='artist_photo_delete'),
    path('dashboard/streams/novo/', views.stream_create, name='stream_create'),
    path('dashboard/streams/<int:stream_id>/editar/', views.stream_update, name='stream_update'),
    path('dashboard/streams/<int:stream_id>/alternar-ativo/', views.stream_toggle_active, name='stream_toggle_active'),
    path('dashboard/streams/<int:stream_id>/upload-concluido/', views.stream_mark_upload_complete, name='stream_mark_upload_complete'),
    path('dashboard/streams/<int:stream_id>/apagar/', views.stream_delete, name='stream_delete'),
    path('dashboard/galerias/nova/', views.photo_gallery_create, name='photo_gallery_create'),
    path('dashboard/galerias/<int:gallery_id>/editar/', views.photo_gallery_update, name='photo_gallery_update'),
    path('dashboard/galerias/<int:gallery_id>/apagar/', views.photo_gallery_delete, name='photo_gallery_delete'),
    path('dashboard/galerias/fotos/<int:image_id>/remover/', views.photo_gallery_image_delete, name='photo_gallery_image_delete'),
]
