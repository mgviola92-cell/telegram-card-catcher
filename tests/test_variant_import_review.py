"""Variant importer approval gates and single-batch SQL safety."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock,patch

from scripts import import_variants


def row(source="review:character-one", key="alt-one"):
    return {"character_source_key":source,"variant_key":key,
            "label":"Alternate fan-art (licensed)","rarity":"Rare",
            "image_url":"https://upload.wikimedia.org/wiki/shared-variant.jpg",
            "spawn_weight":60}


def proof(item=None):
    entry=item or row()
    return {"character_source_key":entry["character_source_key"],
            "variant_key":entry["variant_key"],
            "image_url":entry["image_url"],"status":"approved",
            "artwork_identity_verified":True,"reuse_rights_verified":True,
            "content_suitability_verified":True,"upstream_terms_verified":True,
            "permission_reference":"https://commons.wikimedia.org/wiki/File:Reviewed_Artwork.jpg",
            "review_note":"Human reviewed exact character image and source rights."}


class VariantImporterTests(unittest.TestCase):
    def test_one_exact_approved_variant_is_metadata_only(self):
        rows=import_variants.validate([row()],[proof()])
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0][0],"review:character-one")
        self.assertEqual(rows[0][3],row()["image_url"])
        self.assertNotIn("telegram_file_id",row())
        self.assertNotIn("image_bytes",row())

    def test_cannot_promote_unapproved_and_misidentified_art(self):
        for change in ({"status":"pending"},{"image_url":"https://example.org/other.jpg"},
                       {"artwork_identity_verified":False},
                       {"reuse_rights_verified":False},
                       {"content_suitability_verified":False},
                       {"upstream_terms_verified":False},
                       {"permission_reference":"not-evidence"},
                       {"review_note":"ok"}):
            val=proof()
            val.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                import_variants.validate([row()],[val])

    def test_reject_malformed_or_untrusted_url(self):
        for url in ("http://example.org/img.jpg","https://127.0.0.1/x.jpg",
                    "https://localhost/x.jpg","https://evil:password@example.org/x.jpg",
                    "https://cdn.example.org:8080/img.jpg","file:///data/photo.png",
                    "https://cdn.example.org/photo.jpg#anchor"):
            value=row()
            value["image_url"]=url
            with self.subTest(url=url),self.assertRaises(ValueError):
                import_variants.validate([value],[proof(value)])

    def test_reject_duplicates_and_bad_rarity_or_weight(self):
        base=row()
        for data in ([base,base],
                     [dict(base,spawn_weight=True)],
                     [dict(base,spawn_weight=-1)],
                     [dict(base,rarity="God")]):
            with self.subTest(data=data),self.assertRaises(ValueError):
                import_variants.validate(data,[proof(base)])

    def test_default_cli_never_opens_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/"variants.json",Path(tmp)/"permission.json"
            a.write_text(json.dumps([row()]),encoding="utf8")
            b.write_text(json.dumps([proof()]),encoding="utf8")
            with patch("sys.argv",["main",str(a),"--approval-manifest",str(b)]):
                with patch("scripts.import_variants.connect") as db:
                    self.assertEqual(import_variants.main(),0)
                    db.assert_not_called()

    def test_apply_requires_both_rights_and_exact_confirmation(self):
        with tempfile.TemporaryDirectory() as tmp:
            a,b=Path(tmp)/"variants.json",Path(tmp)/"permission.json"
            a.write_text(json.dumps([row()]),encoding="utf8")
            b.write_text(json.dumps([proof()]),encoding="utf8")
            for flags in (["--apply"],["--apply","--rights-reviewed"],
                          ["--apply","--confirm",import_variants.CONFIRM]):
                with self.subTest(flags=flags),patch("sys.argv",
                    ["main",str(a),"--approval-manifest",str(b),*flags]):
                    with patch("scripts.import_variants.connect") as db:
                        with self.assertRaises(SystemExit):
                            import_variants.main()
                        db.assert_not_called()

    def test_upsert_atomic_and_invalidates_only_changed_image(self):
        db=MagicMock()
        db.execute.return_value.fetchone.return_value={"id":47}
        with patch("scripts.import_variants.connect") as connected:
            connected.return_value.__enter__.return_value=db
            self.assertEqual(import_variants.apply([row()],[proof()]),1)
        sql,args=db.execute.call_args_list[-1].args
        self.assertIn("telegram_file_id=CASE",sql)
        self.assertIn("IS DISTINCT FROM EXCLUDED.image_url",sql)
        self.assertIn("enabled=true",sql)
        self.assertEqual(args,(47,"alt-one","Alternate fan-art (licensed)",
                               row()["image_url"],"Rare",60))

    def test_unknown_character_aborts_transaction(self):
        db=MagicMock()
        db.execute.return_value.fetchone.return_value=None
        with patch("scripts.import_variants.connect") as connected:
            connected.return_value.__enter__.return_value=db
            with self.assertRaises(ValueError):
                import_variants.apply([row()],[proof()])
        self.assertEqual(db.execute.call_count,1)


if __name__=="__main__":
    unittest.main()
