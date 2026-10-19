import unittest
from scripts.import_characters import validate

class ImportSafetyTests(unittest.TestCase):
    def item(self,url):
        return dict(source_key='original:test-1',name='Test Hero',series='Test Series',image_url=url)
    def test_https_public_hostname_accepted(self):
        self.assertEqual(len(validate([self.item('https://images.example.org/hero.jpg')])),1)
    def test_localhost_blocked(self):
        with self.assertRaises(ValueError):
            validate([self.item('https://localhost/private')])
    def test_ip_host_blocked(self):
        with self.assertRaises(ValueError):
            validate([self.item('https://127.0.0.1/internal')])
    def test_embedded_credentials_blocked(self):
        with self.assertRaises(ValueError):
            validate([self.item('https://user:password@images.example.org/file')])
    def test_nondefault_port_blocked(self):
        with self.assertRaises(ValueError):
            validate([self.item('https://images.example.org:444/file')])
    def test_invalid_port_rejected(self):
        with self.assertRaises(ValueError):
            validate([self.item('https://images.example.org:bad/file')])
