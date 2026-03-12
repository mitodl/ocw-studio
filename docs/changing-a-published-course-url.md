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

Publish live, and draft sites from the Studio publish drawer.

Monitor the Concourse builds until they show `succeeded`.

## Step 6 — Add a Redirect from the Old URL

Redirect the old url to the new one. See [this PR](https://github.com/mitodl/ol-infrastructure/pull/4257) as an example of how to add a redirect.

## Step 7 — Handle Cross-Site References

The course may be referenced by other sites — most commonly by ocw-www in course lists and course collections. The redirect will handle any such links that may appear on ocw, but subsequent hugo builds of ocw-www
may fail if they encounter the old URL in course lists or collections.

Hence, we should update any such references to the new URL.

To find affected `WebsiteContent` objects, use the following snippet:

```python
from websites.constants import *
from websites.models import *

www = Website.objects.get(name='ocw-www')
wc = WebsiteContent.objects.filter(
    metadata__icontains=<old_url_path>,
    website=www
)

```

## Step 8 — Search Indexes

Search on [ocw.mit.edu](https://ocw.mit.edu/search) — results should point to the new URL.

This may take some time, depending on when the indexing in open-discussions/learn completes.

## Step 9 — Remove Old Content from S3

> **Cleanup step only.** This step is optional and carries no urgency. Only proceed once you are fully satisfied that the new URL is working correctly, the redirect is in place, and all cross-site references have been resolved. There is no harm in leaving the old content in S3 temporarily while you verify everything.

Only do this once you are confident the entire migration was successful.

```bash
aws s3 rm s3://<AWS_PUBLISH_BUCKET_NAME>/courses/<old-slug>/ --recursive
aws s3 rm s3://<AWS_PREVIEW_BUCKET_NAME>/courses/<old-slug>/ --recursive

aws s3 rm s3://<AWS_OFFLINE_PUBLISH_BUCKET_NAME>/courses/<old-slug>/ --recursive
aws s3 rm s3://<AWS_OFFLINE_PREVIEW_BUCKET_NAME>/courses/<old-slug>/ --recursive

```
