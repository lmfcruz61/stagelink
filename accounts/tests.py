from django.test import TestCase
from django.urls import reverse


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
