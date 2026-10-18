import unittest
from scripts.anilist_export import parse_character

class AniListParsingTests(unittest.TestCase):
    def test_character_with_media(self):
        record={"id":42,"name":{"full":"Aster","alternative":["Aster Star"]},
                "image":{"large":"https://images.example.org/aster.png"},
                "media":{"nodes":[{"type":"MANGA","isAdult":False,"title":{"english":"Sky Story"}}]}}
        parsed=parse_character(record)
        self.assertEqual(parsed["source_key"],"anilist:character:42")
        self.assertEqual(parsed["category"],"manga")
        self.assertEqual(parsed["aliases"],["Aster Star"])
    def test_no_image_skipped(self):
        self.assertIsNone(parse_character({"id":42,"name":{"full":"Aster"},"image":{}}))
    def test_missing_series(self):
        x=parse_character({"id":9,"name":{"full":"B"},"image":{"large":"https://example.org/b.png"}})
        self.assertEqual(x["series"],"Unknown Series")

if __name__=="__main__":
    unittest.main()
