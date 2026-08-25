"""
Twilio WhatsApp integration client (PRD Section 10 — Tech Stack).

Responsibilities:
- Send outbound WhatsApp messages (nudges, PTP negotiation messages,
  update-card prompts) via Twilio's WhatsApp API.
- Receive inbound customer replies via Twilio webhook callback,
  forwarded into the graph's Communication node for intent parsing.
- Never sends a clickable payment link — only the fixed,
  whitelisted "open your app" instruction (Trust Firewall constraint).

No implementation yet — skeleton only.
"""
