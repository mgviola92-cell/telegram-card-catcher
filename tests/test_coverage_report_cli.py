import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

class CoverageReportCLITests(unittest.TestCase):
    def test_generated_report_is_parseable_json(self):
        snapshot={'meta':{'totalCharacters':1},
                  'data':[{'mal_id':5,'name':'Hero',
                    'animeAppearances':[{'anime':{'title':'Example Series'}}]}]}
        with tempfile.TemporaryDirectory() as folder:
            src=Path(folder)/'snapshot.json'
            staged=Path(folder)/'staged.review.json'
            report=Path(folder)/'coverage.json'
            src.write_text(json.dumps(snapshot),encoding='utf-8')
            subprocess.run([sys.executable,'-m','scripts.stage_character_offline',
                str(src),str(staged),'--report',str(report)],check=True,capture_output=True)
            result=json.loads(report.read_text(encoding='utf-8'))
            self.assertEqual(result['snapshot_rows'],1)
            self.assertEqual(result['staged_unique_characters'],1)
            self.assertEqual(result['eligible_for_live_import'],0)
            self.assertIsNone(json.loads(staged.read_text(encoding='utf-8'))[0]['image_url'])
