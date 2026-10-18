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
