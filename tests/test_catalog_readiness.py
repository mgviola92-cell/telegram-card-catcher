import unittest
from scripts.catalog_readiness import readiness

class CatalogReadinessTests(unittest.TestCase):
    def setUp(self):
        self.item={'source_key':'demo:hero','name':'Demo Hero',
                   'series':'Demo Series','image_url':'https://example.org/art.png'}
        self.approval={'source_key':'demo:hero','image_url':'https://example.org/art.png',
                       'status':'approved','permission_reference':'creator license grant 123'}

    def test_unapproved_catalog_is_not_ready(self):
        result=readiness([self.item],[])
        self.assertEqual(result['characters'],1)
        self.assertEqual(result['approved_artwork'],0)
        self.assertEqual(result['awaiting_artwork_review'],['demo:hero'])
        self.assertFalse(result['ready_to_import'])

    def test_reviewed_catalog_is_ready(self):
        result=readiness([self.item],[self.approval])
        self.assertTrue(result['ready_to_import'])
        self.assertEqual(result['series'],1)

    def test_changed_image_is_no_longer_approved(self):
        changed=dict(self.item,image_url='https://example.org/new.png')
        result=readiness([changed],[self.approval])
        self.assertFalse(result['ready_to_import'])

    def test_empty_catalog_never_marked_ready(self):
        self.assertFalse(readiness([],[])['ready_to_import'])
