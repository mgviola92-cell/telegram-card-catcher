"""Offline Commons artwork review checklists never imply photo approvals."""
import unittest
from scripts.artwork_candidate_checklist import make_checklist, checked_https


def candidate(**kwargs):
    row={
        "source_key":"mal:character:1",
        "character_name":"Example Hero",
        "series":"Example Show",
        "candidate_image_url":"https://upload.wikimedia.org/wikipedia/commons/a/a0/hero.png",
        "file_page_url":"https://commons.wikimedia.org/wiki/File:Example_Hero.png",
        "license_hint":"CC BY-SA 4.0",
        "artist_hint":"Sample Creator",
        "approved_for_import":False,
    }
    row.update(kwargs)
    return row


class ArtworkReviewChecklistTests(unittest.TestCase):
    def test_hints_and_valid_links_do_not_approve_media(self):
        result=make_checklist([candidate()])
        self.assertEqual(result["review_queue_count"],1)
        self.assertEqual(result["approved_artworks"],0)
        self.assertEqual(result["import_ready_characters"],0)
        row=result["review_queue"][0]
        self.assertFalse(row["approved_for_import"])
        self.assertFalse(row["image_rights_approved"])
        self.assertIsNone(row.get("permission_reference"))
        self.assertNotIn("image_url",row)
        self.assertEqual(row["license_hint_unverified"],"CC BY-SA 4.0")
        self.assertEqual(len(row["required_checks"]),5)
        self.assertTrue(all(x=="pending" for x in row["required_checks"].values()))

    def test_repeated_candidates_are_deduplicated_only_within_same_character(self):
        r=make_checklist([candidate(),candidate(),
                          candidate(source_key="mal:character:2")])
        self.assertEqual(r["review_queue_count"],2)
        self.assertEqual(r["counters"]["repeated_candidate_image_for_character"],1)

    def test_untrusted_url_and_credentials_rejected_without_requests(self):
        wrong=[
            candidate(candidate_image_url="http://upload.wikimedia.org/photo.jpg"),
            candidate(candidate_image_url="https://127.0.0.1/photo.jpg"),
            candidate(candidate_image_url="https://upload.wikimedia.org.attacker.com/x.png"),
            candidate(candidate_image_url="https://user:pwd@upload.wikimedia.org/a.jpg"),
            candidate(file_page_url="https://attacker.test/fake-license"),
            candidate(file_page_url="https://commons.wikimedia.org:999/page"),
        ]
        result=make_checklist(wrong)
        self.assertEqual(result["review_queue_count"],0)
        self.assertEqual(result["counters"]["untrusted_media_provenance"],6)

    def test_limit_and_input_bounds(self):
        rows=[candidate(source_key=f"stage:{i}") for i in range(8)]
        result=make_checklist(rows,limit=3)
        self.assertEqual(result["review_queue_count"],3)
        self.assertEqual(result["counters"]["beyond_output_limit"],5)
        with self.assertRaises(ValueError):
            make_checklist(rows,limit=0)
        with self.assertRaises(ValueError):
            make_checklist(rows*700)

    def test_untrusted_string_metadata_cannot_enable_import(self):
        value=candidate(approved_for_import=True,
                        image_rights_approved=True,
                        permission_reference="https://commons.wikimedia.org/wiki/File:Example_Hero.png",
                        license_hint="Public Domain",
                        artist_hint="<script>fake</script>")
        result=make_checklist([value])
        row=result["review_queue"][0]
        self.assertFalse(row["approved_for_import"])
        self.assertFalse(row["image_rights_approved"])
        self.assertNotIn("permission_reference",row)
        self.assertIn("pending",row["required_checks"].values())

    def test_no_invalid_fragments_allowed(self):
        self.assertFalse(checked_https(
            "https://commons.wikimedia.org/wiki/File:x.png#anchor",
            "commons.wikimedia.org"))
        self.assertTrue(checked_https("https://commons.wikimedia.org/wiki/File:x.png",
                                     "commons.wikimedia.org"))


if __name__=="__main__":
    unittest.main()
