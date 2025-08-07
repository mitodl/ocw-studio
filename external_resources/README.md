# External Resource Availability Workflow

If a resource is valid, the `check_external_resources` task triggers the `submit_url_to_wayback_task` to archive it.

**External resource creation**: External resources can be created in multiple ways:

1. **Manually** through the content management interface
2. **Automatically** when adding links in the content editor
3. **Via markdown cleanup** command for converting legacy external links (processes all websites by default; use `--published-only` flag for published websites only)
   - **Note**: Requires either `--commit` flag to save changes or `--out filename.csv` to export results
   - **Referencing content tracking**: Automatically tracks which content references each external resource

Here's a high-level description of the process: Workflow

This document describes the workflow for validating external resources (link checking) and integrating with the Internet Archive's Wayback Machine.

**SECTIONS**

1. [Overview](#overview)
1. [External Resource Creation](#external-resource-creation)
1. [Enabling Tasks](#enabling-tasks)
1. [Wayback Machine Integration](#wayback-machine-integration-1)
1. [Wayback Machine Removal Requests](#wayback-machine-removal-requests)
1. [Frequency Control](#frequency-control)
1. [Rate Limiting](#rate-limiting)
1. [Task Priority](#task-priority)
1. [Management Commands](#management-commands)
1. [Code References](#code-references)

# Overview

This assumes that **Celery beat scheduler** is installed and enabled, which is required for the task scheduling.

The frequency for **external resource checking** is set to once per week (`1/week`), as defined by the `CHECK_EXTERNAL_RESOURCE_STATUS_FREQUENCY` variable. All external resources, both new and existing, are validated weekly, regardless of their last status.

The **Wayback Machine integration** is enabled by default. Valid external resources are submitted for archiving as part of the external resource validation task. The system monitors the submission status and avoids resubmitting resources within a specified interval of `30` days, as defined by the `WAYBACK_SUBMISSION_INTERVAL_DAYS` variable.

The status of Wayback Machine archiving jobs is updated every `6` hours to track the progress of pending jobs, as defined by the `UPDATE_WAYBACK_JOBS_STATUS_FREQUENCY` variable.

These variables can be found in [settings.py](/main/settings.py).

If a resource is valid, the `check_external_resources` task triggers the `submit_url_to_wayback_task` to archive it.

Here’s a high-level description of the process:

### External Resource Validation:

- Task is automatically added in scheduler on system start.
- On execution, all available external resources are retrieved from DB.
- Gathered data is divided into preconfigured batch sizes, defined by `BATCH_SIZE_EXTERNAL_RESOURCE_STATUS_CHECK` in [websites/constants.py](/websites/constants.py), which is currently set to `100`.
- All batches are grouped into a single Celery task and executed.
- Each batch-task iterates over the batch to validate availability of each resource and its backup resource if available.
- The status of resource is then added to DB.
- Batch tasks have a preconfigured rate limiter and lower priority by default.

### Wayback Machine Integration:

- When external resource validation occurs, valid external resources are submitted to the Wayback Machine for archiving.
- The status of Wayback Machine archiving jobs is tracked and updated periodically (currently, every 6 hours).
- New external resources are automatically submitted to the Wayback Machine upon creation.

# External Resource Creation

External resources can be created in multiple ways:

### 1. Manual Creation via Content Form

External resources can be created manually through the OCW Studio content management interface:

- Navigate to the course content area
- Add a new external resource content item
- Fill in the required fields (title, external URL, description, etc.)
- Configure metadata and settings as needed
- Save to create the external resource

### 2. Automatic Creation in Editor

When adding links in the content editor, external resources are automatically created:

- When inserting external links in the text editor
- The system automatically creates external resource objects for external URLs
- These are then rendered as resource_link shortcodes in the final content
- Applies to course content created using the OCW course starter

### 3. Legacy Link Conversion via Markdown Cleanup

The `markdown_cleanup` command is used to convert legacy external links to external resources:

**Purpose**: Convert existing markdown links and navigation menu external links to the new external resource system.

**LinkToExternalResourceRule**: Converts markdown links `[text](url)` to external resource shortcodes `{{% resource_link "uuid" "text" %}}` and creates corresponding external resource objects.

**NavItemToExternalResourceRule**: Converts navigation menu external links to external resource references.

**Key behaviors:**

- **Default processing scope**: All websites (published and unpublished) are processed by default.
- **Published-only option**: Use `--published-only` flag to process only published websites.
- **Safety-first defaults**: Commands run in dry-run mode by default; use `--commit` flag to save changes to database.
- **Referencing content tracking**: Automatically establishes relationships between content and the external resources they reference.
- **External License Warning Control**: The command provides three-state control over external license warnings:
  - **Default behavior**: Domains matching the `SITEMAP_DOMAIN` setting (defaults to `ocw.mit.edu`) show no warnings; external domains show warnings
  - **Force enable**: Use `--add-external-license-warning` to show warnings for ALL domains (including the `SITEMAP_DOMAIN`)
    - Use case: Migration scenarios where you want consistent warning behavior across all external links
  - **Force disable**: Use `--no-external-license-warning` to hide warnings for ALL domains
    - Use case: Environments where license warnings are not needed
  - **Mutual exclusion**: The two license warning flags cannot be used together
- **Internal reference support**: Navigation items that reference internal content are tracked with proper referencing relationships.
- **External license warnings**: Non-`SITEMAP_DOMAIN` URLs automatically get `has_external_license_warning: true`.
- **Deduplication**: Existing external resources with the same URL are reused rather than creating duplicates.
- **Course content only**: Rules only apply to websites using the OCW course starter.

**Example transformation:**

```markdown
# Before

[MIT OpenCourseWare](https://ocw.mit.edu)
[Example Site](https://example.com)

# After

{{% resource_link "f3d0ebae-7083-4524-9b93-f688537a0317" "MIT OpenCourseWare" %}}
{{% resource_link "d3d0ebae-7083-3453-7b92-a688537a0276" "Example Site" %}}
```

All methods create external resource objects with:

- Unique UUID identifiers
- Automatic filename generation based on title
- External license warnings for non-OCW domains
- Metadata populated from site configuration defaults

# Enabling Tasks

### External Resource Checking:

The task for external resource checking can be enabled/disabled using the `ENABLE_CHECK_EXTERNAL_RESOURCE_TASK` defined in [settings.py](/main/settings.py). By default, this task is enabled.

### Wayback Machine Tasks:

Wayback Machine tasks are controlled by the `ENABLE_WAYBACK_TASKS` environment setting in [settings.py](/main/settings.py), which is `False` by default. It can be overridden through your `.env` file.

If the `ENABLE_WAYBACK_TASKS` setting is set to `True`, Wayback Machine tasks are executed.

Note: Modifications to Celery beat schedules require a restart.

**Restart Instructions:**

- Local Development: Restart the Celery container (`ocw-studio-celery-1`).
- RC/Production (Heroku): `worker` and `extra_worker` are the relevant dynos. You can simply click on "Restart all dynos" from the Heroku dashboard.

# Wayback Machine Integration

When Wayback Machine tasks are enabled, the system performs the following actions:

- **Submit Valid URLs:**
  - After an external resource URL is validated and found to be valid, it is submitted to the Wayback Machine for archiving.
  - The submission is handled by the `submit_url_to_wayback_task` task.
- **Automatically Submit on Creation:**
  - When a new external resource is created, it is automatically submitted to the Wayback Machine via the Django signal in [signals.py](/external_resources/signals.py).
- **Track Job Statuses:**
  - The status of Wayback Machine archiving jobs is tracked using the `wayback_status` field in the `ExternalResourceState` model.
  - The system periodically updates the status of pending jobs using the `update_wayback_jobs_status_batch` task at an interval set by `UPDATE_WAYBACK_JOBS_STATUS_FREQUENCY` in [settings.py](/main/settings.py). Currently, it is set to `6` hours (21600 seconds).
- **Control Resubmissions:**
  - The system avoids resubmitting the same URL to the Wayback Machine within a specified interval, defined by `WAYBACK_SUBMISSION_INTERVAL_DAYS` in [settings.py](/main/settings.py). Currently, it is set to `30` days.
  - This interval can be overridden using the `submit_sites_to_wayback` management command with `--force` flag (as detailed below).

# Wayback Machine Removal Requests

To request removal of a URL from the Wayback Machine, email info@archive.org with the details mentioned in [this guide](https://help.archive.org/help/how-do-i-request-to-remove-something-from-archive-org/).

# Frequency Control

- **External Resource Checking:**

  - The frequency of the external resource checking task is set using `CHECK_EXTERNAL_RESOURCE_STATUS_FREQUENCY` in [settings.py](/main/settings.py).
  - The default value is 604800 seconds (1 week).
  - The task checks all external resources for availability regardless of their last status.

- **Wayback Machine Status Updates:**
  - The frequency of updating Wayback Machine job statuses in the task `update_wayback_jobs_status_batch` is controlled by `UPDATE_WAYBACK_JOBS_STATUS_FREQUENCY` in [settings.py](/main/settings.py).
  - The default value is 21600 seconds (6 hours).
  - The task only checks external resources with wayback_status of `pending`.
  - The chunk size is provided by `BATCH_SIZE_WAYBACK_STATUS_UPDATE` in [constants.py](/external_resources/constants.py). Currently, it is set to `50`.

# Rate Limiting

- **External Resource Checking:**

  - The rate limit for the external resource checking tasks is set using `EXTERNAL_RESOURCE_TASK_RATE_LIMIT` in [constants.py](/external_resources/constants.py).
  - The assigned rate limit value is `100/s`.

- **Wayback Machine Tasks:**
  - The rate limit for Wayback Machine submission tasks is set using `WAYBACK_MACHINE_TASK_RATE_LIMIT` in [constants.py](/external_resources/constants.py).
  - The assigned rate limit value is `0.11/s`, which means approximately `1` request every `9` seconds.

# Task Priority

- **External Resource Checking:**

  - Batch-task priority is set using the `EXTERNAL_RESOURCE_TASK_PRIORITY` in [constants.py](/external_resources/constants.py).
  - External resource tasks have the lowest priority (`4`) by default, out of range `0(highest) - 4(lowest)`.

- **Wayback Machine Tasks:**
  - The priority for Wayback Machine submission tasks is set using `WAYBACK_MACHINE_SUBMISSION_TASK_PRIORITY` in [constants.py](/external_resources/constants.py).
  - The assigned priority value is currently set to `3`.

**Note**: Priority levels and Celery default task priority can be configured by `PRIORITY_STEPS` and `DEFAULT_PRIORITY`, respectively, in [main/constants.py](/main/constants.py).

# Management Commands

Three management commands are available to interact with external resources:

- **Markdown Cleanup with External Resource Processing:**
  - Command: `markdown_cleanup`.
  - Usage:
    - Performs various markdown cleaning operations, including converting external links to external resources.
    - **Default behavior**: Processes all websites (both published and unpublished).
    - Use the `--published-only` flag to process only published websites.
    - **REQUIRED**: Must specify either `--commit` (to save changes) or `--out filename.csv` (to export results).
    - Supports various cleanup rules including `link_to_external_resource` and `nav_item_to_external_resource`.
    - Automatically tracks referencing content relationships when creating external resources.
    - Use `--out filename.csv` to export results to CSV for analysis.
  - Example Usage:

```
    # Dry-run: process and export results to CSV without database changes
    ./manage.py markdown_cleanup link_to_external_resource --out external_links.csv

    # Convert external links to external resources for all websites
    ./manage.py markdown_cleanup link_to_external_resource --commit

    # Convert only for published websites
    ./manage.py markdown_cleanup link_to_external_resource --published-only --commit

    # Convert navigation menu external links to external resources
    ./manage.py markdown_cleanup nav_item_to_external_resource --commit

    # Commit changes and export results for analysis
    ./manage.py markdown_cleanup link_to_external_resource --commit --out results.csv

    # Force license warnings for ALL domains (including OCW domains)
    ./manage.py markdown_cleanup link_to_external_resource --add-external-license-warning --commit

    # Disable license warnings for ALL domains
    ./manage.py markdown_cleanup link_to_external_resource --no-external-license-warning --commit

    # Use license warning control with published-only processing
    ./manage.py markdown_cleanup link_to_external_resource --published-only --add-external-license-warning --commit
```

- **Submitting Resources to Wayback Machine:**
  - Command: `submit_sites_to_wayback`.
  - Usage:
    - Submits all external resources for specified websites to the Wayback Machine.
    - Supports website filtering via options (e.g., `--filter course-name`).
    - Use the `--force` flag to force submission even if resources were submitted recently (bypassing `WAYBACK_SUBMISSION_INTERVAL_DAYS` logic).
  - Example Usage:

```
    ./manage.py submit_sites_to_wayback --filter "example-site"
    ./manage.py submit_sites_to_wayback --filter "example-site" --force
```

- **Updating Wayback Machine Statuses:**
  - Command: `update_wayback_status`.
  - Usage:
    - Updates the status of pending Wayback Machine jobs for specified websites.
    - Supports website filtering via the options.
    - Use the `--sync` flag to run updates synchronously; note that this requires specifying website filters.
  - Example Usage:

```
    ./manage.py update_wayback_status --filter "example-site" --sync
    ./manage.py update_wayback_status --filter "example-site"
    ./manage.py update_wayback_status
```

# Code References

- **Models:**
  - [`ExternalResourceState`](/external_resources/models.py): Stores the state and Wayback Machine information for external resources.
- **Management Commands:**
  - [`markdown_cleanup`](/websites/management/commands/markdown_cleanup.py): Main command for processing markdown content and converting external links to resources.
- **Markdown Cleanup Rules:**
  - [`LinkToExternalResourceRule`](/websites/management/commands/markdown_cleaning/rules/link_to_external_resource.py): Converts markdown links to external resource shortcodes.
  - [`NavItemToExternalResourceRule`](/websites/management/commands/markdown_cleaning/rules/link_to_external_resource.py): Converts navigation menu external links to external resources.
- **Tasks:**
  - [`check_external_resources`](/external_resources/tasks.py): Checks external resources for broken links.
  - [`submit_url_to_wayback_task`](/external_resources/tasks.py): Submits external resource URLs to the Wayback Machine. This task is linked with `check_external_resources` and will only send valid external resources.
  - [`update_wayback_jobs_status_batch`](/external_resources/tasks.py): Updates the status of Wayback Machine archiving jobs.
- **API:**
  - [`api.py`](/external_resources/api.py): Contains functions for checking URLs and interacting with the Wayback Machine API.
- **Signals:**
  - [`signals.py`](/external_resources/signals.py): Creates `ExternalResourceState` for the External Resource (`WebsiteContent`), and submits the link to the Wayback Machine upon creation.
- **Celery Configuration:**
  - [`celery.py`](/main/celery.py): Configures the Celery app with task routing, priority, and other settings for handling external resource validation and Wayback Machine integration.
- **Constants and Settings:**
  - [`external_resources/constants.py`](/external_resources/constants.py), [`websites/constants.py`](/websites/constants.py): Defines constants such as batch sizes, task priorities, and rate limits for external resource checking and Wayback Machine tasks.
  - Settings in [`main/settings.py`](/main/settings.py) control tasks enabling (used in `tasks.py`), frequency, and other configurations.
- **Deployment Configuration:**
  - [`app.json`](/app.json): Defines deployment-specific environment variables and metadata for Heroku, including placeholders for Wayback Machine API credentials, submission intervals, and app configuration details.
