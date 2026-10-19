"""Normalize provider subject links without merging by names or copying images."""
import unittest
from scripts.flatten_bangumi_pilot import flatten


def card(key="bangumi:character:41",name="Safe Character",series="Family Series"):
    return {"source_key":key,"name":name,"series":series,"image_url":None,
            "telegram_file_id":None,"import_ready":False}


def response(groups):
    return {"source":"Bangumi public API v0","subjects":groups}


def group(sid,characters,eligible=True):
    return {"subject_id":sid,"status":"metadata_review_only" if eligible
            else "not_eligible_or_unverified","eligible":eligible,
            "characters":characters}


class FlattenBangumiTests(unittest.TestCase):
    def test_same_character_in_two_subjects_is_one_staged_identity(self):
        data=response([group(1,[card()]),group(2,[card(series="Other Show")])])
        result=flatten(data)
        self.assertEqual(result["staged_unique_source_characters"],1)
        self.assertEqual(result["extra_subject_links"],1)
        self.assertEqual(result["staged"][0]["series"],"Family Series")
        self.assertEqual(result["staged"][0]["additional_series"],["Other Show"])
        self.assertFalse(result["staged"][0]["import_ready"])
        self.assertIsNone(result["staged"][0]["image_url"])
        self.assertEqual(result["artworks_approved"],0)

    def test_identical_name_with_distinct_ids_are_distinct(self):
        data=response([group(1,[card(key="bangumi:character:41"),
                                  card(key="bangumi:character:43")])])
        self.assertEqual(flatten(data)["staged_unique_source_characters"],2)

    def test_invalid_age_group_with_records_is_not_accepted(self):
        data=response([group(1,[card()],eligible=False)])
        with self.assertRaises(ValueError):
            flatten(data)

    def test_provider_approved_image_claims_are_not_trusted(self):
        for change in ({"image_url":"https://thirdparty.example/img.png"},
                       {"telegram_file_id":"abc"},
                       {"import_ready":True}):
            meta=card()
            meta.update(change)
            with self.subTest(change=change),self.assertRaises(ValueError):
                flatten(response([group(1,[meta])]))

    def test_conflicting_names_for_same_source_id_fail(self):
        data=response([group(1,[card()]),group(2,[card(name="Different Person")])])
        with self.assertRaises(ValueError):
            flatten(data)

    def test_unknown_source_and_overlimit_denied(self):
        with self.assertRaises(ValueError):
            flatten({"source":"unexpected","subjects":[]})
        with self.assertRaises(ValueError):
            flatten(response([group(i,[]) for i in range(6)]))


if __name__=="__main__":
    unittest.main()
