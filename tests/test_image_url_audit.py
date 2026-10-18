import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from scripts.image_url_audit import public_url,check_one,audit

class DummyResponse:
    status=200
    headers={'Content-Type':'image/jpeg'}
    def __enter__(self):return self
    def __exit__(self,*args):pass

class ImageUrlAuditTests(unittest.TestCase):
    @patch('scripts.image_url_audit.socket.getaddrinfo')
    def test_private_ip_blocked(self,dns):
        dns.return_value=[(2,1,6,'',('127.0.0.1',443))]
        self.assertFalse(public_url('https://images.example.org/art.jpg'))
    @patch('scripts.image_url_audit.public_url',return_value=True)
    def test_valid_image_head(self,_):
        class Opener:
            def open(self,*args,**kwargs):return DummyResponse()
        self.assertEqual(check_one('https://images.example.org/a.jpg',Opener())['status'],'ok')
    @patch('scripts.image_url_audit.public_url',return_value=True)
    def test_rejected_redirect(self,_):
        class Opener:
            def open(self,*args,**kwargs):
                raise HTTPError('https://images.example.org/a.jpg',302,'Redirect',{},None)
        self.assertEqual(check_one('https://images.example.org/a.jpg',Opener())['http_status'],302)
    def test_limits(self):
        records=[dict(source_key='custom:one',name='Hero',series='World',image_url='https://images.example.org/a.jpg')]
        result=audit(records,checker=lambda url:{'status':'ok'})
        self.assertEqual(result['checked'],1)
        with self.assertRaises(ValueError):audit(records,limit=101)
