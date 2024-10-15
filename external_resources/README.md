# External Resource Availability Workflow

This document describes the workflow for validating external resources and integrating with the Wayback Machine.

**SECTIONS**

1. [Overview](#overview)
1. [Enabling Tasks](#enabling-tasks)
1. [Wayback Machine Integration](#wayback-machine-integration)
1. [Frequency Control](#frequency-control)
1. [Rate Limiting](#rate-limiting)
1. [Task Priority](#task-priority)
1. [Management Commands](#management-commands)

# Overview

This assumes that celery beat scheduler is installed and enabled, which is required for the task scheduling.

<!-- Frequency for the task is set to `1/week`. After each week, all external resources, new or existing, will be validated regardless of their last status. -->

The high-level description of the process is below, and each subsequent section contains additional details, including links to the relevant code.

### External Resource Validation:

- Task is automatically added in scheduler on system start.
- On execution, all available external resources are retrieved from DB.
- Gathered data is divided into preconfigured batch sizes.
- All batches are grouped into a single celery task and executed.
- Each batch-task iterates over batch to validate availability of each resource and its backup resource if available.
- The status of resource is then added to DB.
- Batch tasks have a preconfigured rate-limiter and lower priority by default.

### Wayback Machine Integration:

- Valid external resources are submitted to the Wayback Machine for archiving after External Resource Validation.
- The status of Wayback Machine archiving jobs is tracked and updated.
- New external resources are automatically submitted to the Wayback Machine upon creation.

# Enabling Tasks

### External Resource Checking:

The task for external resource checking can be enabled/disabled using the `CHECK_EXTERNAL_RESOURCE_TASK_ENABLE` defined in [here](/main/settings.py). By default, this task is enabled.

### Wayback Machine Tasks:

Wayback Machine tasks can be enabled or disabled using the `ENABLE_WAYBACK_TASKS` defined in [here](/main/settings.py). By default, this task is enabled as well.

Note: Changes to these settings require restarting Celery workers to take effect.

# Wayback Machine Integration

When Wayback Machine tasks are enabled, the system performs the following actions:

- **Submission of Valid URLs:**
  - After an external resource URL is validated and found to be valid, it is submitted to the Wayback Machine for archiving.
  - The submission is handled by the `submit_url_to_wayback_task` task.
- **Automatic Submission on Creation:**
  - When a new external resource is created, it is automatically submitted to the Wayback Machine via the Django signal in [here](/external_resources/signals.py)
- **Tracking Job Status:**
  - The status of Wayback Machine archiving jobs is tracked using the `wayback_status` field in the `ExternalResourceState` model.
  - The system periodically updates the status of pending jobs using the `update_wayback_jobs_status_batch` task by the interval set by `UPDATE_WAYBACK_JOBS_STATUS_FREQUENCY` in [settings](/main/settings.py).
- **Re-submission Control:**
  - The system avoids re-submitting the same URL to the Wayback Machine within a specified interval, defined by `WAYBACK_SUBMISSION_INTERVAL_DAYS` in [settings](/main/settings.py).
  - This interval can be overridden using management command if needed (shared below).

# Frequency Control

- **External Resource Checking:**

  - The frequency of the external resource checking task is set using `CHECK_EXTERNAL_RESOURCE_STATUS_FREQUENCY` in [here](/main/settings.py).
  - The default value is 604800 seconds (1 week).
  - The task checks all external resources for availability regardless of their last status.

- **Wayback Machine Status Updates:**
  - The frequency of updating Wayback Machine job statuses in the task `update_wayback_jobs_status_batch` is controlled by `UPDATE_WAYBACK_JOBS_STATUS_FREQUENCY` in [here](/main/settings.py).
  - The default value is 21600 seconds (6 hours).
  - The task only checks external resources with wayback_status of `pending`.
  - The chunk size is provided by `BATCH_SIZE_WAYBACK_STATUS_UPDATE` in `constants.py`

# Rate Limiting

The rate-limit for the external resource batch-tasks is set using `EXTERNAL_RESOURCE_TASK_RATE_LIMIT` in [here](constants.py). The assigned value for the rate-limiter is set to `100/s`.

# Task Priority

Batch-task priority is set using the `EXTERNAL_RESOURCE_TASK_PRIORITY` in [here](constants.py). The default priority for each celery task has been preconfigured to `2` out of range `0(lowest) - 4(highest)`. External resource tasks have lowest (`0`) priority by default.

Priority levels and celery default task priority can be configured by `PRIORITY_STEPS` and `DEFAULT_PRIORITY`, respectively, in [here](/main/constants.py).
