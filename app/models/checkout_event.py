"""
CheckoutEvent entity (PRD Section 11).

Fields: id, cart_id, customer_id, cart_value, funnel_stage_reached,
created_at, last_activity_at, prior_abandonment_count.

Represents an abandoned-checkout entry point — no gateway code exists,
so this is detected via behavioral signal (app/rules/abandonment_scorer.py).

No implementation yet — skeleton only.
"""
