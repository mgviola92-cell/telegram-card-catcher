# Bulk artwork source-ID join — development only

Stage up to 500,000 character identifiers as normalized JSONL with
scripts/bulk_metadata_stage.py; then supply locally authorized provider
artwork metadata as a separate JSONL file with exact source_key values,
candidate_image_url and approved_for_import=false.

scripts/bulk_artwork_match.py performs bounded offline SQLite indexed
source ID joins. The operator must explicitly give allowable *exact*
hostnames via --allowed-host. Different source IDs with the same character
name are never automatically merged. Duplicate images are skipped and up
to 12 distinct image leads per character are retained.

Output is a PENDING local JSONL review queue, not a production import.
All candidate art URLs and credit hints require a verified author/source
license, cross-franchise rights review, age suitability, image content
identity, plus actual Telegram sendPhoto; all flags remain false.
No image binaries stored in Neon/Render; temporary SQLite stores metadata
only and is deleted on exit. Ownership schema unchanged.
