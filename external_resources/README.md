# External Resource Availability Workflow

This document describes the workflow for validating external resources (link checking) and integrating with the Internet Archive's Wayback Machine.

**SECTIONS**

1. [Overview](#overview)
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

# Enabling Tasks

### External Resource Checking:

The task for external resource checking can be enabled/disabled using the `ENABLE_CHECK_EXTERNAL_RESOURCE_TASK` defined in [settings.py](/main/settings.py). By default, this task is enabled.

### Wayback Machine Tasks:

Wayback Machine tasks are governed by PostHog feature flags, with the feature flag key `OCW_STUDIO_WAYBACK_MACHINE_TASKS` defined in `ENABLE_WAYBACK_TASKS` in [constants.py](/external_resources/constants.py). In addition to this, the `ENABLE_WAYBACK_TASKS` setting in [settings.py](/main/settings.py) is responsible for adding the `update_wayback_jobs_status_batch` task to the Celery beat schedule.

Note: Changes to PostHog feature flags take effect immediately, but modifications to Celery beat schedules still require a restart.

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

Two management commands are available to interact with the external resources' Wayback Machine functionality:

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
