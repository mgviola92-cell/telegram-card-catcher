"""Safe importer CLI and internal API: no write without exact artwork review."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from scripts.import_characters import (
    CONFIRM_PHRASE, QUERY, import_batch, main, validate, safe_image_url,
)
from scripts.artwork_approval import require_artwork_approval


def item(key="fixture:hero-1", image="https://upload.wikimedia.org/example.jpg",
         **overrides):
    row={"source_key":key,"name":"Example Hero","series":"Original Show",
         "category":"other","rarity":"Common","aliases":["Hero"],
         "image_url":image,"weight":100}
    row.update(overrides)
    return row


def approval(row):
    return {"source_key":row["source_key"],
            "image_url":row["image_url"],"status":"approved",
            "permission_reference":"https://commons.wikimedia.org/wiki/File:Reviewed_Art.jpg"}


class SafeImportTests(unittest.TestCase):
    def test_all_external_url_risks_fail_preflight(self):
        for url in (
            "http://example.org/one.jpg",
            "https://127.0.0.1/file.jpg",
            "https://[::1]/file.jpg",
            "https://localhost/file.jpg",
            "https://a.localhost/file.jpg",
            "https://user:secret@host.example/one.jpg",
            "https://host.example:444/one.jpg",
            "https://host.example:bad/one.jpg",
            "file:///tmp/one.jpg",
        ):
            with self.subTest(url=url):
                self.assertFalse(safe_image_url(url))
                with self.assertRaises(ValueError):
                    validate([item(image=url)])
        self.assertTrue(safe_image_url("https://upload.wikimedia.org/portrait.jpg"))

    def test_bad_catalog_batch_is_rejected_before_connect(self):
        for rows in (
            [item(),item()],
            [item(key="bad key")],
            [item(key="fixture:ok",weight=True)],
            [item(key="fixture:ok",aliases=[""])],
        ):
            with self.subTest(rows=rows),patch("scripts.import_characters.connect") as db:
                with self.assertRaises(ValueError):
                    import_batch(rows,[])
                db.assert_not_called()

    def test_rights_missing_wrong_url_or_duplication_rejected_before_db_open(self):
        a=item()
        bad=[[],[dict(approval(a),image_url="https://example.org/other.jpg")],
             [dict(approval(a),status="pending")],
             [approval(a),approval(a)]]
        for manifest in bad:
            with self.subTest(manifest=manifest),patch("scripts.import_characters.connect") as db:
                with self.assertRaises(ValueError):
                    import_batch([a],manifest)
                db.assert_not_called()

    def test_exact_manifest_and_batch_size_checked_before_db(self):
        rows=[item(key=f"fixture:{x}") for x in range(5)]
        with patch("scripts.import_characters.connect") as conn:
            with self.assertRaises(ValueError):
                import_batch(rows,[approval(x) for x in rows],batch_size=0)
            conn.assert_not_called()

    def test_rights_gate_does_not_actually_download_images(self):
        a=item()
        self.assertEqual(require_artwork_approval([a],[approval(a)]),1)
        self.assertEqual(validate([a])[0][6],a["image_url"])

    def test_approved_multi_batch_is_one_transaction_and_preserves_cache_on_unchanged_url(self):
        rows=[item(key=f"fixture:{x}") for x in range(7)]
        db=MagicMock()
        ctx=MagicMock()
        cursor=MagicMock()
        ctx.__enter__.return_value=db
        db.cursor.return_value.__enter__.return_value=cursor
        with patch("scripts.import_characters.connect",return_value=ctx) as connected:
            written=import_batch(rows,[approval(x) for x in rows],batch_size=3)
        self.assertEqual(written,7)
        connected.assert_called_once()
        self.assertEqual(cursor.executemany.call_count,3)
        self.assertEqual([len(call.args[1]) for call in cursor.executemany.call_args_list],
                         [3,3,1])
        self.assertIn("telegram_file_id=CASE",QUERY)
        self.assertIn("IS DISTINCT FROM EXCLUDED.image_url",QUERY)

    def test_cli_default_never_writes_even_with_review_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            cat=Path(tmp)/"catalog.json"
            approved=Path(tmp)/"approved.json"
            a=item()
            cat.write_text(json.dumps([a]),encoding="utf8")
            approved.write_text(json.dumps([approval(a)]),encoding="utf8")
            with patch("sys.argv",["program",str(cat),"--approval-manifest",str(approved)]):
                with patch("scripts.import_characters.connect") as db:
                    self.assertEqual(main(),0)
                    db.assert_not_called()

    def test_cli_apply_denies_missing_rights_and_exact_confirm(self):
        with tempfile.TemporaryDirectory() as tmp:
            cat=Path(tmp)/"catalog.json"
            appr=Path(tmp)/"approved.json"
            a=item()
            cat.write_text(json.dumps([a]),encoding="utf8")
            appr.write_text(json.dumps([approval(a)]),encoding="utf8")
            for extras in (
                ["--apply"],
                ["--apply","--approval-manifest",str(appr)],
                ["--apply","--approval-manifest",str(appr),"--rights-reviewed"],
                ["--apply","--rights-reviewed","--confirm-database-write",CONFIRM_PHRASE],
            ):
                with self.subTest(extras=extras),patch("sys.argv",["program",str(cat),*extras]):
                    with patch("scripts.import_characters.connect") as db:
                        with self.assertRaises(SystemExit):
                            main()
                        db.assert_not_called()

    def test_cli_apply_requires_all_gates_then_writes_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            cat=Path(tmp)/"catalog.json"
            appr=Path(tmp)/"approved.json"
            a=item()
            cat.write_text(json.dumps([a]),encoding="utf8")
            appr.write_text(json.dumps([approval(a)]),encoding="utf8")
            args=["program",str(cat),"--apply","--approval-manifest",str(appr),
                  "--rights-reviewed","--confirm-database-write",CONFIRM_PHRASE]
            with patch("sys.argv",args),patch("scripts.import_characters.import_batch",return_value=1) as imp:
                self.assertEqual(main(),0)
                imp.assert_called_once()


if __name__=="__main__":
    unittest.main()
