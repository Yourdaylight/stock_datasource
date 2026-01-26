## ADDED Requirements
### Requirement: Redis Queue as the Single Background Execution Channel
The system SHALL execute data synchronization tasks asynchronously via a Redis-backed queue and dedicated worker processes.
The HTTP API server SHALL NOT execute data synchronization work inline as part of request handling.

#### Scenario: Submit a sync task and return immediately
- **WHEN** a user triggers a data sync task via HTTP API
- **THEN** the system enqueues a task in Redis
- **AND** the API responds without waiting for the task to finish
- **AND** the response includes a `task_id` (and `execution_id` when applicable)

#### Scenario: Worker executes tasks independently of the API server
- **WHEN** the API server is running and at least one worker process is running
- **AND** a sync task exists in Redis queue
- **THEN** a worker consumes the task and executes the corresponding plugin
- **AND** the API server remains responsive during the execution

### Requirement: Fail Fast When Redis Is Not Available (Mode A)
The system SHALL treat Redis as a required dependency for data synchronization task submission and execution.
The system SHALL reject task submission when Redis is disabled or unreachable.
The system SHALL NOT silently fall back to an in-memory or threadpool execution path.

#### Scenario: Redis disabled by configuration
- **WHEN** `REDIS_ENABLED` is set to `false`
- **AND** a user attempts to create a sync task
- **THEN** the API returns a clear error indicating that async task queue is unavailable
- **AND** no task is created

#### Scenario: Redis unreachable at runtime
- **WHEN** Redis is enabled but unreachable (connection or ping fails)
- **AND** a user attempts to create a sync task
- **THEN** the API returns a clear error indicating that Redis is unavailable
- **AND** no silent fallback execution occurs

### Requirement: Task Status Query and Progress Reporting
The system SHALL expose task status and progress via a query API backed by Redis task metadata.
Task status SHALL include at least: `pending`, `running`, `completed`, `failed`, `cancelled`.
Task progress SHALL include at least: percentage and records processed (when applicable).

#### Scenario: Query a pending task
- **WHEN** a task is enqueued
- **THEN** querying the task by `task_id` returns status `pending`

#### Scenario: Query a running task
- **WHEN** a worker starts processing a task
- **THEN** querying the task by `task_id` returns status `running`
- **AND** returns `started_at`

#### Scenario: Query a completed task
- **WHEN** a task finishes successfully
- **THEN** querying the task by `task_id` returns status `completed`
- **AND** returns `completed_at`
- **AND** returns the final `records_processed`

#### Scenario: Query a failed task
- **WHEN** a task fails
- **THEN** querying the task by `task_id` returns status `failed`
- **AND** returns a bounded error message suitable for UI display

### Requirement: Timeout Enforcement
The worker SHALL enforce a wall-clock timeout for each task execution.
If the timeout is exceeded, the system SHALL mark the task as failed and release worker capacity.

#### Scenario: Task exceeds timeout
- **WHEN** a task execution exceeds its configured timeout
- **THEN** the task transitions to status `failed`
- **AND** the failure reason indicates a timeout
- **AND** the worker remains able to process subsequent tasks

### Requirement: Automatic Retry With Backoff
The worker SHALL retry failed tasks that are classified as retryable up to a configured maximum attempt count.
Retries SHALL use a backoff strategy.

#### Scenario: Retryable error triggers retry
- **WHEN** a task fails with a retryable error
- **AND** the task has remaining retry attempts
- **THEN** the system schedules a retry
- **AND** the task metadata reflects the incremented attempt count

#### Scenario: Retries exhausted
- **WHEN** a task fails
- **AND** no retry attempts remain
- **THEN** the task transitions to status `failed`
- **AND** the final error is available via status query

### Requirement: Task Cancellation
The system SHALL support cancelling tasks that have not started executing.

#### Scenario: Cancel a pending task
- **WHEN** a task is in status `pending`
- **AND** the user requests cancellation
- **THEN** the task is removed from the queue
- **AND** the task transitions to status `cancelled`

## MODIFIED Requirements
### Requirement: Financial Report Data Retrieval
The system SHALL support retrieving financial report-related market data via plugins.
When such retrieval is executed as part of a data synchronization job, it SHALL be executed asynchronously via the Redis queue worker system.

#### Scenario: Financial report plugin sync is executed asynchronously
- **WHEN** a financial report related plugin is triggered via data synchronization API
- **THEN** the system enqueues the work and returns a `task_id`
- **AND** the plugin execution occurs in a worker process

## ADDED Requirements
### Requirement: Proxy-Safe Execution for TuShare Data Fetching
When HTTP proxy is configured for TuShare access, the worker SHALL apply proxy settings only within the task execution scope.
The system SHALL NOT apply proxy settings globally at HTTP server startup.

#### Scenario: Proxy is applied only during task execution
- **WHEN** HTTP proxy is enabled in runtime configuration
- **AND** a worker executes a TuShare-backed plugin
- **THEN** outbound TuShare network calls use the configured proxy
- **AND** other unrelated HTTP server operations are not forced to use the proxy
