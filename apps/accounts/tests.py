from django.test import TestCase

from .models import User


class UserModelTests(TestCase):
    def test_user_has_uuid_primary_key_and_hashed_password(self):
        user = User.objects.create_user(username="market-player", password="safe-test-password")

        self.assertIsNotNone(user.pk)
        self.assertEqual(user.pk.version, 4)
        self.assertTrue(user.check_password("safe-test-password"))
        self.assertNotEqual(user.password, "safe-test-password")
