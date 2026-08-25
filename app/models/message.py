"""
Message entity (PRD Section 11).

Fields: id, ptp_id, direction (out|in), content, trust_firewall_result,
blocked_reason (nullable), timestamp.

Every outbound message's Trust Firewall pass/fail decision is logged
here, including blocked-and-regenerated messages.

No implementation yet — skeleton only.
"""
