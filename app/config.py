"""
Central app configuration.

Responsibilities (per PRD Section 10 — Tech Stack):
- Load environment variables (.env): Gemini API key, Razorpay keys,
  Twilio credentials, database URL.
- Expose guardrail constants that must NOT be scattered across nodes:
    MAX_AUTO_RETRIES = 2
    MAX_CUSTOMER_CONTACTS = 3
    CONTACT_HOURS = (9, 20)  # 9 AM - 8 PM local time
    CONFIDENCE_THRESHOLD = 0.70
    PTP_MAX_DATE_EXTENSION_DAYS = 30

No implementation yet — skeleton only.
"""
