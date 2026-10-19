import unittest
from scripts.cross_source_reconciliation import report


class CrossSourceTests(unittest.TestCase):
    def test_identical_name_series_are_only_pending_match(self):
        a=[{'source_key':'mal:1','name':'Test Hero','series':'Example Show'}]
        b=[{'source_key':'acdb:2','name':'test  hero','series':' example SHOW '}]
        r=report({'offline':a,'acdb':b})
        self.assertEqual(r['distinct_source_keys'],2)
        self.assertEqual(r['potential_name_plus_series_collision_groups'],1)
        self.assertEqual(r['potential_duplicate_additional_keys'],1)
        self.assertEqual(r['verified_cross_source_matches'],0)
        self.assertIsNone(r['union_unique_characters'])

    def test_same_name_different_series_not_silently_merged(self):
        r=report({'a':[{'source_key':'a:1','name':'Alex','series':'Series A'}],
                  'b':[{'source_key':'b:1','name':'Alex','series':'Series B'}]})
        self.assertEqual(r['potential_duplicate_additional_keys'],0)

    def test_collision_and_bad_data(self):
        r=report({'a':[{'source_key':'x:1','name':'X','series':'A'},
                       {'source_key':'x:1','name':'Y','series':'B'},None]})
        self.assertEqual(r['conflicting_source_keys'],1)
        self.assertEqual(r['invalid_rows'],1)
        self.assertEqual(r['repeated_source_keys'],1)

    def test_bare_list_rejected(self):
        with self.assertRaises(ValueError):
            report([])


if __name__=='__main__':
    unittest.main()
