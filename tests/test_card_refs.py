"""Short public numeric card IDs: no schema migration or image storage."""
import unittest

from app.card_refs import MAX_BIGINT, parse_card_ref, public_card_id


class NumericCardReferenceTests(unittest.TestCase):
    def test_numeric_public_card_ids(self):
        self.assertEqual(parse_card_ref("6103"), ("id", 6103))
        self.assertEqual(parse_card_ref(6103), ("id", 6103))
        self.assertEqual(parse_card_ref("0006103"), ("id", 6103))
        self.assertEqual(parse_card_ref(str(MAX_BIGINT)), ("id", MAX_BIGINT))

    def test_legacy_cards_remain_lookuppable(self):
        self.assertEqual(parse_card_ref("40qbiwxi8p"), ("legacy_code", "40QBIWXI8P"))
        self.assertEqual(parse_card_ref("ABC123"), ("legacy_code", "ABC123"))

    def test_bad_references_are_rejected(self):
        for value in (None, "", "  ", 0, -1, True, 1.5, "6103; DROP TABLE",
                      str(MAX_BIGINT + 1), "x" * 33, "1 2", "-5", "၁၂၃"):
            with self.subTest(value=value):
                self.assertIsNone(parse_card_ref(value))

    def test_db_identity_is_visible_not_legacy_random_string(self):
        row = {"card_id": 6103, "code": "40QBIWXI8P"}
        self.assertEqual(public_card_id(row), "6103")
        self.assertEqual(public_card_id({"code": "40QBIWXI8P"}), "40QBIWXI8P")


if __name__ == "__main__":
    unittest.main()
