"""Curated Wikimedia source review: mocked metadata only, no network/images."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from scripts.commons_category_discovery import (
    discover,parse_members,CATEGORY_IDENTITIES,FILES_PER_CATEGORY
)
from scripts.commons_file_enrichment import (
    enrich,select_titles,parse_imageinfo, BATCH
)
from scripts.build_reviewed_catalog import assemble

CATS=list(CATEGORY_IDENTITIES)
DEMO_FILES={
  CATS[0]:["File:Wikipe-tan 01.png","File:Wikipe-tan happy.jpg",
           "File:Adult Wikipe-tan.png","File:Wikipe-tan screenshot.png"],
  CATS[1]:["File:Commons-tan.jpeg","File:Commons-tan 2.png",
           "File:Commons-tan poster.jpg"],
  CATS[2]:["File:Wikiquote-tan 1.png","File:Quote-tan.png"],
  CATS[3]:["File:Kiki front.png","File:Kiki 2.jpg","File:Kiki cosplay.jpg"],
}


class FakeReply:
    def __init__(self,payload):
        self.body=json.dumps(payload).encode("utf8")
        self.status=200
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.body[:n]


def category_json(titles):
    return {"batchcomplete":True,
            "query":{"categorymembers":[
                {"pageid":idx+1000,"ns":6,"title":name}
                for idx,name in enumerate(titles)]}}


def report():
    return {"source":"Wikimedia Commons categorymembers API",
            "review_titles":[
                row
                for cat,files in DEMO_FILES.items()
                for row in parse_members(cat,category_json(files))["review_titles"]
            ]}


def imageinfo_result(selected, *,extra=None):
    extra=extra or {}
    return {"query":{"pages":[{
        "title":row["commons_file_title"],
        "imageinfo":[{
            "mime":"image/png",
            "url":"https://upload.wikimedia.org/wikipedia/commons/0/00/"+(
                row["commons_file_title"][5:].replace(" ","_")),
            "descriptionurl":"https://commons.wikimedia.org/wiki/"+(
                row["commons_file_title"].replace(" ","_")),
            "width":400,"height":900,"size":125000,
            "extmetadata":{"LicenseShortName":{"value":"CC BY-SA 3.0"},
                           "Artist":{"value":"<b>Creator</b>"},
                           "LicenseUrl":{"value":"https://creativecommons.org/licenses/by-sa/3.0/"}},
            **extra,
        }]
    } for row in selected]}}


class CommonsCategoryDiscoveryTests(unittest.TestCase):
    def test_four_explicit_characters_are_staged_without_images(self):
        self.assertEqual(len(CATEGORY_IDENTITIES),4)
        response=discover(CATS,fetch=False,
                          opener=lambda *x,**k:self.fail("network used"))
        self.assertEqual(response["mode"],"offline")
        self.assertEqual(response["api_requests"],0)
        self.assertEqual(response["file_titles_for_review"],0)
        self.assertEqual(response["approved_artworks"],0)

    def test_parse_filename_hints_filtered_but_not_rights_approved(self):
        one=parse_members(CATS[0],category_json(DEMO_FILES[CATS[0]]))
        self.assertEqual(len(one["review_titles"]),2)
        self.assertEqual(one["rejected"]["potentially_unsuitable_title"],2)
        self.assertTrue(all(x["image_url"] is None for x in one["review_titles"]))
        self.assertTrue(all(x["approved_for_import"] is False for x in one["review_titles"]))
        self.assertTrue(all(not x["audience_suitability_verified"] for x in one["review_titles"]))

    def test_mixed_file_types_are_not_images(self):
        one=parse_members(CATS[0],{"query":{"categorymembers":[
            {"ns":6,"title":"File:Audio.ogg"},
            {"ns":14,"title":"Category:Wikipe-tan"},
            {"ns":6,"title":"File:Fine.jpg"},
            {"ns":6,"title":"File:Fine.jpg"},
        ]}})
        self.assertEqual(len(one["review_titles"]),1)
        self.assertEqual(one["rejected"]["duplicate"],1)
        self.assertEqual(one["rejected"]["not_single_jpeg_png_file"],2)

    def test_provider_continuation_is_reported_not_followed(self):
        data=category_json(["File:One.png"])
        data["continue"]={"cmcontinue":"opaque-next-page","continue":"-||"}
        result=parse_members(CATS[0],data)
        self.assertTrue(result["has_more_pages"])
        self.assertEqual(result["reported_file_rows"],1)

    def test_provider_refusal_aborts_no_retries(self):
        requests=[]
        def refuse(req,timeout):
            requests.append(req)
            raise HTTPError(req.full_url,429,"rate limited",{},None)
        with self.assertRaises(RuntimeError):
            discover(CATS,fetch=True,
                     user_agent="CardKout review contact qa@example.org",
                     opener=refuse)
        self.assertEqual(len(requests),1)

    def test_actual_bounded_network_flow_mocked_once_per_category(self):
        request_urls=[]
        test_case=self
        class Caller:
            def __call__(self,req,timeout):
                request_urls.append(req.full_url)
                test_case.assertEqual(timeout,15)
                # The request contains a specific category label. Never fetch
                # subcategories or paginate into unreviewed material.
                from urllib.parse import parse_qs,urlsplit
                params=parse_qs(urlsplit(req.full_url).query)
                cat=params["cmtitle"][0]
                test_case.assertIn(cat,CATS)
                test_case.assertEqual(params["cmtype"],["file"])
                test_case.assertEqual(params["cmlimit"],["50"])
                return FakeReply(category_json(DEMO_FILES[cat]))
        called=discover(CATS,fetch=True,
                        user_agent="CardKout review contact qa@example.org",
                        opener=Caller())
        self.assertEqual(called["api_requests"],4)
        self.assertEqual(len(request_urls),4)
        self.assertEqual(called["approved_artworks"],0)
        self.assertGreater(called["file_titles_for_review"],4)
        self.assertTrue(all("candidate_image_url" not in x for x in called["review_titles"]))

    def test_whitelist_bounds_and_bad_api_data_fail_closed(self):
        for categories in ([],["Category:Adult Wikipe-tan"],
                           CATS+CATS[:1],[CATS[0],CATS[0]]):
            with self.subTest(categories=categories),self.assertRaises(ValueError):
                discover(categories)
        for body in ({"error":{"code":"bad"}}, {"query":{"categorymembers":"oops"}},
                     {"query":{"categorymembers": [{}]*(FILES_PER_CATEGORY+1)}}):
            with self.subTest(body=body),self.assertRaises(ValueError):
                parse_members(CATS[0],body)


class CommonsImageinfoEnrichmentTests(unittest.TestCase):
    def test_round_robin_spreads_candidates_over_character_identities(self):
        seed=report()
        chosen=select_titles(seed,limit=8)
        self.assertEqual(len(chosen),8)
        self.assertEqual({x["claimed_character_source_key"] for x in chosen},
                         {x[0] for x in CATEGORY_IDENTITIES.values()})
        self.assertEqual(len({x["commons_file_title"] for x in chosen}),8)

    def test_metadata_enrichment_never_autopromotes_art(self):
        chosen=select_titles(report(),limit=6)
        out=parse_imageinfo(chosen,imageinfo_result(chosen))
        self.assertEqual(len(out),6)
        for row in out:
            self.assertIsNone(row["image_url"])
            self.assertTrue(row["metadata_photo_candidate"])
            self.assertTrue(row["candidate_image_url"].startswith(
                "https://upload.wikimedia.org/"))
            self.assertFalse(row["approved_for_import"])
            self.assertFalse(row["audience_suitability_verified"])
            self.assertFalse(row["reuse_rights_verified"])
            self.assertFalse(row["source_identity_verified"])
            self.assertEqual(row["artist_hint_unverified"],"Creator")
        # Category filename suggestions alone never produce a catalog.
        staged=[{"source_key":source,"name":row["claimed_character_name"],
                 "series":row["claimed_series"]}
                for source,row in {x["claimed_character_source_key"]:x
                                   for x in chosen}.items()]
        release=assemble(staged,[])["catalog"]
        self.assertEqual(release,[])

    def test_bad_mime_oversized_and_untrusted_url_fail_closed(self):
        chosen=select_titles(report(),limit=1)
        original=imageinfo_result(chosen)
        bad=original["query"]["pages"][0]["imageinfo"][0]
        for edits in ({"mime":"image/svg+xml"},
                      {"size":20_000_000},
                      {"url":"http://127.0.0.1/danger.png"},
                      {"url":"https://evil.org/danger.jpg"},
                      {"descriptionurl":"https://evil.org/test.jpg"},
                      {"width":0},
                      {"extmetadata":{"NonFree":{"value":"true"}}}):
            with self.subTest(edits=edits):
                response=imageinfo_result(chosen)
                response["query"]["pages"][0]["imageinfo"][0].update(edits)
                items=parse_imageinfo(chosen,response)
                self.assertFalse(items[0]["metadata_photo_candidate"])
                self.assertFalse(items[0]["approved_for_import"])

    def test_offline_enrichment_no_http_and_max_48(self):
        out=enrich(report(),fetch=False,
                   opener=lambda *a,**k:self.fail("Unexpected HTTP"))
        self.assertEqual(out["api_requests"],0)
        self.assertEqual(out["artworks_approved"],0)
        for n in (0,49,True):
            with self.subTest(n=n),self.assertRaises(ValueError):
                select_titles(report(),limit=n)

    def test_one_bounded_imageinfo_call_for_12_titles(self):
        seed=report()
        selected=select_titles(seed,limit=8)
        calls=[]
        def opener(req,timeout):
            calls.append(req)
            self.assertEqual(timeout,16)
            self.assertIn("imageinfo",req.full_url)
            self.assertNotIn("upload.wikimedia.org",req.full_url)
            return FakeReply(imageinfo_result(selected))
        output=enrich(seed,fetch=True,limit=8,
                      user_agent="CardKout contact qa@example.org",opener=opener)
        self.assertEqual(output["selected_file_titles"],8)
        self.assertEqual(output["api_requests"],1)
        self.assertEqual(len(calls),1)
        self.assertEqual(output["image_bytes_downloaded"],0)
        self.assertEqual(output["database_writes"],0)

    def test_clashing_category_identity_is_dropped_from_both_character_pools(self):
        example=report()
        duplicate=example["review_titles"][0]
        example["review_titles"].append({
            **duplicate,
            "category":CATS[1],
            "claimed_character_source_key":CATEGORY_IDENTITIES[CATS[1]][0],
            "claimed_character_name":CATEGORY_IDENTITIES[CATS[1]][1],
            "claimed_series":CATEGORY_IDENTITIES[CATS[1]][2],
        })
        selected=select_titles(example)
        self.assertTrue(selected)
        # Never attribute a shared photo to either character by ordering.
        self.assertNotIn(duplicate["commons_file_title"],
                         {x["commons_file_title"] for x in selected})
        output=enrich(example,fetch=False)
        self.assertEqual(output["ambiguous_cross_character_file_titles_excluded"],1)
        self.assertEqual(output["artworks_approved"],0)


if __name__=="__main__":
    unittest.main()
