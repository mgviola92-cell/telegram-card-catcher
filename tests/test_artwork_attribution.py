"""Attribution and real anime-style Commons candidate review regressions.

No real web API, photo downloading, image generation, or database writes.
"""
import json
from pathlib import Path
import unittest

from app.artwork_credit import credit_line
from app import card_ui
from scripts.artwork_attribution import CREDIT_FIELDS, credit_tuple, reviewed_credit, safe_page
from scripts.artwork_approval import require_artwork_approval
from scripts.build_reviewed_catalog import assemble
from scripts.commons_media_metadata_audit import inspect_payload
from scripts.prepare_review_queue import make_queue

CANDIDATES=json.loads(Path("data/commons_anime_style_pilot_candidates.review.json").read_text(encoding="utf8"))
STAGED=json.loads(Path("data/commons_anime_style_pilot_metadata.stage.json").read_text(encoding="utf8"))
LICENSE="https://creativecommons.org/licenses/by-sa/3.0/"


def credit():
    return {
        "artwork_author":"Kasuga",
        "artwork_license_name":"CC BY-SA 3.0",
        "artwork_license_url":LICENSE,
        "artwork_page_url":"https://commons.wikimedia.org/wiki/File:Wikipe-tan_sailor_fuku.png",
    }


class AttributionTests(unittest.TestCase):
    def test_existing_legacy_metadata_can_stay_uncredited_without_fabrication(self):
        self.assertEqual(credit_tuple({}),(None,)*4)
        self.assertEqual(credit_line({}),"")
        self.assertEqual(credit_line({"artwork_author":"Anonymous"}),"")

    def test_license_credit_requires_all_four_safe_public_fields(self):
        fields=credit()
        self.assertEqual(credit_tuple(fields),tuple(fields[k] for k in CREDIT_FIELDS))
        for key in CREDIT_FIELDS:
            bad=dict(fields)
            bad.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):
                credit_tuple(bad)
        for url in ("http://commons.wikimedia.org/file",
                    "https://localhost/file.png",
                    "https://127.0.0.1/file.png",
                    "https://user:password@commons.wikimedia.org/file.png",
                    "https://commons.wikimedia.org:8888/file.png",
                    "https://commons.wikimedia.org/file.png#fragment"):
            with self.subTest(url=url):
                self.assertFalse(safe_page(url))
                bad=dict(fields,artwork_page_url=url)
                with self.assertRaises(ValueError):
                    credit_tuple(bad)

    def test_spoiler_free_spawn_credit_and_full_owned_card_attribution(self):
        meta=dict(credit(),name="Wikipe-tan",
                  series="Wikimedia Anime and Manga Project",
                  rarity="Uncommon",generation=1,card_id=9001,
                  aliases=["Wiki-tan"],favorite=False)
        spawn=card_ui.spawn_caption(meta)
        self.assertIn("Kasuga",spawn)
        self.assertIn("CC BY-SA 3.0",spawn)
        self.assertNotIn("Wikipe-tan",spawn)
        self.assertNotIn("Source</a>",spawn)
        owned=card_ui.owned_caption(meta)
        self.assertIn("Wikipe-tan",owned)
        self.assertIn("Kasuga",owned)
        self.assertIn("Source</a>",owned)
        self.assertIn("CC BY-SA 3.0",owned)
        self.assertIn("<code>9001</code>",owned)
        self.assertLess(len(spawn),1024)
        self.assertLess(len(owned),1024)

    def test_html_escape_and_untrusted_url_never_break_telegram_caption(self):
        metadata=dict(credit(),artwork_author='A <B> & "C"',
                      artwork_license_name="CC & <danger>",
                      artwork_license_url='https://creativecommons.org/?q="bad"&id=2',
                      artwork_page_url="https://example.org/wiki/Foo?x=1&y=2")
        body=credit_line(metadata,reveal_source=True)
        self.assertIn("&lt;B&gt;",body)
        self.assertIn("&amp;",body)
        self.assertNotIn("<danger>",body)
        self.assertIn("&quot;",body)
        bad=dict(metadata,artwork_license_url="javascript:alert(1)")
        self.assertNotIn("javascript:",credit_line(bad))
        self.assertNotIn("<a href=\"javascript:",credit_line(bad))

    def test_manifest_credit_must_match_exact_catalog_identity(self):
        card={"source_key":"commons:wikipe-tan:original",
              "image_url":CANDIDATES[0]["candidate_image_url"],**credit()}
        reviewed={"source_key":card["source_key"],
                  "image_url":card["image_url"],
                  "status":"approved",
                  "permission_reference":card["artwork_page_url"],**credit()}
        self.assertEqual(require_artwork_approval([card],[reviewed]),1)
        self.assertEqual(reviewed_credit(card,reviewed),credit_tuple(credit()))
        wrong=dict(reviewed,artwork_author="Some Other Artist")
        with self.assertRaises(ValueError):
            require_artwork_approval([card],[wrong])
        omitted=dict(reviewed)
        omitted.pop("artwork_license_url")
        with self.assertRaises(ValueError):
            require_artwork_approval([card],[omitted])

    def test_wikipe_tan_two_real_files_one_source_identity_zero_approved(self):
        self.assertEqual(len(CANDIDATES),2)
        self.assertEqual({r["character_name"] for r in CANDIDATES},{"Wikipe-tan"})
        self.assertEqual({r["role"] for r in CANDIDATES},
                         {"potential_base_art","potential_variant_art"})
        self.assertEqual(len(STAGED),1)
        self.assertIsNone(STAGED[0]["image_url"])
        self.assertEqual({r["source_key"] for r in STAGED},{"commons:wikipe-tan:original"})
        pending=make_queue(STAGED,limit=5)
        self.assertEqual(pending["review_queue_count"],1)
        self.assertEqual(pending["approved_for_import"],0)
        self.assertEqual(assemble(STAGED,pending["review_queue"])["catalog"],[])

    def test_candidate_commons_info_never_automatically_approves_art(self):
        pages=[]
        for row in CANDIDATES:
            pages.append({
                "title":row["commons_file_title"],
                "imageinfo":[{
                    "url":row["candidate_image_url"],
                    "descriptionurl":row["file_page_url"],
                    "mime":"image/png","width":1000,"height":2100,
                    "size":120_000,
                    "extmetadata":{"LicenseShortName":{"value":"CC BY-SA 3.0"},
                                   "Artist":{"value":"Kasuga"}},
                }],
            })
        result=inspect_payload(CANDIDATES,{"query":{"pages":pages}})
        self.assertEqual(result["candidate_count"],2)
        self.assertEqual(result["metadata_potentially_usable_count"],2)
        self.assertEqual(result["artworks_approved"],0)
        self.assertEqual(result["image_bytes_downloaded"],0)
        self.assertTrue(all(not r["approved_for_import"]
                            for r in result["review_rows"]))


if __name__=="__main__":
    unittest.main()
