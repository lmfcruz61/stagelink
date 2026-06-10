from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = 'accounts'

urlpatterns = [
    path('registo/', views.register, name='register'),
    path('login/', views.StageLinkLoginView.as_view(), name='login'),
    path(
        'password/esqueci/',
        auth_views.PasswordResetView.as_view(
            email_template_name='accounts/password_reset_email.html',
            subject_template_name='accounts/password_reset_subject.txt',
            success_url=reverse_lazy('accounts:password_reset_done'),
            template_name='accounts/password_reset_form.html',
        ),
        name='password_reset',
    ),
    path(
        'password/email-enviado/',
        auth_views.PasswordResetDoneView.as_view(template_name='accounts/password_reset_done.html'),
        name='password_reset_done',
    ),
    path(
        'password/novo/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            success_url=reverse_lazy('accounts:password_reset_complete'),
            template_name='accounts/password_reset_confirm.html',
        ),
        name='password_reset_confirm',
    ),
    path(
        'password/concluido/',
        auth_views.PasswordResetCompleteView.as_view(template_name='accounts/password_reset_complete.html'),
        name='password_reset_complete',
    ),
    path('perfil/', views.profile, name='profile'),
    path('logout/', views.StageLinkLogoutView.as_view(), name='logout'),
]
