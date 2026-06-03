from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('registo/', views.register, name='register'),
    path('login/', views.StageLinkLoginView.as_view(), name='login'),
    path('perfil/', views.profile, name='profile'),
    path('logout/', views.StageLinkLogoutView.as_view(), name='logout'),
]
