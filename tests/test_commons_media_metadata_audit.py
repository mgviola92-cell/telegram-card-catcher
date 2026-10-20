"""Commons metadata audit: mock Action API only; no image files/Neon calls."""
import json
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import Mock

from scripts.commons_media_metadata_audit import inspect, inspect_payload


CANDIDATES=json.loads(Path("data/commons_literary_pilot_candidates.review.json").read_text(encoding="utf8"))


def file_page(candidate,*,override=None):
    info={"url":candidate["candidate_image_url"],
          "descriptionurl":candidate["file_page_url"],
          "mime":"image/png","size":200_000,
          "width":1280,"height":2000,
          "extmetadata":{
              "LicenseShortName":{"value":"CC0"},
              "Artist":{"value":"<a href='https://example.org'>W. W. Denslow</a>"},
              "Attribution":{"value":"Original artist"},
              "NonFree":{"value":"false"},
          }}
    info.update(override or {})
    return {"title":candidate["commons_file_title"],"ns":6,"imageinfo":[info]}


def response(*pages):
    return {"query":{"pages":list(pages)}}


class CommonsMediaAuditTests(unittest.TestCase):
    def test_real_candidate_pages_are_staged_but_not_approved(self):
        self.assertEqual(len(CANDIDATES),4)
        self.assertEqual({x["character_name"] for x in CANDIDATES},
                         {"Alice","Tin Woodman","Scarecrow","Dorothy Gale"})
        pages=[file_page(c) for c in CANDIDATES]
        out=inspect_payload(CANDIDATES,response(*pages))
        self.assertEqual(out["candidate_count"],4)
        self.assertEqual(out["metadata_potentially_usable_count"],4)
        self.assertEqual(out["artworks_approved"],0)
        self.assertEqual(out["telegram_uploads"],0)
        self.assertEqual(out["image_bytes_downloaded"],0)
        self.assertEqual(out["database_writes"],0)
        for row in out["review_rows"]:
            self.assertFalse(row["artwork_permission_verified"])
            self.assertFalse(row["source_identity_verified"])
            self.assertFalse(row["telegram_send_verified"])
            self.assertFalse(row["approved_for_import"])
            self.assertEqual(row["artist_unverified"],"W. W. Denslow")
            self.assertTrue(all(row["raw_media_checks"].values()))

    def test_single_bounded_api_request_not_image_download(self):
        used=[]
        data=json.dumps(response(*[file_page(c) for c in CANDIDATES])).encode()
        class Resp:
            def __enter__(self):return self
            def __exit__(self,*a):return False
            def read(self,max_bytes):return data
        def opener(req,timeout):
            used.append((req,timeout))
            return Resp()
        out=inspect(CANDIDATES,fetch=True,
                    user_agent="CardKout metadata audit (contact: qa@example.org)",
                    opener=opener)
        self.assertEqual(len(used),1)
        req,timeout=used[0]
        self.assertTrue(req.full_url.startswith("https://commons.wikimedia.org/w/api.php?"))
        self.assertIn("imageinfo",req.full_url)
        self.assertIn("maxlag",req.full_url)
        self.assertNotIn("upload.wikimedia.org",req.full_url)
        self.assertEqual(timeout,20)
        self.assertEqual(out["metadata_potentially_usable_count"],4)

    def test_default_dry_run_never_reaches_network(self):
        result=inspect(CANDIDATES,opener=lambda *a,**k:self.fail("Network forbidden"))
        self.assertEqual(result["mode"],"offline")
        self.assertTrue(result["requires_live_api_inspection"])

    def test_image_url_mismatch_never_counts_valid(self):
        one=CANDIDATES[0]
        bad=file_page(one,override={"url":"https://upload.wikimedia.org/unrelated.jpg"})
        out=inspect_payload([one],response(bad))
        self.assertFalse(out["review_rows"][0]["metadata_potentially_usable"])
        self.assertFalse(out["review_rows"][0]["raw_media_checks"]["exact_media_url"])

    def test_nonfree_flag_wrong_mime_oversize_and_invalid_dimensions_fail(self):
        one=CANDIDATES[0]
        wrong=file_page(one,override={
            "mime":"image/svg+xml","size":100_000_000,"width":100_000,
            "height":0,"extmetadata":{"NonFree":{"value":"true"}}})
        out=inspect_payload([one],response(wrong))
        row=out["review_rows"][0]
        self.assertFalse(row["metadata_potentially_usable"])
        self.assertEqual(row["raw_media_checks"]["no_nonfree_flag"],False)
        self.assertEqual(out["artworks_approved"],0)

    def test_empty_result_missing_image_stays_pending(self):
        row=inspect_payload([CANDIDATES[0]],response())["review_rows"][0]
        self.assertFalse(row["metadata_potentially_usable"])
        self.assertEqual(row["license_name_unverified"],"")
        self.assertFalse(row["approved_for_import"])

    def test_mismatched_hosts_duplicate_titles_and_schema_fails(self):
        wrong=dict(CANDIDATES[0],file_page_url="https://evil.test/wiki/Fake")
        with self.assertRaises(ValueError):
            inspect_payload([wrong],response())
        with self.assertRaises(ValueError):
            inspect(CANDIDATES[:1]*2,fetch=True,
                    user_agent="CardKout metadata contact qa@example.org")
        with self.assertRaises(ValueError):
            inspect(CANDIDATES*4)
        with self.assertRaises(ValueError):
            inspect_payload([CANDIDATES[0]],{"query":{"pages":"invalid"}})

    def test_rejections_stop_no_retry_and_require_contact(self):
        with self.assertRaises(ValueError):
            inspect(CANDIDATES,fetch=True,user_agent="Bad bot")
        called=[]
        def opener(req,timeout):
            called.append(req)
            raise HTTPError(req.full_url,429,"rate limited",{},None)
        with self.assertRaises(RuntimeError):
            inspect(CANDIDATES[:1],fetch=True,
                    user_agent="CardKout source contact qa@example.org",opener=opener)
        self.assertEqual(len(called),1)

    def test_response_size_capped_and_json_never_saves_license_as_approval(self):
        class Large:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return b"X"*1_000_001
        with self.assertRaises(ValueError):
            inspect(CANDIDATES[:1],fetch=True,
                    user_agent="CardKout source contact qa@example.org",
                    opener=lambda req,timeout: Large())


if __name__=="__main__":
    unittest.main()
