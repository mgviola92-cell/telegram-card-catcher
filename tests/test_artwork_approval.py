import unittest
from scripts.artwork_approval import require_artwork_approval


class ArtworkApprovalTests(unittest.TestCase):
    def setUp(self):
        self.catalog=[{'source_key':'original:one','image_url':'https://images.example.org/one.jpg'}]
        self.approvals=[{'source_key':'original:one','image_url':'https://images.example.org/one.jpg',
                         'status':'approved','permission_reference':'creator permission #123'}]

    def test_exact_reviewed_artwork_accepted(self):
        self.assertEqual(require_artwork_approval(self.catalog,self.approvals),1)

    def test_changed_artwork_requires_new_approval(self):
        changed=[dict(self.catalog[0],image_url='https://images.example.org/new.jpg')]
        with self.assertRaises(ValueError):
            require_artwork_approval(changed,self.approvals)

    def test_missing_reference_or_unapproved_blocks(self):
        for field,value in [('permission_reference',''),('status','pending')]:
            with self.subTest(field=field),self.assertRaises(ValueError):
                require_artwork_approval(self.catalog,[dict(self.approvals[0],**{field:value})])

    def test_no_approval_and_duplicate_approval_block(self):
        with self.assertRaises(ValueError):
            require_artwork_approval(self.catalog,[])
        with self.assertRaises(ValueError):
            require_artwork_approval(self.catalog,self.approvals*2)
