"""
Verification Agent
------------------
Scores the trustworthiness of an incoming ClaimRecord and
annotates it with a verification result that the downstream
agents use for memory decisions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from agents.claim_extractor import ClaimRecord


# ── Dataclass ────────────────────────────────────────────────────────────────

@dataclass
class VerificationResult:
    claim_id: str
    is_trustworthy: bool          # True if worth considering
    adjusted_confidence: float    # 0.0 – 1.0
    threat_score: float           # For REFUTES claims: how dangerous to existing memory
    flags: list[str]              # Human-readable flags
    verdict: str                  # SHORT summary: "HIGH_TRUST" | "LOW_TRUST" | "ADVERSARIAL" | "UNVERIFIABLE"


# ── Agent ────────────────────────────────────────────────────────────────────

class VerificationAgent:
    """
    Applies heuristic trustworthiness rules to produce a VerificationResult.

    Rules
    -----
    1. source_reliability < 0.3  → ADVERSARIAL / LOW_TRUST flag
    2. NOT VERIFIABLE            → confidence penalised by ×0.5
    3. REFUTES label             → compute threat_score for conflict resolution
    4. Missing timestamp         → confidence penalised by ×0.9 (slight uncertainty)
    """

    TRUST_THRESHOLD = 0.30          # Below this → untrusted
    HIGH_TRUST_THRESHOLD = 0.75     # Above this → high trust

    def verify(self, claim: ClaimRecord) -> VerificationResult:
        flags: list[str] = []
        confidence = claim.initial_confidence

        # --- Verifiability penalty -------------------------------------------
        if claim.verifiable == "NOT VERIFIABLE":
            confidence *= 0.5
            flags.append("NOT_VERIFIABLE")

        # --- Missing timestamp penalty ----------------------------------------
        if claim.timestamp_missing:
            confidence *= 0.9
            flags.append("MISSING_TIMESTAMP")

        # --- Source reliability checks ----------------------------------------
        if claim.source_reliability < self.TRUST_THRESHOLD:
            flags.append("LOW_TRUST_SOURCE")
            verdict = "ADVERSARIAL"
            is_trustworthy = False
        elif claim.source_reliability >= self.HIGH_TRUST_THRESHOLD:
            flags.append("HIGH_TRUST_SOURCE")
            verdict = "HIGH_TRUST"
            is_trustworthy = True
        else:
            verdict = "MODERATE_TRUST"
            is_trustworthy = True

        # --- Label-based adjustments -----------------------------------------
        if claim.label == "NOT ENOUGH INFO":
            flags.append("INSUFFICIENT_EVIDENCE")
            confidence *= 0.5
            if verdict not in ("ADVERSARIAL",):
                verdict = "UNVERIFIABLE"

        if claim.label == "REFUTES" and claim.source_reliability >= self.TRUST_THRESHOLD:
            flags.append("REFUTING_CLAIM")

        # Clamp
        confidence = round(min(max(confidence, 0.0), 1.0), 4)

        # Threat score: how strongly this claim threatens existing memory
        # Only meaningful for REFUTES; for SUPPORTS it stays 0.0
        threat_score = 0.0
        if claim.label == "REFUTES":
            threat_score = round(claim.source_reliability * 0.8, 4)

        return VerificationResult(
            claim_id=claim.id,
            is_trustworthy=is_trustworthy,
            adjusted_confidence=confidence,
            threat_score=threat_score,
            flags=flags,
            verdict=verdict,
        )
