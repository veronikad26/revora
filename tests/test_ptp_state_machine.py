"""
Tests for the PTP state machine transitions (PRD Section 7).

To cover: DETECTED -> CONTACTED -> NEGOTIATING -> PROMISED ->
KEPT/BROKEN; DISPUTED -> ESCALATED (immediate, from any state);
BROKEN -> RENEGOTIATE (max 1x) -> ESCALATED.

No implementation yet — skeleton only.
"""
