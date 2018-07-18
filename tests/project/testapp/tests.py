import os
from django.test import TestCase


class Tests(TestCase):
    def test(self):
        self.assertNotIn('LETS_TEST_FAIL', os.environ)
