"""Shared helper for persisting the one guardrail decision that must
survive a single case invocation: a customer's opt-out (PRD Section 6.4).

Both the Consent Gate (outbound path) and the inbound Communication reply
parser can independently detect a "STOP"-style reply. Whichever one sees
it first calls this so ``ConsentFlag.consent`` is flipped to ``False`` and
the trigger is recorded as an ``AuditLogEntry`` -- no new table, per the
Phase 0 decision that opt-out handling doesn't need one.

This function is intentionally a no-op when ``session`` is ``None`` so
every caller stays fully testable without a database: direct unit tests
(and any ``build_graph()`` call that omits ``session_factory``, such as
the evaluation harness) keep their existing in-memory-only behavior.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.audit_log_entry import AuditLogEntry
from app.models.consent_flag import ConsentFlag

OPT_OUT_AUDIT_ACTION = "opt_out"


def record_opt_out(session: Any, *, customer_id: str, channel: str, case_id: str, reason: str) -> None:
    """Flip ``ConsentFlag.consent`` to ``False`` and audit-log the trigger.

    Upserts the ``ConsentFlag`` row for ``(customer_id, channel)`` rather
    than deleting it, so "this customer previously opted out" remains an
    auditable fact rather than an absence of data.
    """
    if session is None or not customer_id:
        return
    record = session.query(ConsentFlag).filter_by(customer_id=customer_id, channel=channel).one_or_none()
    if record is None:
        session.add(ConsentFlag(id=str(uuid.uuid4()), customer_id=customer_id, channel=channel, consent=False))
    else:
        record.consent = False
    session.add(
        AuditLogEntry(
            id=str(uuid.uuid4()),
            case_id=case_id or "unknown",
            entity_type="consent",
            entity_id=f"{customer_id}:{channel}",
            action=OPT_OUT_AUDIT_ACTION,
            actor="rule",
            reason=reason,
            customer_visible_reason=None,
            created_at=datetime.now(timezone.utc),
        )
    )