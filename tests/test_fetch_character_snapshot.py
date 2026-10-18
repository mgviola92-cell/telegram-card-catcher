import io
import json
import tempfile
import unittest
from pathlib import Path
from scripts.fetch_character_snapshot import download_snapshot

class Reply:
    status=200
    def __init__(self,content,declared=None):
        self.content=content
        self.headers={'Content-Length':str(declared if declared is not None else len(content))}
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self,n):
        if not hasattr(self,'position'): self.position=0
        part=self.content[self.position:self.position+n]
        self.position+=len(part)
        return part

class SnapshotFetcherTests(unittest.TestCase):
    def test_official_snapshot_saved_when_valid(self):
        content=json.dumps({'data':[{'mal_id':1}]}).encode()
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'snapshot.json'
            self.assertEqual(download_snapshot(dest,opener=lambda *a,**k:Reply(content)),1)
            self.assertEqual(json.loads(dest.read_text())['data'][0]['mal_id'],1)

    def test_over_limit_refused_without_file(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'snapshot.json'
            with self.assertRaises(ValueError):
                download_snapshot(dest,opener=lambda *a,**k:Reply(b'x'*21),max_bytes=20)
            self.assertFalse(dest.exists())

    def test_invalid_json_does_not_overwrite_last_good(self):
        with tempfile.TemporaryDirectory() as folder:
            dest=Path(folder)/'snapshot.json'
            dest.write_text('previous')
            with self.assertRaises(ValueError):
                download_snapshot(dest,opener=lambda *a,**k:Reply(b'{}'))
            self.assertEqual(dest.read_text(),'previous')

    def test_partial_network_reads_are_assembled(self):
        content=json.dumps({'data':[{'mal_id':1},{'mal_id':2}]}).encode()
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/'snapshot.json'
            self.assertEqual(download_snapshot(target,opener=lambda *a,**k:Reply(content)),2)
            self.assertEqual(target.read_bytes(),content)
