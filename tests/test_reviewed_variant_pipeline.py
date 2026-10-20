"""Review-only Commons member -> metadata -> variant worksheet -> importer bridge.

All approvals in this test are synthetic fixtures, NOT real rights decisions.
No artwork bytes, no provider HTTP, no Telegram, no production DB access.
"""
import copy
import tempfile
from pathlib import Path
import json
import unittest
from unittest.mock import patch
from scripts.prepare_variant_review_queue import prepare_queue
from scripts.assemble_reviewed_variants import assemble
from scripts.import_variants import validate as importer_validate
from scripts.build_reviewed_catalog import REQUIRED_CHECKS

PAGE="https://commons.wikimedia.org/wiki/File:Wikipe-tan_head.png"
IMAGE="https://upload.wikimedia.org/wikipedia/commons/a/ac/Wikipe-tan_head.png"
SOURCE="commons:wikipe-tan:original"


def pending_imageinfo():
    return {
        "mode":"bounded_live_imageinfo_metadata",
        "review_rows":[{
            "category":"Category:Wikipe-tan",
            "claimed_character_source_key":SOURCE,
            "claimed_character_name":"Wikipe-tan",
            "claimed_series":"Wikimedia mascots",
            "commons_file_title":"File:Wikipe-tan head.png",
            "candidate_image_url":IMAGE,
            "file_page_url":PAGE,
            "artist_hint_unverified":"Kasuga",
            "license_hint_unverified":"CC BY-SA 3.0",
            "metadata_photo_candidate":True,
            "approved_for_import":False,
        }],
    }


def reviewed(queue):
    return {
        "character_source_key":queue["character_source_key"],
        "variant_key":queue["variant_key"],
        "candidate_file_title":queue["candidate_file_title"],
        "status":"approved",
        "image_url":queue["candidate_image_url"],
        "artwork_page_url":queue["candidate_file_page"],
        "label":"Wikipe-tan head","rarity":"Uncommon","spawn_weight":30,
        "artwork_author":"Kasuga",
        "artwork_license_name":"CC BY-SA 3.0",
        "artwork_license_url":"https://creativecommons.org/licenses/by-sa/3.0/",
        "artwork_identity_verified":True,
        "reuse_rights_verified":True,
        "content_suitability_verified":True,
        "upstream_terms_verified":True,
        "telegram_photo_verified":True,
        "review_note":"Synthetic test reviewer checked all identity and license evidence fields.",
        "evidence":{f:"https://example.org/review-evidence/"+str(i)
                    for i,f in enumerate(REQUIRED_CHECKS)},
    }


