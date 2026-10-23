# Input a SINGLE official DATASET URL with 100,000+ character artwork URLs

A single dataset URL can include 100k+ external \`image_url\` fields inside
JSONL rows. The importer must not request each image, upload individual
pictures or store image bytes. The source license applies only when it
genuinely grants redistribution/reuse for all included images and correct
per-image author credit. A random ACDB/booru URL list does not pass this gate.

Use the operator-only script (no production Render scheduling):

python -m scripts.bulk_url_dataset \
  --dataset-url https://trusted-creator-source.example/catalog/100k.jsonl.gz \
  --dataset-host trusted-creator-source.example \
  --source-grant /tmp/independently_reviewed_full_dataset_grant.json

The example URL is a placeholder, NOT a real licensed catalog. It shows
the required contract. The dataset provider hostname is exact, must use
HTTPS, no redirects or raw IPs, maximum metadata-only response 250MiB.
It is placed temporarily on the operator's machine, then removed.
The exact dataset SHA256 must match its separately approved grant.

After explicit owner authorization, independent full-batch rights review,
free-space check and Telegram photo test, the same command can take
\`--apply --rights-reviewed --confirm IMPORT_REVIEWED_BULK_URLS\`
plus \`CARDKOUT_BULK_IMPORT_AUTHORIZED=YES\`, to stream the metadata into
a disposable SQLite key index and then PostgreSQL COPY/upsert. New images
default disabled until source-wide Telegram photo compatibility confirmed;
add \`--enable\` only when the grant documents such testing.

No image binaries are stored on Neon, Render or the repo. No real
100,000-image legally licensed named-anime source has been obtained:
the pipeline capability alone does not create rights.
