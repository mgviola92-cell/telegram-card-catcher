"""Mock-only Bangumi public-v0 pilot checks: no real API/image/database calls."""
import json
import unittest
from urllib.error import HTTPError

from scripts.bangumi_review import discover, review_characters, safe_subject_id


def response(payload, status=200):
    class Response:
        def __init__(self):
            self.status=status
        def __enter__(self):
            return self
        def __exit__(self,*args):
            return False
        def read(self, size):
            return json.dumps(payload).encode()
    return Response()


class BangumiReviewTests(unittest.TestCase):
    def test_offline_never_contacts_external_site(self):
        def blocked(*args, **kwargs):
            raise AssertionError("No Bangumi API access without --fetch")
        report=discover([1,2],opener=blocked)
        self.assertEqual(report["subjects_requested"],2)
        self.assertEqual(report["review_only_character_records"],0)
        self.assertEqual(report["database_writes"],0)
        self.assertEqual(report["downloaded_image_bytes"],0)

    def test_age_sensitive_or_unknown_subjects_fail_closed(self):
        for meta in ({"nsfw":True,"name":"Unapproved"},
                     {"name":"Unknown classification"},
                     {"nsfw":"false","name":"Bad flag"},
                     {"nsfw":False,"name":""}):
            calls=[]
            def opener(req,timeout):
                calls.append(req.full_url)
                return response(meta)
            res=discover([123],fetch=True,
                         user_agent="CardKout metadata audit review@example.org",
                         opener=opener)
            self.assertEqual(len(calls),1)
            self.assertEqual(res["review_only_character_records"],0)
            self.assertEqual(res["eligible_subjects"],0)
            self.assertNotIn("Unapproved",str(res))

    def test_exact_two_calls_and_never_copy_image_links(self):
        seen=[]
        subject={"id":3,"name":"Family Friendly Cartoon","nsfw":False}
        characters=[
            {"id":555,"name":"Main Character","images":{"large":"https://x/img.jpg"}},
            {"id":556,"name":"Friend","images":{"small":"https://x/another.jpg"}},
            {"id":555,"name":"Repeated"},
            {"id":"not valid","name":"Skip"},
        ]
        def opener(req,timeout):
            seen.append((req.full_url, timeout, req.get_header("User-agent")))
            return response(subject if req.full_url.endswith("/3") else characters)
        result=discover([3],fetch=True,
                        user_agent="CardKout research contact@example.org",
                        opener=opener)
        self.assertEqual(len(seen),2)
        self.assertTrue(seen[0][0].endswith("/v0/subjects/3"))
        self.assertTrue(seen[1][0].endswith("/v0/subjects/3/characters"))
        self.assertEqual(result["eligible_subjects"],1)
        self.assertEqual(result["review_only_character_records"],2)
        entries=result["subjects"][0]["characters"]
        self.assertEqual(entries[0]["source_key"],"bangumi:character:555")
        self.assertIsNone(entries[0]["image_url"])
        self.assertIsNone(entries[0]["telegram_file_id"])
        self.assertFalse(entries[0]["import_ready"])
        self.assertNotIn("https://x/",str(result))
        self.assertEqual(result["artwork_approved"],0)

    def test_malformed_response_and_abusive_request_limit_rejected(self):
        self.assertIsNone(safe_subject_id(True))
        for ids in ([],list(range(1,8)),[1,1],[-1],["x"]):
            with self.subTest(ids=ids),self.assertRaises(ValueError):
                discover(ids)
        with self.assertRaises(ValueError):
            discover([1],fetch=True,user_agent="UnknownBot")
        with self.assertRaises(ValueError):
            review_characters(1,{"name":"Safe", "nsfw":False},[{}]*101)

    def test_rate_limit_aborts_without_retry(self):
        count=[0]
        def refused(req,timeout):
            count[0]+=1
            raise HTTPError(req.full_url,429,"Too many requests",{},None)
        with self.assertRaises(RuntimeError):
            discover([1],fetch=True,
                     user_agent="CardKout metadata contact@example.org",
                     opener=refused)
        self.assertEqual(count[0],1)

    def test_enormous_json_is_rejected_before_parsing(self):
        class Large:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return b'x'*500_001
        with self.assertRaises(ValueError):
            discover([1],fetch=True,
                     user_agent="CardKout metadata contact@example.org",
                     opener=lambda req,timeout:Large())


if __name__=="__main__":
    unittest.main()
