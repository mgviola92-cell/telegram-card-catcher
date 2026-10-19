import unittest
from unittest.mock import Mock
from scripts.database_footprint import audit

class FootprintAuditTests(unittest.TestCase):
    def test_read_only_queries_and_size_fields(self):
        db=Mock()
        db.execute.side_effect=[
            Mock(fetchone=lambda:{'database_bytes':8159232,'readable_size':'7968 kB'}),
            Mock(fetchall=lambda:[{'table_name':'characters','total_bytes':16384,
                                  'table_bytes':8192,'index_bytes':8192,
                                  'estimated_rows':0,'estimated_dead_rows':0}])
        ]
        result=audit(db)
        self.assertEqual(result['database_bytes'],8159232)
        self.assertEqual(result['tables'][0]['index_bytes'],8192)
        self.assertEqual(db.execute.call_count,2)
        for call in db.execute.call_args_list:
            self.assertTrue(call.args[0].lstrip().startswith('SELECT'))
            self.assertNotIn('DELETE',call.args[0])

    def test_pilot_blocks_metadata_without_artwork_approval(self):
        from scripts.pilot_preflight import check
        row={'source_key':'mal:character:123','name':'Hero','series':'Series',
             'image_url':'https://example.org/image.jpg'}
        result=check([row],[])
        self.assertTrue(result['metadata_valid'])
        self.assertFalse(result['can_pilot'])

    def test_pilot_blocks_staged_rows_without_image(self):
        from scripts.pilot_preflight import check
        row={'source_key':'mal:character:123','name':'Hero','series':'Series',
             'image_url':None}
        result=check([row],[])
        self.assertFalse(result['metadata_valid'])
        self.assertFalse(result['can_pilot'])

    def test_catalog_capacity_scenarios_are_not_measured(self):
        from scripts.catalog_capacity import estimate
        r=estimate(50000,100000)
        self.assertGreater(r['estimated_total_bytes'],8_200_192)
        self.assertIn('not measured',r['warning'])
        with self.assertRaises(ValueError):
            estimate(-1,100)

    def test_pilot_review_queue_is_diverse_and_deterministic(self):
        from scripts.build_pilot_review_queue import build_queue
        items=[
            {'source_key':'a:1','name':'Zed','series':'A'},
            {'source_key':'a:2','name':'Ace','series':'A'},
            {'source_key':'b:1','name':'Bee','series':'B'},
            {'source_key':'b:2','name':'Cee','series':'B'},
            {'source_key':'c:1','name':'See','series':'C'},
        ]
        first=build_queue(items,limit=3,max_per_series=2)
        second=build_queue(list(reversed(items)),limit=3,max_per_series=2)
        self.assertEqual(first,second)
        self.assertEqual(len({x['series'] for x in first}),3)
        self.assertTrue(all(x['image_url'] is None for x in first))
        self.assertTrue(all(x['permission_reference'] is None for x in first))

    def test_pilot_review_queue_invalid_limit(self):
        from scripts.build_pilot_review_queue import build_queue
        with self.assertRaises(ValueError):
            build_queue([],limit=0)
