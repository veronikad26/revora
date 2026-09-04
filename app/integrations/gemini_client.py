"""Gemini adapter limited to message generation and reply parsing."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import requests

from app.config import DRY_RUN, GEMINI_API_KEY, GEMINI_MODEL, HTTP_TIMEOUT_SECONDS


@dataclass(frozen=True)
class CustomerIntent:
    promise_date: str | None = None
    amount_acknowledged: bool = False
    dispute_flag: bool = False
    refusal: bool = False
    opt_out: bool = False
    raw_text: str = ""
    payment_confirmed: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "promise_date": self.promise_date,
            "amount_acknowledged": self.amount_acknowledged,
            "dispute_flag": self.dispute_flag,
            "refusal": self.refusal,
            "opt_out": self.opt_out,
            "raw_text": self.raw_text,
            "payment_confirmed": self.payment_confirmed,
        }


class GeminiClient:
    """Small REST adapter; external calls are disabled by default in development."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str = GEMINI_API_KEY, model: str = GEMINI_MODEL, *, dry_run: bool = DRY_RUN, http: Any = requests) -> None:
        self.api_key = api_key
        self.model = model
        self.dry_run = dry_run
        self.http = http

    @staticmethod
    def _dry_run_message(prompt: str) -> str:
        """Deterministic, content-aware stand-in for a live Gemini call.

        Keeps local/offline demos free of any API key while still reflecting
        the case's actual reference and amount (parsed out of the prompt
        built by communication.py's build_message_prompt), so a dashboard
        walkthrough shows a believable PTP-style reminder instead of a
        fixed placeholder string. No network call, no cost, no external
        dependency — purely local string construction.
        """
        reference_match = re.search(r"Reference:\s*([^.]+)\.", prompt)
        # FIX: the previous pattern `[0-9.,]+` was greedy and swallowed the
        # sentence-terminating period after the amount (e.g. captured
        # "1000.0." instead of "1000.0"), which then leaked a trailing
        # period into the generated message and the amount_clause. Anchor
        # on digits, with optional decimal groups, and stop before the
        # literal ". Action:" that always follows in build_message_prompt.
        amount_match = re.search(r"Amount:\s*INR\s*([0-9][0-9,]*(?:\.[0-9]+)?)", prompt)
        reference = reference_match.group(1).strip() if reference_match else "your case"
        amount = amount_match.group(1).strip() if amount_match else None
        amount_clause = f" of INR {amount}" if amount else ""
        return (
            f"Hi! This is a reminder about {reference} — a pending amount{amount_clause}. "
            "Could you share a date by which you can complete this payment? "
            "You can also open your payment app directly. Reply STOP anytime to opt out."
        )

    def _generate(self, prompt: str, *, response_mime_type: str | None = None) -> str:
        if not prompt or not prompt.strip():
            raise ValueError("prompt is required")
        if self.dry_run:
            return self._dry_run_message(prompt)
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for live LLM operations")
        generation_config: dict[str, Any] = {"temperature": 0.2, "maxOutputTokens": 512}
        if response_mime_type:
            generation_config["responseMimeType"] = response_mime_type
        url = f"{self.BASE_URL}/{self.model}:generateContent"
        response = self.http.post(
            url,
            params={"key": self.api_key},
            json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": generation_config},
            timeout=HTTP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            return payload["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("Gemini response did not contain candidate text") from exc

    def generate_message(self, prompt: str) -> str:
        """Generate one outbound message; caller must run Trust Firewall before send."""
        return self._generate(prompt)

    @staticmethod
    def _extract_json(text: str) -> dict[str, Any]:
        cleaned = text.strip().removeprefix("```json").removesuffix("```").strip()
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise ValueError("Gemini intent response did not contain a JSON object")
        value = json.loads(match.group(0))
        if not isinstance(value, dict):
            raise ValueError("Gemini intent response must be a JSON object")
        return value

    def parse_customer_reply(self, reply: str) -> CustomerIntent:
        if not reply or not reply.strip():
            raise ValueError("customer reply is required")
        if self.dry_run:
            lowered = reply.casefold()
            opt_out = any(term in lowered for term in ("stop", "unsubscribe", "band karo", "बंद करो"))
            dispute = any(term in lowered for term in ("dispute", "wrong amount", "गलत रकम", "not my invoice"))
            refusal = any(term in lowered for term in ("cannot pay", "can't pay", "refuse", "नहीं दे सकता"))
            acknowledged = any(term in lowered for term in ("pay", "payment", "invoice", "कर दूंगा", "कर दूँगा"))
            payment_confirmed = any(term in lowered for term in ("paid", "payment done", "payment successful", "भुगतान कर दिया"))
            promise_date = None
            date_match = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", reply)
            if date_match:
                promise_date = date_match.group(1)
            elif any(term in lowered for term in ("today", "aaj", "आज")) and not payment_confirmed:
                from datetime import date
                promise_date = date.today().isoformat()
            return CustomerIntent(promise_date=promise_date, amount_acknowledged=acknowledged, dispute_flag=dispute, refusal=refusal, opt_out=opt_out, raw_text=reply, payment_confirmed=payment_confirmed)
        schema = {"type": "OBJECT", "properties": {"promise_date": {"type": "STRING", "nullable": True}, "amount_acknowledged": {"type": "BOOLEAN"}, "dispute_flag": {"type": "BOOLEAN"}, "refusal": {"type": "BOOLEAN"}, "opt_out": {"type": "BOOLEAN"}, "payment_confirmed": {"type": "BOOLEAN"}}, "required": ["amount_acknowledged", "dispute_flag", "refusal", "opt_out", "payment_confirmed"]}
        prompt = ("Parse this customer reply into JSON only. Do not invent a date. "
                  "Fields: promise_date (ISO date or null), amount_acknowledged, dispute_flag, refusal, opt_out, payment_confirmed.\nReply: " + reply)
        raw = self._generate(prompt, response_mime_type="application/json")
        data = self._extract_json(raw)
        return CustomerIntent(
            promise_date=data.get("promise_date"),
            amount_acknowledged=bool(data.get("amount_acknowledged", False)),
            dispute_flag=bool(data.get("dispute_flag", False)),
            refusal=bool(data.get("refusal", False)),
            opt_out=bool(data.get("opt_out", False)),
            raw_text=reply,
            payment_confirmed=bool(data.get("payment_confirmed", False)),
        )


_default_client = GeminiClient()
generate_message = _default_client.generate_message
parse_customer_reply = _default_client.parse_customer_reply