class ReviewedVariantPipelineTests(unittest.TestCase):
    def test_prepared_variants_never_self_approve_or_fill_credits(self):
        result=prepare_queue(pending_imageinfo())
        self.assertEqual(result["pending_variant_artworks"],1)
        self.assertEqual(result["approved_artworks"],0)
        item=result["review_queue"][0]
        self.assertTrue(item["variant_key"].startswith("commons-"))
        self.assertIsNone(item["image_url"])
        self.assertIsNone(item["artwork_license_url"])
        self.assertTrue(all(v is None for v in item["evidence"].values()))
        self.assertFalse(item["artwork_identity_verified"])

    def test_stable_variant_key_across_metadata_license_changes(self):
        report=pending_imageinfo()
        one=prepare_queue(report)["review_queue"][0]["variant_key"]
        report["review_rows"][0]["artist_hint_unverified"]="Changed by someone else"
        self.assertEqual(prepare_queue(report)["review_queue"][0]["variant_key"],one)

    def test_unreviewed_and_rejected_input_outputs_no_variants(self):
        row=prepare_queue(pending_imageinfo())["review_queue"][0]
        self.assertEqual(assemble([row],[])["variants"],[])
        pending=reviewed(row)
        pending["status"]="pending"
        self.assertEqual(assemble([row],[pending])["approvals"],[])
        pending["status"]="rejected"
        self.assertEqual(assemble([row],[pending])["variants"],[])

    def test_only_exact_five_check_human_evidence_becomes_import_candidate(self):
        row=prepare_queue(pending_imageinfo())["review_queue"][0]
        accepted=reviewed(row)
        result=assemble([row],[accepted])
        self.assertEqual(result["summary"]["human_approved_variant_records"],1)
        self.assertEqual(result["summary"]["database_writes"],0)
        self.assertEqual(result["summary"]["images_downloaded"],0)
        self.assertEqual(len(result["approvals"]),1)
        self.assertEqual(len(importer_validate(result["variants"],result["approvals"])),1)
        self.assertEqual(result["variants"][0]["variant_key"],row["variant_key"])
        self.assertEqual(result["variants"][0]["artwork_author"],"Kasuga")
        self.assertNotIn("telegram_file_id",result["variants"][0])
        self.assertNotIn("photo_bytes",str(result))

    def test_reject_image_swap_license_substitution_and_wrong_file_identity(self):
        q=prepare_queue(pending_imageinfo())["review_queue"][0]
        for updates in (
            {"candidate_file_title":"File:Else.png"},
            {"image_url":"https://upload.wikimedia.org/malicious.jpg"},
            {"artwork_page_url":"https://commons.wikimedia.org/wiki/File:Unrelated.png"},
            {"artwork_license_url":"http://evil.test/by-sa"},
            {"artwork_license_name":""},
            {"artwork_author":None},
            {"status":"okay"},
        ):
            d=reviewed(q)
            d.update(updates)
            with self.subTest(updates=updates),self.assertRaises(ValueError):
                assemble([q],[d])

    def test_all_verification_flags_mandatory(self):
        q=prepare_queue(pending_imageinfo())["review_queue"][0]
        for flag in ("artwork_identity_verified","reuse_rights_verified",
                     "content_suitability_verified","upstream_terms_verified",
                     "telegram_photo_verified"):
            review=reviewed(q)
            review[flag]=False
            with self.subTest(flag=flag),self.assertRaises(ValueError):
                assemble([q],[review])

    def test_five_independent_review_evidence_urls_required(self):
        q=prepare_queue(pending_imageinfo())["review_queue"][0]
        for check in REQUIRED_CHECKS:
            decision=reviewed(q)
            decision["evidence"][check]=None
            with self.subTest(check=check),self.assertRaises(ValueError):
                assemble([q],[decision])

    def test_unknown_duplicate_or_unreviewed_rows_fail_closed(self):
        q=prepare_queue(pending_imageinfo())["review_queue"][0]
        d=reviewed(q)
        with self.assertRaises(ValueError):
            assemble([q,q],[d])
        with self.assertRaises(ValueError):
            assemble([q],[d,d])
        d["variant_key"]="commons-other"
        with self.assertRaises(ValueError):
            assemble([q],[d])
        bad=dict(q,approved_for_import=True)
        with self.assertRaises(ValueError):
            assemble([bad],[])

    def test_unsupported_or_untrusted_metadata_cannot_reach_worksheet(self):
        for change in ({"metadata_photo_candidate":False},
                       {"candidate_image_url":"http://127.0.0.1/a.jpg"},
                       {"file_page_url":"https://evil.example/page"}):
            r=pending_imageinfo()
            r["review_rows"][0].update(change)
            output=prepare_queue(r)
            self.assertEqual(output["pending_variant_artworks"],0)
            self.assertEqual(output["excluded_unsupported_metadata"],1)

    def test_refuse_different_category_source_and_oversized_report(self):
        r=pending_imageinfo()
        r["review_rows"][0]["claimed_character_source_key"]="commons:kiki:original"
        with self.assertRaises(ValueError):
            prepare_queue(r)
        r=pending_imageinfo()
        r["review_rows"]*=49
        with self.assertRaises(ValueError):
            prepare_queue(r)

    def test_demo_review_cli_does_not_use_db_or_network(self):
        from scripts import prepare_variant_review_queue as p
        from scripts import assemble_reviewed_variants as a
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            discovery=root/"metadata.json"
            worksheet=root/"worksheet.json"
            decisions=root/"decisions.json"
            variants=root/"ready.json"
            manifest=root/"proof.json"
            discovery.write_text(json.dumps(pending_imageinfo()),encoding="utf8")
            with patch("sys.argv",["review",str(discovery),str(worksheet)]):
                p.main()
            staged=json.loads(worksheet.read_text(encoding="utf8"))
            self.assertEqual(len(staged),1)
            decisions.write_text("[]",encoding="utf8")
            with patch("sys.argv",["review",str(worksheet),str(decisions),
                                   "--variants-out",str(variants),
                                   "--approvals-out",str(manifest)]):
                a.main()
            self.assertEqual(json.loads(variants.read_text(encoding="utf8")),[])
            self.assertEqual(json.loads(manifest.read_text(encoding="utf8")),[])


if __name__=="__main__":
    unittest.main()
