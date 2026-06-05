from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .models import Fan, Profile


class StageLinkSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        extra_data = sociallogin.account.extra_data or {}
        display_name = user.get_full_name() or user.username
        avatar_url = extra_data.get('picture') or extra_data.get('avatar_url') or ''

        # Logins sociais entram como publico por defeito.
        Profile.objects.get_or_create(user=user, defaults={'role': Profile.FAN})
        Fan.objects.get_or_create(
            user=user,
            defaults={
                'display_name': display_name,
                'social_avatar_url': avatar_url,
            },
        )
        return user
