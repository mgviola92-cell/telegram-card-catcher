import unittest
from scripts.anilist_export import parse_character

def character(adult):
    return {'id':123,'name':{'full':'Example Character','alternative':[]},
            'image':{'large':'https://example.org/character.jpg'},
            'media':{'nodes':[{'title':{'english':'Example Series'},
                               'type':'ANIME','isAdult':adult}]}}

class AniListGeneralAudienceTests(unittest.TestCase):
    def test_nonadult_metadata_can_be_reviewed(self):
        record=parse_character(character(False))
        self.assertEqual(record['source_key'],'anilist:character:123')
        self.assertEqual(record['series'],'Example Series')

    def test_adult_media_excluded(self):
        self.assertIsNone(parse_character(character(True)))

    def test_unknown_media_classification_excluded(self):
        self.assertIsNone(parse_character(character(None)))
