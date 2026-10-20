"""Reviewed source/art catalog bridge never promotes API hints by itself."""
import copy
import unittest

from scripts.build_reviewed_catalog import assemble, REQUIRED_CHECKS
from scripts.import_characters import validate
from scripts.artwork_approval import require_artwork_approval


def meta(key="bangumi:character:500"):
    return {"source_key":key,"name":"Example Hero","series":"Safe Show",
            "aliases":["Hero"],"category":"anime","rarity":"Uncommon",
            "weight":50,"image_url":None,
            "metadata_status":"pending_upstream_terms_review"}


def reviewed(key="bangumi:character:500"):
    return {
        "source_key":key,"status":"approved",
        "image_url":"https://upload.wikimedia.org/wikipedia/commons/a/a0/reviewed.jpg",
        "evidence":{k:f"https://commons.wikimedia.org/wiki/File:{k}.jpg"
                    for k in REQUIRED_CHECKS},
        "review_note":"Human verified source and character mapping with reuse permission."
    }


class CatalogBridgeTests(unittest.TestCase):
    def test_no_manual_approval_means_no_catalog_even_when_source_has_image_hint(self):
        row=meta()
        row["image_url"]="https://unapproved.example/art.jpg"
        result=assemble([row],[])
        self.assertEqual(result["catalog"],[])
        self.assertEqual(result["approvals"],[])
        self.assertEqual(result["summary"]["human_reviewed_approved"],0)
        self.assertEqual(result["summary"]["database_writes"],0)

    def test_manual_record_creates_only_shared_url_metadata(self):
        catalog=assemble([meta()],[reviewed()])
        entry=catalog["catalog"][0]
        approval=catalog["approvals"][0]
        self.assertEqual(entry["source_key"],"bangumi:character:500")
        self.assertEqual(entry["image_url"],reviewed()["image_url"])
        self.assertNotIn("telegram_file_id",entry)
        self.assertNotIn("owner_id",entry)
        self.assertEqual(len(validate(catalog["catalog"])),1)
        self.assertEqual(require_artwork_approval(catalog["catalog"],catalog["approvals"]),1)
        self.assertEqual(approval["status"],"approved")
        self.assertEqual(set(approval["verification_evidence"]),set(REQUIRED_CHECKS))
        self.assertEqual(catalog["summary"]["image_files_saved"],0)

    def test_source_metadata_does_not_override_reviewed_art(self):
        row=meta()
        row["image_url"]="https://evil.example/pic.jpg"
        result=assemble([row],[reviewed()])
        self.assertNotIn("evil.example",str(result))

    def test_missing_any_evidence_refuses_approval(self):
        for label in REQUIRED_CHECKS:
            row=reviewed()
            del row["evidence"][label]
            with self.subTest(label=label),self.assertRaises(ValueError):
                assemble([meta()],[row])

    def test_review_checks_must_be_individual_public_https_references(self):
        for change in (
            "http://example.org/not-secure",
            "https://admin:password@commons.wikimedia.org/",
            "https://commons.wikimedia.org:4242/",
            "/local-review",
        ):
            row=reviewed()
            row["evidence"]["subject_identity"]=change
            with self.subTest(change=change),self.assertRaises(ValueError):
                assemble([meta()],[row])

    def test_short_notes_and_missing_image_are_rejected(self):
        for field,value in (("review_note","okay"),
                            ("image_url",None),
                            ("status","not_reviewed")):
            row=reviewed()
            row[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                assemble([meta()],[row])

    def test_rejected_and_pending_skipped_without_autoimport(self):
        rows=[meta("bangumi:character:1"),meta("bangumi:character:2"),meta("bangumi:character:3")]
        a=reviewed("bangumi:character:1")
        b=reviewed("bangumi:character:2")
        b["status"]="rejected"
        result=assemble(rows,[a,b])
        self.assertEqual(result["summary"]["metadata_rows"],3)
        self.assertEqual(result["summary"]["human_reviewed_approved"],1)
        self.assertEqual(result["summary"]["pending_or_rejected"],2)

    def test_duplicate_staged_or_unknown_approval_is_refused(self):
        with self.assertRaises(ValueError):
            assemble([meta(),meta()],[reviewed()])
        with self.assertRaises(ValueError):
            assemble([meta()],[reviewed("bangumi:character:does-not-exist")])
        with self.assertRaises(ValueError):
            assemble([meta()],[reviewed(),reviewed()])

    def test_no_mutation_or_media_download(self):
        data=[meta()]
        manual=[reviewed()]
        original_data=copy.deepcopy(data)
        original_manual=copy.deepcopy(manual)
        assemble(data,manual)
        self.assertEqual(data,original_data)
        self.assertEqual(manual,original_manual)


if __name__=="__main__":
    unittest.main()
