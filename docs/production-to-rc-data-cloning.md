# Cloning production to RC/staging

This document outlines the process for duplicating OCW Studio data from production to RC/staging environments. This process ensures that testing on RC uses realistic production data, making testing more reliable and accurate.

## Overview

At a high level, the process consists of the following steps:

1. **Database replication** - Copying the PostgreSQL database from production to RC
2. **Google Drive folder management** - Handling gdrive connections and folder assignments for the sites
3. **GitHub synchronization** - Publishing content to GitHub repositories
4. **Pipeline management** - Creating/Updating build pipelines for the new environment and running the mass build
5. **Static asset synchronization** - Copying S3 bucket contents (optional)

## Step 1: Database Replication

### 1.1 Prerequisites

Follow the [Platform Engineering guide](https://pe.ol.mit.edu/getting_started/developer_eks_access/) for getting set up with EKS credentials, if you haven't already.

### 1.2 Get connection info

Save the production and RC `DATABASE_URL`s to local shell variables, rather than printing them to the terminal:

```
PROD_DATABASE_URL=$(kubectl get secret -n ocw-studio postgres-ocw-studio-dynamic-secret --context applications-production -o jsonpath='{.data.DATABASE_URL}' | base64 --decode)
RC_DATABASE_URL=$(kubectl get secret -n ocw-studio postgres-ocw-studio-dynamic-secret --context applications-qa -o jsonpath='{.data.DATABASE_URL}' | base64 --decode)
```

### 1.3 Create ephemeral pods

Production and RC/QA can't reach each other's database directly, so the dump is piped from a pod in one cluster to a pod in the other, through your own machine.

Create one in production:

```
kubectl run pg-client-<your name> \
  --image=postgres:18 \
  --restart=Never \
  --context applications-production \
  -n ocw-studio \
  --command -- sleep 3600

kubectl wait --for=condition=Ready pod/pg-client-<your name> --context applications-production -n ocw-studio --timeout=120s
```

And one in RC/QA:

```
kubectl run pg-client-<your name> \
  --image=postgres:18 \
  --restart=Never \
  --context applications-qa \
  -n ocw-studio \
  --command -- sleep 3600

kubectl wait --for=condition=Ready pod/pg-client-<your name> --context applications-qa -n ocw-studio --timeout=120s
```

### 1.4 Dump and restore

Try the direct pipe first — simplest option, fine for smaller databases:

```
kubectl exec -n ocw-studio --context applications-production pg-client-<your name> -- pg_dump -v -Fc -d "$PROD_DATABASE_URL" | kubectl exec -i -n ocw-studio --context applications-qa pg-client-<your name> -- pg_restore -v --clean --no-privileges --no-owner -d "$RC_DATABASE_URL"
```

**If it drops partway through** (`unexpected EOF`, `could not read from input file: end of file`): this is a hard limit, not a fluke. `kubectl exec` on these clusters authenticates with an AWS EKS token that expires after ~15 minutes, and that isn't configurable — any single continuous `kubectl exec`/`cp` session gets cut at that mark regardless of what's transferring. The fix is to move the dump in chunks small enough to each finish inside that window.

Dump to a file in the production pod:

```
kubectl exec -n ocw-studio --context applications-production pg-client-<your name> -- pg_dump -v -Fc -d "$PROD_DATABASE_URL" -f /tmp/prod.dump
```

Split it into chunks (size `-b` based on how much data moved before the connection dropped last time, so each chunk comfortably finishes in a few minutes):

```
kubectl exec -n ocw-studio --context applications-production pg-client-<your name> -- sh -c 'cd /tmp && split -b 5m prod.dump prod.dump.part'
```

Copy each chunk to the RC pod under its own name — don't combine yet, so a dropped chunk is caught before it can corrupt the restore:

```
kubectl exec -n ocw-studio --context applications-production pg-client-<your name> -- sh -c 'ls /tmp/prod.dump.part*' | while IFS= read -r part; do
  echo "Copying $part"
  kubectl exec -n ocw-studio --context applications-production pg-client-<your name> -- cat "$part" | kubectl exec -i -n ocw-studio --context applications-qa pg-client-<your name> -- sh -c "cat > $part"
done
```

Verify every chunk arrived before combining — compare the file lists and sizes on both sides:

```
kubectl exec -n ocw-studio --context applications-production pg-client-<your name> -- sh -c 'ls -la /tmp/prod.dump.part*'
kubectl exec -n ocw-studio --context applications-qa pg-client-<your name> -- sh -c 'ls -la /tmp/prod.dump.part*'
```

Only once both listings match exactly (same files, same sizes), combine the chunks and restore:

```
kubectl exec -n ocw-studio --context applications-qa pg-client-<your name> -- sh -c 'cat /tmp/prod.dump.part* > /tmp/prod.dump'
kubectl exec -n ocw-studio --context applications-qa pg-client-<your name> -- pg_restore -v --clean --no-privileges --no-owner -d "$RC_DATABASE_URL" /tmp/prod.dump
```

If the dump or restore step itself runs past ~15 minutes rather than the transfer, background it the same way (`nohup ... > /tmp/dump.log 2>&1 &` inside the pod), then check progress with a fresh, short `kubectl exec ... -- tail /tmp/dump.log`.

### 1.5 Clean up

```
kubectl delete pod -n ocw-studio --context applications-production pg-client-<your name>
kubectl delete pod -n ocw-studio --context applications-qa pg-client-<your name>
```

## Step 2: Google Drive Folder Management

Once the database is restored, Website objects' gdrive folders will be pointing to the Google Drive for the production environment. We need to update these to link to appropriate folders in the Google Drive for the RC environment.

### 2.1 Clear Existing gdrive Folder References

In a Django shell on the RC environment:

```python
from websites.models import Website
Website.objects.all().update(gdrive_folder=None)
```

### 2.2 Create/Update GDrive Folders

Run the management command to create missing GDrive folders:

```bash
./manage.py create_missing_gdrive_folders
```

This command will:

- Check if each website has a corresponding GDrive folder in the RC GDrive account
- Create new folders where they don't exist
- Assign existing folders where they do exist

## Step 3: GitHub Synchronization

The RC environment needs to synchronize all content with GitHub repositories. This can be done by clearing sync states for the ContentSyncState objects and subsequently running a mass publish.

### 3.1 Backpopulate Site Pipelines

Cloned websites already have a `publish_date` (inherited from production), which the publish flow (`content_sync/api.py::publish_website`) treats as "this site's Concourse pipeline already exists," skipping pipeline creation. RC's Concourse has no pipeline for these sites yet, so publishing before this step fails to trigger a build — you'll see `Could not find live build <id> for <site>` / `A live pipeline build failed for <site>` in the celery logs, and the stale production build ID is left in place. Create the missing per-site pipelines first:

```bash
./manage.py backpopulate_pipelines
```

### 3.2 Reset Sync States

Reset all sync states to ensure complete synchronization:

```bash
./manage.py reset_sync_states --skip_sync
```

### 3.3 Mass Publish (Excluding ocw-www)

Publish all websites except `ocw-www`, for both live and draft:

```bash
./manage.py mass_publish live --exclude ocw-www
./manage.py mass_publish draft --exclude ocw-www
```

**Note:** This process can take a long time as it publishes every website to GitHub.

### 3.4 Publish ocw-www separately

The `ocw-www` website requires special handling due to its large size. This is the reason we exclude it during the mass publish as its publication is prone to network failures.

Go to the studio UI and trigger a publish of `ocw-www`. Verify from the github content repo that the content has been properly synced. This step may run into failures due to the large number of objects associated to `ocw-www`. If repeated attempts to publish `ocw-www` fail, you can use batch-processing to sync `ocw-www` to its github content repo:-

1. Set all ContentSyncState objects for `ocw-www` to have already been synced:

```python
# In Django shell
from django.db.models import F
from content_sync.models import ContentSyncState
from websites.models import Website

ocw_www = Website.objects.get(name='ocw-www')
ContentSyncState.objects.filter(website=ocw_www).update(synced_checksum=F('current_checksum'))
```

2. Process in batches of ~500 objects:

```python
# Select a batch and reset their sync state
batch = sync_states[:500]
batch.update(synced_checksum=None)
```

3. Trigger github sync for this batch by publishing through the UI. Verify from the github content repo that the sync completed.
4. Repeat for remaining batches

## Step 4: Pipeline Management and Mass build

### 4.1 Refresh Mass Build Pipeline Definitions

After all content has been published, refresh the mass build pipeline definitions:

```bash
./manage.py upsert_mass_build_pipeline
./manage.py upsert_mass_build_pipeline --offline
```

### 4.2 Trigger Mass Build

Now is the time to trigger a mass build through the concourse UI and verify that it completes without errors.

One issue that you are likely to run into here is the circular dependency between `ocw-www` and course sites. Particularly, the problem is that

- `ocw-www` needs those course sites to be built that it references (for example in course lists)
- Course sites need instructor JSON files, which are only generated when `ocw-www` is built

One way to get around this is to manually copy instructor JSON files from production to RC:

```bash
aws s3 sync s3://{AWS_PUBLISH/PREVIEW_BUCKET_NAME_PROD}/instructors/ s3://{AWS_PUBLISH/PREVIEW_BUCKET_NAME_RC}/instructors/
```

## Step 5: Static Asset Synchronization (Optional)

Assets may not load properly on newly built sites because we haven't replicated the content buckets across the environments yet. Note that the content bucket may contain hundreds of GBs of data so you may want to consult with devops/SRE for advice on the best way to achieve this.

### 5.1 Sync S3 Buckets

To sync static assets from production to RC:

```bash
aws s3 sync s3://{AWS_STORAGE_BUCKET_NAME_PROD}/ s3://{AWS_STORAGE_BUCKET_NAME_RC}/"

```

In the future, we will be setting up an automated concourse pipeline for regular incremental syncs.

### 5.2 Run the mass build

Once the content buckets have been synced, trigger the mass build again and monitor it to completion.
