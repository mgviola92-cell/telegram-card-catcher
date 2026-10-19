"""Offline-only candidate discovery tests: no Wikimedia requests or image transfer."""
import unittest
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit
from scripts.discover_commons_artwork import build_candidates, discover, search_character

CHAR = {'source_key':'mal:character:42','name':'Example Hero','series':'Example Show'}


def sample_payload():
    return {'query':{'pages':[
        {'ns':6,'title':'File:Example Hero Example Show.png',
         'imageinfo':[{'mime':'image/png','url':'https://upload.wikimedia.org/commons/a/a0/hero.png',
                       'descriptionurl':'https://commons.wikimedia.org/wiki/File:Hero.png',
                       'extmetadata': {'LicenseShortName':{'value':'CC BY-SA 4.0'},
                                       'Artist':{'value':'Artist Example'}}}]},
        {'ns':6,'title':'File:Example Hero NSFW.jpg',
         'imageinfo':[{'mime':'image/jpeg','url':'https://upload.wikimedia.org/commons/a/a0/unsafe.jpg',
                       'descriptionurl':'https://commons.wikimedia.org/wiki/File:Unsafe.jpg'}]},
    ]}}


class CommonsArtworkTests(unittest.TestCase):
    def test_candidates_never_approve_even_with_license_hints(self):
        result = build_candidates(CHAR, sample_payload())
        self.assertEqual(len(result), 1)
        row=result[0]
        self.assertEqual(row['license_hint'], 'CC BY-SA 4.0')
        self.assertEqual(row['source_key'], CHAR['source_key'])
        self.assertFalse(row['approved_for_import'])
        self.assertIsNone(row['permission_reference'])
        self.assertNotIn('image_url', row)  # cannot accidentally feed directly to importer

    def test_missing_metadata_never_claims_rights(self):
        data=sample_payload()
        del data['query']['pages'][0]['imageinfo'][0]['extmetadata']
        self.assertEqual(build_candidates(CHAR, data)[0]['license_hint'], '')

    def test_skip_nonfree_and_untrusted_direct_url(self):
        data=sample_payload()
        info=data['query']['pages'][0]['imageinfo'][0]
        info['extmetadata']['NonFree']={'value':'true'}
        self.assertEqual(build_candidates(CHAR, data), [])
        del info['extmetadata']['NonFree']
        info['url']='https://attacker.example/pic.png'
        self.assertEqual(build_candidates(CHAR, data), [])

    def test_non_images_and_bad_response(self):
        data=sample_payload()
        data['query']['pages'][0]['imageinfo'][0]['mime']='image/svg+xml'
        self.assertEqual(build_candidates(CHAR,data),[])
        self.assertEqual(build_candidates(CHAR, {'batchcomplete': True}), [])
        with self.assertRaises(ValueError):
            build_candidates(CHAR,{'error':'bad'})

    def test_one_request_with_bounded_settings_and_contact(self):
        stream=MagicMock()
        stream.read.return_value=__import__('json').dumps(sample_payload()).encode()
        ctx=MagicMock()
        ctx.__enter__.return_value=stream
        with patch('scripts.discover_commons_artwork.urlopen',return_value=ctx) as fetch:
            candidates=search_character(CHAR,'CardReviewTool/1.0 (dev-contact@example.org)', 2)
        self.assertEqual(len(candidates),1)
        request=fetch.call_args.args[0]
        params=parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(params['gsrnamespace'],['6'])
        self.assertEqual(params['gsrlimit'],['2'])
        self.assertIn('Example Hero',params['gsrsearch'][0])
        self.assertEqual(fetch.call_args.kwargs['timeout'],12)

    def test_bounded_discover_deduplicates_characters(self):
        rows=[CHAR, dict(CHAR),dict(CHAR, source_key='mal:character:43')]
        calls=[]
        def mock_fetch(row,n):
            calls.append(row['source_key'])
            return build_candidates(row,sample_payload(),n)
        result=discover(rows,mock_fetch,limit=1)
        self.assertEqual(calls,[CHAR['source_key']])
        self.assertEqual(len(result),1)

    def test_invalid_limits_and_user_agent(self):
        with self.assertRaises(ValueError):
            discover([CHAR], lambda *x: [], limit=0)
        with self.assertRaises(ValueError):
            search_character(CHAR,'short')

if __name__ == '__main__':
    unittest.main()
