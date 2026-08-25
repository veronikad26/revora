"""
ConsentFlag entity (PRD Section 11, simplified Consent Gate).

Fields: customer_id, channel, consent (bool).

Checked by the Consent Gate node before any outreach. If false or
missing, the case is routed to DO NOTHING with reason
"no consent on file".

No implementation yet — skeleton only.
"""
