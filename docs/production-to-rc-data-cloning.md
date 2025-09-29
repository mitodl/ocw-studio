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

### 1.1 Set up Concourse Pipeline Config

Create a concourse pipeline configuration for database replication. This is essentially a pg_dump followed by a pg_restore. Set the postgres image version as appropriate.

```yaml
jobs:
  - build_log_retention:
      builds: 10
    name: restore-db
    plan:
      - config:
          image_resource:
            name: ""
            source:
              repository: postgres
              tag: "16"
            type: registry-image
          outputs:
            - name: dump
          params:
            PGHOST: ((source.host))
            PGPASSWORD: ((source.password))
            PGPORT: ((source.port))
            PGUSER: ((source.username))
          platform: linux
          run:
            args:
              - -c
              - pg_dump -v -Fc -d ((source.database)) > ./dump/db.dump
            path: /bin/sh
        task: run-pg-dump
      - config:
          image_resource:
            name: ""
            source:
              repository: postgres
              tag: "16"
            type: registry-image
          inputs:
            - name: dump
          params:
            PGHOST: ((destination.host))
            PGPASSWORD: ((destination.password))
            PGPORT: ((destination.port))
            PGUSER: ((destination.username))
          platform: linux
          run:
            args:
              - -c
              - pg_restore -v --clean --no-privileges --no-owner -d ((destination.database))
                ./dump/db.dump
            path: /bin/sh
        task: run-pg-restore
```

### 1.2 Configure Pipeline Variables

Create a `vars.yaml` file with database connection information:

```yaml
source:
  database: ocw_studio
  host: [PRODUCTION_HOST]
  port: 5432
  username: [PRODUCTION_USERNAME]
  password: [PRODUCTION_PASSWORD]
destination:
  database: [RC_DATABASE]
  host: [RC_HOST]
  port: 5432
  username: [RC_USERNAME]
  password: [RC_PASSWORD]
```

**Getting Connection Information:**
At MIT, ocw-studio is run in heroku, hence the database name, host, username and password can be obtained through the heroku cli as `heroku config:get -a <app_name> DATABASE_URL`

### 1.3 Deploy and Run Pipeline

Push the pipeline to Concourse:

```bash
fly -t rc set-pipeline -p db-restore -c db-restore.yml --load-vars-from vars.yaml
```

Then trigger the pipeline through the Concourse UI.

## Step 2: Google Drive Folder Management

After the database restore, Website objects' gdrive folders will be pointing to the production gdrive instance. We need to update them to point to appropriate RC gdrive links.

### 2.1 Clear Existing gdrive Folder References

In a Django shell on the RC environment:

```python
from websites.models import *
Website.objects.all().update(gdrive_folder=None)
```

### 2.2 Recreate GDrive Folders

Run the management command to recreate missing GDrive folders:

```bash
./manage.py recreate_missing_gdrive_folders
```

This command will:

- Check if each website has a corresponding GDrive folder in the RC GDrive account
- Create new folders where they don't exist
- Assign existing folders where they do exist

## Step 3: GitHub Synchronization

The RC environment needs to synchronize all content with GitHub repositories. This can be done by clearing sync states for the ContentSyncState objects and subsequently running a mass publish.

### 3.1 Reset Sync States

Reset all sync states to ensure a clean synchronization:

```bash
./manage.py reset_sync_states --skip_sync
```

### 3.2 Mass Publish (Excluding ocw-www)

Publish all websites except `ocw-www`:

```bash
./manage.py mass_publish --exclude ocw-www
```

**Note:** This process can take a very long time as it publishes every website to GitHub.

### 3.3 Publish ocw-www Separately

The `ocw-www` website requires special handling due to its large size. This is the reason we exclude it during the mass publish as its publication is prone to network failures.

Go to the studio UI and trigger a publish of ocw-www. Verify from the github content repo that the content has been properly synced. This step may run into failures due to the large number of objects associated to ocw-www. If repeated attempts to publish `ocw-www` fail, you can use batch-processing to sync `ocw-www` to its github content repo:-

1. Set all ContentSyncState objects for `ocw-www` to have already been synced:

```python
# In Django shell
from content_sync.models import ContentSyncState
from websites.models import Website

ocw_www = Website.objects.get(name='ocw-www')
sync_states = ContentSyncState.objects.filter(website=ocw_www)

for sync_state in sync_states:
    sync_state.synced_checksum = sync_state.calculate_checksum()
    sync_state.save()
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

### 4.1 Refresh Pipeline Definitions

After all content has been published, refresh the pipeline definitions:

```bash
./manage.py upsert_mass_build_pipeline
./manage.py upsert_mass_build_pipeline --offline
./manage.py backpopulate_pipelines
```

### 4.2 Trigger Mass Build

Now is the time to trigger a mass build through the concourse UI and verify that it completes without errors.

One issue that you are likely to run into here is the circular dependency between `ocw-www` and course sites. Particularly, the problem is that

- `ocw-www` needs those course sites to be built that it references(for example in course lists)
- Course sites need instructor JSON files, which are only generated when `ocw-www` is built

One way to get around this is to manually copy instructor JSON files from production to RC:

```bash
# Example AWS CLI command (adjust bucket names as needed)
aws s3 sync s3://ol-ocw-studio-app-production/instructors/ s3://ol-ocw-studio-app-qa/instructors/
```

## Step 5: Static Asset Synchronization (Optional)

Assets may not load properly on newly built sites because we haven't replicated the content buckets across the environments yet. Note that the content bucket may contain hundreds of GBs of data so you may want to consult with devops/SRE for advice on the best way to achieve this.

### 5.1 Sync S3 Buckets

To sync static assets from production to RC:

```bash
# Full sync (this can be very large - ~2TB)
aws s3 sync s3://ol-ocw-studio-app-production/ s3://ol-ocw-studio-app-qa/ --exclude "instructors/*"

```

In the future, we will be setting up an automated concourse pipeline for regular incremental syncs.

### 5.2 Run the mass build

Once the content buckets have been synced, trigger the mass build again and monitor it to completion.
