"""Specific real-provider URL candidates; offline-only no Telegram/DB calls."""
import copy
import json
import unittest

from scripts.audit_official_art_leads import PEPPER, COMMONS, audit


class OfficialArtworkLeadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=json.loads(PEPPER.read_text(encoding="utf8"))
        cls.c=json.loads(COMMONS.read_text(encoding="utf8"))

    def test_fifteen_distinct_real_named_original_webcomic_characters(self):
        result=audit(self.p,self.c)
        self.assertEqual(result["pending_distinct_official_characters"],15)
        self.assertEqual(result["pending_official_picture_urls"],15)
        self.assertEqual(result["rights_approved"],0)
        self.assertEqual(result["telegram_tested"],0)
        self.assertEqual(result["import_ready"],0)
        names={r["name"] for r in self.p["rows"]}
        self.assertIn("Pepper",names)
        self.assertIn("Coriander",names)
        self.assertIn("Carrot",names)
        self.assertIn("Torreya",names)

    def test_commons_six_individual_page_triage_does_not_mean_approved(self):
        out=audit(self.p,self.c)
        self.assertEqual(out["commons_reviewed_file_page_leads"],6)
        self.assertEqual(out["commons_on_hold_for_cross_ip_or_other_flags"],1)
        self.assertIn("Abstract Wikipe-tan.png",self.c["reviews"][0]["file_title"])

    def test_duplicate_identity_url_and_unapproved_import_paths_fail_closed(self):
        for mutation in ("duplicate","url","approved","media","spoof","telegram"):
            data=copy.deepcopy(self.p)
            row=data["rows"][0]
            if mutation=="duplicate":
                row["source_key"]=data["rows"][1]["source_key"]
            elif mutation=="url":
                row["candidate_image_url"]=data["rows"][1]["candidate_image_url"]
            elif mutation=="approved":
                row["approved_for_import"]=True
            elif mutation=="media":
                row["image_url"]=row["candidate_image_url"]
            elif mutation=="spoof":
                row["candidate_image_url"]="https://www.peppercarrot.com.evil.test/art.jpg"
            else:
                row["telegram_photo_verified"]=True
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                audit(data,self.c)

    def test_commons_triage_cannot_be_changed_to_released_or_unsafe_host(self):
        for field,value in (("approved_for_import",True),
                            ("artwork_identity_verified",True),
                            ("file_page_url","https://commons.wikimedia.org.bad.example/x")):
            c=copy.deepcopy(self.c)
            c["reviews"][0][field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                audit(self.p,c)

    def test_summary_and_all_metadata_have_zero_production_writes(self):
        self.assertEqual(self.p["db_writes"],0)
        self.assertTrue(all(x["image_url"] is None for x in self.p["rows"]))
        self.assertTrue(all(x["approved_for_import"] is False for x in self.p["rows"]))
        self.assertEqual(audit(self.p,self.c)["database_writes"],0)


if __name__=="__main__":
    unittest.main()
