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
"""
Central app configuration (PRD Section 10 — Tech Stack).

Single source of truth for:
- Environment-loaded credentials/URLs (.env).
- Guardrail constants that must NOT be scattered across nodes.

Every node that needs a guardrail number (retry caps, contact caps,
contact-hours window, confidence threshold, PTP extension limit,
opt-out keywords, or the risk-ops audit action name) imports it from
here rather than hardcoding it locally. This is what makes the
guardrails auditable as a single, reviewable list (PRD Section 6).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root regardless of CWD.
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


# --------------------------------------------------------------------------
# Credentials / connection strings (PRD Section 10 — Tech Stack)
# --------------------------------------------------------------------------

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

RAZORPAY_KEY_ID: str = os.getenv("RAZORPAY_KEY_ID", "")
RAZORPAY_KEY_SECRET: str = os.getenv("RAZORPAY_KEY_SECRET", "")

TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_FROM: str = os.getenv("TWILIO_WHATSAPP_FROM", "")

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./revora.db")

APP_ENV: str = os.getenv("APP_ENV", "development")
DRY_RUN: bool = os.getenv("DRY_RUN", "true").strip().lower() in {"1", "true", "yes", "on"}
HTTP_TIMEOUT_SECONDS: float = float(os.getenv("HTTP_TIMEOUT_SECONDS", "15"))
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")


def _require_in_production(name: str, value: str) -> None:
    """Fail loudly at startup if a required secret is missing outside dev."""
    if APP_ENV != "development" and not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Set it in .env before running outside APP_ENV=development."
        )


for _var_name, _var_value in (
    ("GEMINI_API_KEY", GEMINI_API_KEY),
    ("RAZORPAY_KEY_ID", RAZORPAY_KEY_ID),
    ("RAZORPAY_KEY_SECRET", RAZORPAY_KEY_SECRET),
    ("TWILIO_ACCOUNT_SID", TWILIO_ACCOUNT_SID),
    ("TWILIO_AUTH_TOKEN", TWILIO_AUTH_TOKEN),
    ("TWILIO_WHATSAPP_FROM", TWILIO_WHATSAPP_FROM),
):
    _require_in_production(_var_name, _var_value)


# --------------------------------------------------------------------------
# Hard, non-negotiable guardrail constants (PRD Section 6.4)
# --------------------------------------------------------------------------

# Maximum of 2 automated retries for any single failure, ever.
MAX_AUTO_RETRIES: int = 2

# Maximum of 3 outbound customer contacts per case before mandatory
# human escalation.
MAX_CUSTOMER_CONTACTS: int = 3

# No contact outside 9 AM-8 PM local time. Tuple of (start_hour, end_hour)
# in 24h local time, end-exclusive.
CONTACT_HOURS: tuple[int, int] = (9, 20)

# Below this confidence, the Recovery Router sends the case to human
# review instead of guessing (PRD Section 5.1).
CONFIDENCE_THRESHOLD: float = 0.70

# The only negotiable variable in a PTP is timing, and only within this
# many days of the original due date (PRD Section 6.4 / 7).
PTP_MAX_DATE_EXTENSION_DAYS: int = 30

# At most one Trust Firewall regeneration attempt before a message is
# escalated instead of resent (PRD Section 6.3).
TRUST_FIREWALL_MAX_REGENERATIONS: int = 1

# At most one renegotiation of a broken PTP before escalation
# (PRD Section 7).
PTP_MAX_RENEGOTIATIONS: int = 1


def effective_retry_limit(category_retry_limit: int) -> int:
    """
    The Policy Engine is the sole authority on how many retries a case
    may actually receive. Per-category playbooks (app/rules/playbook_table.yaml)
    propose a category-specific retry_limit, but that proposal can never
    exceed the global MAX_AUTO_RETRIES cap — the Policy Engine enforces
    min(category_retry_limit, MAX_AUTO_RETRIES), never the category
    limit alone. Centralized here so this rule has exactly one
    implementation instead of being reimplemented per node.
    """
    return min(category_retry_limit, MAX_AUTO_RETRIES)


# --------------------------------------------------------------------------
# STOP / opt-out (PRD Section 6.4)
# --------------------------------------------------------------------------
#
# "Instant opt-out honored — any 'stop' / 'बंद करो' reply halts all future
# automated contact permanently." This is a fixed keyword list (not an
# LLM judgment call) so opt-out detection is deterministic and cannot be
# talked out of by a customer reply or an LLM misparse. Matching is
# case-insensitive substring matching against the customer's raw reply
# text, checked BEFORE the reply is handed to the Communication node's
# intent parser.
#
# When matched, the Consent Gate's existing consent/state mechanism is
# used to permanently disable outreach: the matching ConsentFlag.consent
# is set to False (not deleted, so the "opted out" fact remains
# auditable), and an AuditLogEntry is written with the trigger. No new
# table is introduced for this.
OPT_OUT_KEYWORDS: tuple[str, ...] = (
    "stop",
    "unsubscribe",
    "opt out",
    "opt-out",
    "बंद करो",
    "बंद कर",
    "band karo",
    "band kar do",
)


# --------------------------------------------------------------------------
# Risk-ops routing (PRD Section 5 / 12)
# --------------------------------------------------------------------------
#
# Risk/Fraud Block cases are identified and routed only — never scored,
# never messaged, never retried. Routing is represented as a normal
# AuditLogEntry (app/models/audit_log_entry.py) using this action name,
# rather than a dedicated risk-ops table. Any node/dashboard query that
# needs "all risk-ops-flagged cases" filters AuditLogEntry on this
# action value.
RISK_OPS_AUDIT_ACTION: str = "risk_ops_flag"