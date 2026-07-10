---
status: completed
created_at: 2026-07-10
updated_at: 2026-07-10
reviewer: security-review-specialist
target: cumulative restart notification recovery diff
scope: scheduler recovery implementation, scheduler unit tests, and relevant unchanged repository, startup, dependency, and container context
supporting_docs:
  - tests/unit/utils/test_scheduler_recovery.py
  - tests/unit/utils/test_scheduler_recovery_security.py
  - substrate/traces/status/2026-07-10-restart-notification-recovery-workspace-state.md
---

# Restart notification recovery security review

## Summary

One medium and one low task-introduced availability and integrity risk remain. Unbounded overdue recovery can create a boot-time notification storm. Database updates are added to memory scheduler before transaction commit, so commit failure can leave memory and database state divergent. No task-introduced authorization, injection, secret leakage, or cross-user access regression found.

## Scope and methodology

Reviewed Git status, cumulative diff, modified scheduler and tests, repository transaction behavior, startup order, notification flow, access checks, DTO constraints, and unchanged container and dependency configuration. Traced database-to-memory transitions, replay paths, per-reminder error isolation, untrusted reminder volume, logs, and authorization boundaries.

Review was source-only. No Docker, scanner, network, application, or active tests were run by this reviewer. Supplied test, Docker, and Trivy results were considered but not independently executed.

## Findings by severity

### Medium

#### 🟡 risk: Unbounded overdue catch-up creates restart notification storm

- **Location:** `reminder_bot/utils/scheduler.py:374`, `reminder_bot/utils/scheduler.py:377`, `reminder_bot/utils/scheduler.py:397`, `reminder_bot/utils/scheduler.py:407`; `reminder_bot/bot_service.py:55`, `reminder_bot/bot_service.py:66`
- **Status:** Introduced by this task. It amplifies preexisting lack of per-user active-reminder quotas.
- **Evidence:** Recovery loads every active reminder, rewrites every overdue row to approximately 30 seconds in the future, and creates one memory job per row. Scheduler starts only after recovery returns. Large recovery sets therefore become overdue together and execute as a burst. Diff removes prior 60-minute cutoff without adding batching, age policy, rate limiting, or concurrency bounds across distinct jobs.
- **Impact:** A bot user can accumulate unbounded active reminders. After downtime or restart, stale backlog can drive many concurrent Telegram calls and database sessions, exhaust API limits or process resources, and delay or deny notifications for other users. Legitimate large backlogs create the same availability failure.
- **False-positive notes:** Existing code already permits many future reminders and multi-instance duplicate scheduling. Finding is limited to new restart amplification for reminders previously skipped when more than 60 minutes overdue. Small, trusted deployments reduce likelihood but do not bound impact.
- **Remediation:** Recover in bounded batches. Apply global send concurrency and rate limits. Stagger overdue jobs instead of assigning one 30-second window. Enforce per-user active-reminder quotas. Define maximum catch-up age or explicit stale-reminder policy rather than silently replaying an unlimited backlog.

### Low

#### 🟡 risk: Database-before-memory ordering is not durable

- **Location:** `reminder_bot/utils/scheduler.py:234`, `reminder_bot/utils/scheduler.py:247`, `reminder_bot/utils/scheduler.py:398`, `reminder_bot/utils/scheduler.py:407`; `reminder_bot/utils/database.py:46`, `reminder_bot/utils/database.py:51`; `reminder_bot/bot_service.py:264`, `reminder_bot/bot_service.py:66`
- **Status:** Introduced by this task's new persistence steps. Post-send crash replay and memory-only scheduling were preexisting.
- **Evidence:** `update_next_notification()` executes inside `get_async_session()`, but transaction commits only when context exits. Both new paths add memory jobs before that commit. If commit fails, recovery error is caught and startup continues; staged jobs remain and scheduler starts. Similar divergence can occur in running `_send_reminder_job()` flow.
- **Impact:** Memory jobs can execute while database retains stale `next_notification`. Later recovery or crash can replay notifications. Commit failure can also strand or duplicate schedule state, violating database source-of-truth guarantee.
- **False-positive notes:** Normal boot commits before scheduler starts, and a process crash before scheduler start loses staged memory jobs too. Risk requires commit failure, cancellation handling that preserves process state, or running scheduler path. Tests mock repository return order and do not observe transaction commit order.
- **Remediation:** Commit durable schedule state before adding memory jobs. On commit or recovery failure, remove staged jobs or fail startup. Add reconciliation for schedule-add failure after commit. Durable job store, transactional outbox, or claimed pending-job state provides stronger crash and multi-instance guarantees.

