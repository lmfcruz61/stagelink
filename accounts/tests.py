from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import SignUpForm


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
