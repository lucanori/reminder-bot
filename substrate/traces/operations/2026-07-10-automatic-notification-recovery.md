---
status: completed
created_at: 2026-07-10
files_edited:
  - reminder_bot/utils/scheduler.py
  - tests/unit/utils/test_scheduler.py
  - tests/unit/utils/test_scheduler_recovery.py
  - tests/unit/utils/test_scheduler_recovery_security.py
rationale:
  - Restore every active reminder automatically after a process or container restart without requiring user interaction.
  - Keep database state durable before publishing replacement jobs to the in-memory scheduler.
supporting_docs:
  - substrate/traces/operations/2026-04-07-event-loop-startup-fix.md
  - substrate/traces/research/2026-04-06-project-state.md
  - substrate/traces/reviews/2026-07-10-restart-notification-recovery-security.md
---

# Automatic notification recovery

## Summary of changes

The scheduler now restores every active reminder during startup, including reminders overdue by more than 60 minutes, without involving `/start`. Escalation deadlines are persisted and committed before replacement jobs enter memory, while overdue catch-up work is staggered and globally concurrency-limited.

## Technical reasoning

APScheduler uses an in-memory job store, so the reminders table remains the durable source of truth. The former recovery cutoff left old active reminders permanently unscheduled, and escalation jobs did not persist their next deadline. Recovery now creates a database-backed plan, commits it, and only then adds idempotent scheduler jobs.

The first overdue reminder runs 30 seconds after recovery and each subsequent overdue reminder is delayed by another two seconds. A scheduler-wide semaphore limits notification processing to five concurrent jobs before database sessions or Telegram calls begin. These controls prevent restart bursts without discarding reminders.

This operation extends the startup work in [[2026-04-07-event-loop-startup-fix]] and closes the volatile scheduler gap recorded in [[2026-04-06-project-state]].

## Impact assessment

- Users no longer need to send `/start` after service recovery.
- Future reminders retain their persisted deadlines.
- Overdue reminders resume automatically in a controlled sequence.
- Database commit failures cannot publish uncommitted recovery or escalation jobs to memory.
- Existing at-least-once delivery and single-instance assumptions remain unchanged.

## Validation steps

- `git diff --check` passed.
- Ruff formatting passed for all four changed Python files.
- Ruff checks passed after excluding repository baseline and documentation-rule conflicts `D101`, `D102`, `D103`, `D107`, `B904`, and `E722`.
- The complete test suite passed with 248 tests and 70 percent coverage.
- The production Docker image built successfully as `reminder-bot:restart-recovery-test`.
- Trivy found no secrets or Dockerfile misconfigurations. It reported pre-existing Mako and base-image vulnerabilities because no dependency, lockfile, or container definition changed in this operation.
- The final review in [[2026-07-10-restart-notification-recovery-security]] passed with no open task-introduced security findings after remediation.
