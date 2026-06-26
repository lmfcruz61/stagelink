from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import SignUpForm
from .models import ActivityLog


class SignUpFormTests(TestCase):
    def test_signup_rejects_existing_email_case_insensitive(self):
        User.objects.create_user(username='luis', email='luis@example.com')

        form = SignUpForm(data={
            'username': 'siulc',
            'email': 'LUIS@example.com',
            'display_name': 'SIULC',
            'role': 'musician',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })

        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_signup_normalizes_new_email_to_lowercase(self):
        form = SignUpForm(data={
            'username': 'newartist',
            'email': 'ARTISTA@EXAMPLE.COM',
            'display_name': 'Novo Artista',
            'role': 'musician',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })

        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, 'artista@example.com')


class PasswordResetPageTests(TestCase):
    def test_login_links_to_password_reset(self):
        response = self.client.get(reverse('accounts:login'))

        self.assertContains(response, reverse('accounts:password_reset'))
        self.assertContains(response, 'Esqueceste a password?')

    def test_password_reset_page_is_available(self):
        response = self.client.get(reverse('accounts:password_reset'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Recuperar password')
        self.assertContains(response, 'link seguro')


@override_settings(ACTIVITY_LOG_ENABLED=True)
class ActivityLogMiddlewareTests(TestCase):
    def test_request_creates_activity_log_without_request_body(self):
        user = User.objects.create_user(username='fanlog', password='pass12345')
        self.client.login(username='fanlog', password='pass12345')

        response = self.client.get(
            reverse('streams:home'),
            HTTP_USER_AGENT='StageHub Test Browser',
            HTTP_REFERER='https://example.com/origem',
            HTTP_X_FORWARDED_FOR='203.0.113.55, 10.0.0.1',
        )

        self.assertEqual(response.status_code, 200)
        log = ActivityLog.objects.filter(path=reverse('streams:home')).latest('created_at')
        self.assertEqual(log.user, user)
        self.assertEqual(log.username, 'fanlog')
        self.assertEqual(log.action, ActivityLog.ACTION_REQUEST)
        self.assertEqual(log.method, 'GET')
        self.assertEqual(log.status_code, 200)
        self.assertEqual(log.ip_address, '203.0.113.55')
        self.assertEqual(log.user_agent, 'StageHub Test Browser')
        self.assertEqual(log.referrer, 'https://example.com/origem')

    def test_media_paths_are_not_logged(self):
        response = self.client.get('/media/teste.jpg')

        self.assertEqual(response.status_code, 404)
        self.assertFalse(ActivityLog.objects.filter(path='/media/teste.jpg').exists())

    def test_admin_can_list_activity_logs(self):
        User.objects.create_superuser(username='adminlog', email='admin@example.com', password='pass12345')
        activity_log = ActivityLog.objects.create(
            username='visitante',
            action=ActivityLog.ACTION_REQUEST,
            method='GET',
            path='/',
            status_code=200,
            ip_address='203.0.113.80',
        )
        self.client.login(username='adminlog', password='pass12345')

        response = self.client.get(reverse('admin:accounts_activitylog_changelist'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'visitante')
        self.assertContains(response, '203.0.113.80')

        detail_response = self.client.get(reverse('admin:accounts_activitylog_change', args=[activity_log.pk]))

        self.assertEqual(detail_response.status_code, 200)
        self.assertContains(detail_response, '203.0.113.80')
