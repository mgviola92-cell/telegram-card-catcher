"""Conservative *scenario* calculator for catalog and owned-card storage.

Not a replacement for measuring PostgreSQL pg_total_relation_size after imports.
Does not connect to or modify Neon.
"""
import argparse
import json

def estimate(characters, cards, character_bytes=2048, card_bytes=512,
             baseline_bytes=8_200_192, storage_limit_bytes=1_073_741_824):
    for value in (characters,cards,character_bytes,card_bytes,baseline_bytes,storage_limit_bytes):
        if type(value) is not int or value<0:
            raise ValueError("Nonnegative integer values required")
    projected=baseline_bytes+characters*character_bytes+cards*card_bytes
    return {'characters':characters,'owned_cards':cards,
            'assumed_character_bytes_including_indexes':character_bytes,
            'assumed_card_bytes_including_indexes':card_bytes,
            'estimated_total_bytes':projected,'storage_limit_bytes':storage_limit_bytes,
            'estimated_fraction_of_limit':round(projected/storage_limit_bytes,4) if storage_limit_bytes else None,
            'warning':'Planning assumption, not measured row size; indexes, vacuum bloat, transfer logs and variants can increase actual usage.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--characters',type=int,default=100000)
    parser.add_argument('--owned-cards',type=int,default=1000000)
    args=parser.parse_args()
    print(json.dumps(estimate(args.characters,args.owned_cards),indent=2))
