"""Verifies pinned source tree artwork references, not image rights or Telegram."""
import json
from pathlib import Path
import unittest
from scripts.wesnoth_source_inventory import audit, export_review_leads

FILE=Path("data/wesnoth_1_16_11_official_art_inventory.json")


class WesnothSourceInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=json.loads(FILE.read_text(encoding="utf8"))

    def test_upstream_git_artwork_batch_is_real_and_named_correctly(self):
        summary=audit(self.catalog)
        self.assertEqual(summary["total_source_pngs"],442)
        self.assertEqual(summary["campaign_portraits"],204)
        self.assertEqual(summary["unit_type_portraits"],238)
        self.assertEqual(summary["live_catalog_characters_added"],0)
        self.assertEqual(summary["image_files_downloaded"],0)
        self.assertEqual(summary["database_writes"],0)

    def test_every_asset_uses_provenance_pinned_commit_and_pending_rights(self):
        for row in self.catalog["files"]:
            self.assertTrue(row["candidate_image_url"].startswith(
                "https://raw.githubusercontent.com/wesnoth/wesnoth/"
                "83d4b397f1de466c721e4e393b361c71fc4f5b6c/data/"))
            self.assertFalse(row["approved_for_import"])
            self.assertFalse(row["specific_artwork_license_confirmed"])
            self.assertFalse(row["character_identity_verified"])
            self.assertFalse(row["telegram_send_photo_verified"])
            self.assertNotIn("blob",row)
            self.assertNotIn("image_bytes",row)
            self.assertTrue(row["source_git_blob_sha"])

    def test_review_export_retains_full_real_url_and_zero_approvals(self):
        review=export_review_leads(self.catalog,limit=442)
        self.assertEqual(len(review),442)
        self.assertTrue(all(r["status"]=="pending" for r in review))
        self.assertTrue(all(r["image_url"] is None for r in review))
        self.assertTrue(all(r["approved_for_import"] is False for r in review))
        self.assertTrue(all(r["candidate_image_url"].endswith(".png") for r in review))
        self.assertEqual(len({r["source_file"] for r in review}),442)

    def test_reject_tampered_unknown_repo_non_png_or_duplicate(self):
        import copy
        for badfield, value in (
            ("candidate_image_url","https://evil.invalid/p.png"),
            ("source_file","../secret.png"),
            ("specific_artwork_license_confirmed",True),
            ("approved_for_import",True),
        ):
            with self.subTest(field=badfield):
                bad=copy.deepcopy(self.catalog)
                bad["files"][0][badfield]=value
                with self.assertRaises(ValueError):
                    audit(bad)
        bad=copy.deepcopy(self.catalog)
        bad["files"].append(bad["files"][0])
        with self.assertRaises(ValueError):
            audit(bad)


if __name__=="__main__":
    unittest.main()
