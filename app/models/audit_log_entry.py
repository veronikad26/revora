"""
AuditLogEntry entity (PRD Section 11).

Fields: id, entity_type, entity_id, action, actor
(rule|llm|policy_engine|human), reason, timestamp.

The single source of truth for the whole system. Written BEFORE
execution for every action, including DO NOTHING. Also the source
for the customer-facing transparency footer (PRD Section 8.2).

No implementation yet — skeleton only.
"""
