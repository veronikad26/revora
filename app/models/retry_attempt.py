"""
RetryAttempt entity (PRD Section 11, simplified idempotency).

Fields: failure_event_id, attempt_number, already_attempted (bool),
scheduled_time, executed_time, result.

The already_attempted flag is checked before executing a scheduled
retry to avoid double-charging or wasted duplicate actions.

No implementation yet — skeleton only.
"""
