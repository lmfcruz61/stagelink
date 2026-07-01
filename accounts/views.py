from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from allauth.socialaccount.models import SocialApp

from .forms import FanProfileForm, SignUpForm


def register(request):
    next_url = request.GET.get('next') or request.POST.get('next') or ''
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Com vários backends ativos (login normal + social), o Django precisa do backend explícito.
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}):
                return redirect(next_url)
            if user.profile.role == 'musician':
                return redirect('streams:dashboard')
            return redirect('streams:home')
    else:
        form = SignUpForm()
    return render(request, 'accounts/register.html', {'form': form, 'next_url': next_url})


class StageLinkLoginView(LoginView):
    template_name = 'accounts/login.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['next'] = self.request.GET.get(self.redirect_field_name) or self.request.POST.get(self.redirect_field_name)
        context['social_providers'] = set(SocialApp.objects.values_list('provider', flat=True))
        return context


class StageLinkLogoutView(LogoutView):
    pass


@login_required
def profile(request):
    artist = getattr(request.user, 'artist_profile', None)
    fan = getattr(request.user, 'fan_profile', None)
    fan_form = None

    if fan:
        if request.method == 'POST':
            fan_form = FanProfileForm(request.POST, request.FILES, instance=fan)
            if fan_form.is_valid():
                fan_form.save()
                return redirect('accounts:profile')
        else:
            fan_form = FanProfileForm(instance=fan)

    return render(request, 'accounts/profile.html', {
        'artist': artist,
        'fan': fan,
        'fan_form': fan_form,
        'subscriptions': (
            fan.subscriptions.select_related('artist').order_by('-created_at')
            if fan else []
        ),
    })
