# Changing a Published Course Site URL

The normal Studio api rejects `url_path` changes for published sites (enforced in `WebsiteUrlSerializer.validate_url_path`), so this process requires direct DB edits and manual steps.

> **Note:** If you encounter issues not covered below or discover that a step's instructions are incomplete or incorrect, please update this document so future engineers benefit from the experience.

## Step 1 - Change `url_path` in Django Admin

Update the Website object's **url_path** field to the new value (e.g. `courses/res-100-presenting-your-work`).

## Step 2 — Reset Sync States and Sync to Backend

Reset all `ContentSyncState` checksums for the site and re-sync to GitHub.

```bash
./manage.py reset_sync_states --filter <site-name> --skip_sync
./manage.py sync_website_to_backend --filter <site-name>
```

## Step 3 — Update the Site's Concourse Pipeline

Re-upsert the site pipeline so Concourse picks up the new url paths on which to build the site

```bash
./manage.py backpopulate_pipelines --filter <site-name>
```

## Step 4 — Update Mass Build Pipelines

The mass build pipeline embeds `url_path` values at upsert time. Regenerate both variants:

```bash
./manage.py upsert_mass_build_pipeline
./manage.py upsert_mass_build_pipeline --offline
```

## Step 5 — Publish from the Studio UI

Trigger a live and draft publish from the Studio publish drawer.

Monitor the Concourse builds until they shows `succeeded`.

## Step 6 — Handle Cross-Site References

The course may be referred to by other sites, particularly by ocw-www in course lists and resource collections.

These references may need to be analyzed individually and fixed on a case-to-case basis. To compile a list of such references, the following snippet can be helpful.

```python
from django.db.models import Q
from websites.constants import *
from websites.models import *
wc = WebsiteContent.objects.filter(
    Q(metadata__icontains=<old_url_path>)|Q(markdown__icontains=<old_url_path>)
)

```

## Step 7 — Add a Redirect from the Old URL

Redirect the old url to the new one

## Step 8 — Search Indexes

Search on [ocw.mit.edu](https://ocw.mit.edu/search) — results should point to the new URL.

This may take some time, depending on whenever the indexing in open-discussions/learn happens.

## Step 9 — Remove Old Content from S3

> **Cleanup step only.** This step is a nice to have and carries no urgency. Only proceed once you are fully satisfied that the new URL is working correctly, the redirect is in place, and all cross-site references have been resolved. There is no harm in leaving the old content in S3 temporarily while you verify everything.

Only do this once you are confident the entire migration was successful.

```bash
aws s3 rm s3://<AWS_PUBLISH_BUCKET_NAME>/courses/<old-slug>/ --recursive
aws s3 rm s3://<AWS_DRAFT_PUBLISH_BUCKET_NAME>/courses/<old-slug>/ --recursive

aws s3 rm s3://<AWS_OFFLINE_PUBLISH_BUCKET_NAME>/courses/<old-slug>/ --recursive
aws s3 rm s3://<AWS_OFFLINE_DRAFT_PUBLISH_BUCKET_NAME>/courses/<old-slug>/ --recursive

```
