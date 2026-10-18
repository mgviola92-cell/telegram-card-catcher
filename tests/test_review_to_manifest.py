import unittest
from scripts.review_to_manifest import manifest_from_rows

class ReviewedManifestTests(unittest.TestCase):
    def test_only_approved_rows_exported(self):
        rows=[{'source_key':'hero:1','review_status':'approved',
               'image_url':'https://example.org/one.jpg',
               'permission_reference':'permission grant 123'},
              {'source_key':'hero:2','review_status':'pending','image_url':'https://example.org/two.jpg'},
              {'source_key':'hero:3','review_status':'rejected','image_url':'https://example.org/three.jpg'}]
        result=manifest_from_rows(rows)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['source_key'],'hero:1')
        self.assertEqual(result[0]['status'],'approved')

    def test_duplicate_review_ids_rejected(self):
        with self.assertRaises(ValueError):
            manifest_from_rows([{'source_key':'hero:1','review_status':'pending'}]*2)

    def test_approved_without_permission_proof_rejected(self):
        with self.assertRaises(ValueError):
            manifest_from_rows([{'source_key':'hero:1','review_status':'approved',
                                 'image_url':'https://example.org/a.jpg','permission_reference':''}])

    def test_unknown_review_state_rejected(self):
        with self.assertRaises(ValueError):
            manifest_from_rows([{'source_key':'hero:1','review_status':'unknown'}])
