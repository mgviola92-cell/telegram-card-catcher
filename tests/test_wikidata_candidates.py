"""Wikidata bounded human-review candidate lookup unit checks; no live API."""
import json
import unittest
from unittest.mock import Mock

from scripts.wikidata_candidates import candidates, discover, query_params


ITEM={'source_key':'mal:character:1','name':'Sample Hero','series':'Sample Story'}


class WikidataCandidateTests(unittest.TestCase):
    def test_query_is_bounded_and_carries_maxlag(self):
        params=query_params(ITEM['name'])
        self.assertEqual(params['action'],'wbsearchentities')
        self.assertEqual(params['limit'],'5')
        self.assertEqual(params['maxlag'],'5')
        self.assertEqual(params['type'],'item')
        with self.assertRaises(ValueError):
            query_params(' ',1)
        with self.assertRaises(ValueError):
            query_params('Name',6)

    def test_metadata_hints_never_autoapprove_or_store_images(self):
        payload={'search':[
            {'id':'Q123','label':'Sample Hero','description':'A character in Sample Story'},
            {'id':'Q999','label':'An unrelated item','description':'Different work'},
            {'id':'bad','label':'Bad'}, {'id':'Q123','label':'Duplicate QID'}]}
        rows=candidates(ITEM,payload)
        self.assertEqual(len(rows),2)
        self.assertTrue(rows[0]['label_exact_match_hint'])
        self.assertTrue(rows[0]['series_in_description_hint'])
        self.assertFalse(rows[1]['label_exact_match_hint'])
        self.assertFalse(rows[0]['source_mapping_approved'])
        self.assertFalse(rows[0]['artwork_approved'])
        self.assertIsNone(rows[0]['artwork_url'])
        self.assertNotIn('image_url',rows[0])

    def test_no_fetch_no_network_no_import(self):
        def cannot_fetch(*args,**kwargs):
            raise AssertionError('No network in offline mode')
        result=discover([ITEM,ITEM,{'name':'bad'}],'',opener=cannot_fetch,fetch=False)
        self.assertEqual(result['requested_rows'],1)
        self.assertEqual(result['review_rows'][0]['candidate_count'],0)
        self.assertEqual(result['auto_merged_characters'],0)
        self.assertEqual(result['import_ready'],0)

    def test_online_one_call_and_respects_25_cap(self):
        body=json.dumps({'search':[{'id':'Q42','label':'Sample Hero'}]}).encode('utf8')
        class Response:
            def __init__(self,body): self.body=body
            def __enter__(self): return self
            def __exit__(self,*args): return False
            def read(self,n): return self.body
        used=[]
        def opener(request,timeout):
            used.append((request,timeout))
            return Response(body)
        rows=[dict(ITEM,source_key=f'source:{i}') for i in range(30)]
        result=discover(rows,'CardKout research (contact: hello@example.org)',
                        max_items=25,opener=opener,fetch=True)
        self.assertEqual(len(used),25)
        self.assertEqual(result['requested_rows'],25)
        self.assertEqual(result['review_rows'][0]['candidates'][0]['wikidata_qid'],'Q42')
        self.assertIn('maxlag=5',used[0][0].full_url)
        self.assertEqual(used[0][1],15)
        self.assertFalse(result['review_rows'][0]['import_ready'])

    def test_refuses_missing_contact_or_large_batch(self):
        with self.assertRaises(ValueError):
            discover([ITEM],'BadBot',fetch=True)
        for number in (0,26,True,2.5):
            with self.subTest(number=number), self.assertRaises(ValueError):
                discover([ITEM],'',max_items=number)

    def test_bounded_response(self):
        class HugeResponse:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n): return b'x'*250_001
        with self.assertRaises(ValueError):
            discover([ITEM],'CardKout contact@example.org',fetch=True,
                     opener=lambda request,timeout:HugeResponse())


if __name__=='__main__':
    unittest.main()
