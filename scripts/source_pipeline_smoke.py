"""Offline smoke for the cross-source -> identity -> artwork review chain.

Uses ONLY synthetic in-memory rows, makes no API/DB/Telegram calls, and is
safe for GitHub Actions. Checks the stages never silently approve any image.
"""
import json
from scripts.bangumi_review import review_characters
from scripts.flatten_bangumi_pilot import flatten
from scripts.source_identity_review import inspect_sources, apply_human_decisions
from scripts.artwork_candidate_checklist import make_checklist


def smoke():
    known={"source_key":"local:alice","name":"Alice",
           "series":"Wonderland Adventure","image_url":None}
    bangumi_subject={"id":1,"name":"Wonderland Adventure","nsfw":False}
    b_rows=review_characters(1,bangumi_subject,[{"id":11,"name":"Alice"}])
    b_report={"source":"Bangumi public API v0",
              "subjects":[{"subject_id":1,"eligible":True,
                           "status":"metadata_review_only","characters":b_rows}]}
    staged=flatten(b_report)["staged"]
    identity=inspect_sources({"local":[known],"bangumi":staged})
    decisions=apply_human_decisions(identity,[])
    commons={
        "source_key":"local:alice","character_name":"Alice",
        "series":"Wonderland Adventure",
        "candidate_image_url":"https://upload.wikimedia.org/wikipedia/commons/a/a0/Example.png",
        "file_page_url":"https://commons.wikimedia.org/wiki/File:Example.png",
        "license_hint":"CC0",
        "approved_for_import":False,
    }
    review=make_checklist([commons])
    if (len(identity["candidate_pairs"])!=1 or decisions["human_reviewed_same_pairs"]!=0
        or review["approved_artworks"]!=0 or review["import_ready_characters"]!=0
        or review["review_queue"][0]["approved_for_import"]):
        raise RuntimeError("Unsafe source metadata -> artwork approval pipeline")
    return {"mode":"synthetic_offline_integration",
            "staged_bangumi_characters":len(staged),
            "unverified_cross_source_pairs":len(identity["candidate_pairs"]),
            "human_identity_matches":0,
            "commons_review_candidates":review["review_queue_count"],
            "rights_approved_artworks":0,
            "import_ready_characters":0,
            "production_writes":0,
            "external_requests":0}


if __name__=="__main__":
    print(json.dumps(smoke(),indent=2))
