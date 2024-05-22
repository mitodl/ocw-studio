# External Resource Availability Workflow

This document describes the workflow for the external resources validation tasks.

**SECTIONS**

1. [Overview](#overview)
1. [Frequency Control](#frequency-control)
1. [Rate Limiting](#rate-limiting)
1. [Task Priority](#task-priority)


# Overview

This assumes that celery beat scheduler is installed and enabled, which is required for the task scheduling.

Frequency for the task is set to `1/week`. After each week, all external resources, new or existing, will be validated regardless of their last status.

The high-level description of the process is below, and each subsequent section contains additional details, including links to the relevant code.

* Task is automatically added in scheduler on system start.
* On execution, all available external resources are retrieved from DB.
* Gathered data is divided into preconfigured batch sizes.
* All batches are grouped into a single celery task and executed.
* Each batch-task iterates over batch to validate availability of each resource and its backup resource if available.
* The status of resource is then added to DB.
* Batch tasks have a preconfigured rate-limiter and lower priority by default.


## Frequency Control

The task frequency (in seconds) is set using the `CHECK_EXTERNAL_RESOURCE_STATUS_FREQUENCY` in [here](/main/settings.py). Default value for the frequency is set to `604800 seconds -> 1 week`.


## Rate Limiting

The rate-limit for the external resource batch-tasks is set using `EXTERNAL_RESOURCE_TASK_RATE_LIMIT` in [here](constants.py). The assigned value for the rate-limiter is set to `100/s`.


## Task Priority

Batch-task priority is set using the `EXTERNAL_RESOURCE_TASK_PRIORITY` in [here](constants.py). The default priority for each celery task has been preconfigured to `2` out of range `0(lowest) - 4(highest)`. External resource tasks have lowest (`0`) priority by default.

Priority levels and celery default task priority can be configured by `PRIORITY_STEPS` and `DEFAULT_PRIORITY`, respectively, in [here](/main/constants.py).
