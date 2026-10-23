"""One remote dataset HTTPS URL, never bulk-download actual picture files."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock
from scripts.bulk_url_dataset import acquired_dataset,validate_dataset_url


class MockResponse:
    def __init__(self,url,data,declared=None):
        self.url=url
        self.io=BytesIO(data)
        self.headers={} if declared is None else {"Content-Length":str(declared)}
        self.status=200
    def geturl(self):
        return self.url
    def read(self,n):
        return self.io.read(n)
    def __enter__(self):
        return self
    def __exit__(self,*args):
        self.io.close()


class SingleDatasetURLTests(unittest.TestCase):
    def test_exact_provider_and_supported_formats(self):
        self.assertEqual(validate_dataset_url(
            "https://trusted.example.org/catalog/100k.jsonl.gz","trusted.example.org"),
            ".jsonl.gz")
        for link in (
            "http://trusted.example.org/data.jsonl",
            "https://trusted.example.org.evil.invalid/data.jsonl",
            "https://127.0.0.1/data.jsonl",
            "https://trusted.example.org:8080/data.jsonl",
            "https://trusted.example.org/sample.png",
            "https://user:pass@trusted.example.org/100k.jsonl",
        ):
            with self.subTest(link=link),self.assertRaises(ValueError):
                validate_dataset_url(link,"trusted.example.org")

    def test_metadata_download_only_temporary_file(self):
        url="https://trusted.example.org/characters.jsonl"
        data=b'{"source_key":"test:character:1","name":"One"}\n'
        called=[]
        def fake(req,timeout):
            called.append(req.full_url)
            return MockResponse(url,data)
        with acquired_dataset(url,expected_host="trusted.example.org",
                              opener=fake) as filename:
            name=Path(filename)
            self.assertTrue(name.exists())
            self.assertEqual(name.read_bytes(),data)
            self.assertEqual(called,[url])
        self.assertFalse(name.exists())

    def test_refuses_redirect_and_excessive_data_then_cleans(self):
        url="https://trusted.example.org/characters.jsonl"
        def wrong(req,timeout):
            return MockResponse("https://evil.invalid/stolen.jsonl",b"hi")
        with self.assertRaisesRegex(ValueError,"redirect"):
            with acquired_dataset(url,expected_host="trusted.example.org",opener=wrong):
                pass
        def large(req,timeout):
            return MockResponse(url,b"12345678")
        with self.assertRaisesRegex(ValueError,"downloaded bytes"):
            with acquired_dataset(url,expected_host="trusted.example.org",
                                  opener=large,max_bytes=5):
                pass
        def header_large(req,timeout):
            return MockResponse(url,b"ok",declared=100)
        with self.assertRaisesRegex(ValueError,"too large"):
            with acquired_dataset(url,expected_host="trusted.example.org",
                                  opener=header_large,max_bytes=5):
                pass


if __name__=="__main__":
    unittest.main()
