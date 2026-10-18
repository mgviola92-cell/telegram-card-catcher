import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.anilist_export import export

class ExportResumeTests(unittest.TestCase):
    @patch('scripts.anilist_export.request_page')
    def test_resume_from_later_pages_without_replacing_prior(self,fetch):
        fetch.side_effect=[
            {'characters':[{'id':51,'name':{'full':'New Hero'},'image':{'large':'https://example.org/new.png'},'media':{'nodes':[{'type':'ANIME','title':{'english':'New Show'}}]}}],'pageInfo':{'hasNextPage':True}},
            {'characters':[],'pageInfo':{'hasNextPage':False}}
        ]
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'export.json'
            output.write_text(json.dumps([{'source_key':'original:old','name':'Old Hero','series':'Original','image_url':'https://example.org/old.png'}]))
            self.assertEqual(export(2,str(output),start_page=7),2)
            self.assertEqual([c.args[0] for c in fetch.call_args_list],[7,8])
            self.assertEqual(len(json.loads(output.read_text())),2)

    def test_invalid_start_rejected(self):
        with self.assertRaises(ValueError):
            export(1,'unused.json',start_page=0)