## Excluded preexisting risks

- Telegram send occurs before transaction commit in `_send_reminder_job()`, so crash-after-send replay already existed. New code does not close that at-least-once delivery window.
- Recovery lacks a database lease or compare-and-set claim, so multiple bot instances can schedule duplicate work. Unchanged deployment defines one bot container; task did not introduce multi-instance architecture.
- Reported Mako, `rustls-webpki`, Debian base-image, and other image vulnerabilities are dependency or base-image risks. No dependency, lockfile, Dockerfile, or Compose change belongs to this task.
- Existing logs include identifiers and exception strings. New log calls add reminder IDs only and do not add reminder text, credentials, or tokens.

## Remediation timeline

1. Before merge, bound and stagger overdue catch-up to address medium availability risk.
2. Before production rollout, make database commit and memory scheduling failure handling explicit.
3. Separately triage and patch reported dependency and base-image vulnerabilities without attributing them to this task.

## Validation notes

- Seed more overdue reminders than configured recovery batch and verify bounded boot memory, database sessions, Telegram send concurrency, and staggered execution.
- Force transaction commit failure after successful `update_next_notification()` and verify no staged memory job can run.
- Force scheduler add failure after committed persistence and verify reconciliation retries or marks pending work.
- Start two instances against one database and verify one durable claim produces one notification.
- Crash immediately before and after Telegram send and document expected at-least-once or exactly-once behavior.

## Update: 2026-07-10 by security-review-specialist

### Prior finding status

- Unbounded overdue catch-up notification storm (medium): resolved. `reminder_bot/utils/scheduler.py:32` creates one scheduler-wide five-send semaphore, and `reminder_bot/utils/scheduler.py:197` acquires it before database session creation and holds it across notification processing. `reminder_bot/utils/scheduler.py:407-420` staggers successfully persisted overdue reminders by two seconds. This bounds database and Telegram concurrency while preserving every overdue reminder.
- Database-before-memory ordering (low): resolved. Running notification chain commits at `reminder_bot/utils/scheduler.py:254` before scheduling at `reminder_bot/utils/scheduler.py:255`. Recovery commits all database updates at `reminder_bot/utils/scheduler.py:429` before any scheduler call at `reminder_bot/utils/scheduler.py:431-438`. Commit failure reaches outer error path before memory-job loop.

### New findings

No new task-introduced vulnerability found.

Remaining unbounded active-reminder count and full-list recovery at `reminder_bot/repositories/reminder_repository.py:74-83` are preexisting capacity risks. Stale recovery adds sequential work, but new stagger and semaphore remove prior concurrent restart amplification. Scheduler-add failure can still delay one notification until later recovery, but memory-only scheduling and lack of continuous reconciliation predate this task. Multi-instance duplicate delivery still lacks a distributed claim and remains preexisting under unchanged single-container deployment.

Reported Mako, `rustls-webpki`, Debian base-image, and other image vulnerabilities remain dependency or base-image findings. No dependency, lockfile, Dockerfile, Compose, or agent configuration change belongs to remediation.

### New validation notes

- Source confirms commit-before-add ordering on both changed persistence paths.
- `tests/unit/utils/test_scheduler_recovery_security.py:140-199` covers commit failure without escalation scheduling.
- `tests/unit/utils/test_scheduler_recovery_security.py:203-292` covers recovery commit ordering and zero jobs after commit failure.
- `tests/unit/utils/test_scheduler_recovery_security.py:296-349` covers overdue staggering.
- `tests/unit/utils/test_scheduler_recovery_security.py:429-479` covers five-job concurrency bound before database work.
- Supplied final results report 248 passing tests, successful format and lint gates, successful Docker build, and unchanged Trivy findings. This reviewer did not independently run tests, Docker, scanners, network calls, or active checks.
