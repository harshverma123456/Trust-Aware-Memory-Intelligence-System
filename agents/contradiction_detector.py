"""
Contradiction Detection Agent
------------------------------
Given an incoming ClaimRecord + VerificationResult, looks up the
current memory store and classifies the relationship between the
new claim and any existing memory entries for the same
(subject, predicate) key.

Relationships
-------------
  NOVEL          – No memory entry exists yet
  DUPLICATE      – Exact same object value already stored
  CORROBORATION  – Semantically equivalent object from different source
  UPDATE         – New object value from credible source (non-conflicting evolution)
  CONTRADICTION  – Conflicting object value
  EQUAL_CONFLICT – Conflicting object value with similar confidence to existing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from agents.claim_extractor import ClaimRecord, ClaimExtractorAgent
from agents.verification_agent import VerificationResult


# ── Dataclass ────────────────────────────────────────────────────────────────

@dataclass
class ConflictReport:
    claim_id: str
    relationship: str                   # See module docstring
    conflicting_entry_keys: list[str]   # Keys of conflicting memory entries
    existing_best_confidence: float     # Confidence of strongest existing entry
    existing_best_object: str           # Object value of strongest existing entry
    details: str                        # Human-readable description


# ── Agent ────────────────────────────────────────────────────────────────────

class ContradictionDetectorAgent:
    """
    Detects conflicts between a new claim and the current memory store.
    The memory_store is passed in as a reference so it is always current.
    """

    SEMANTIC_THRESHOLD = 0.82   # similarity ratio to treat objects as equal

    def detect(
        self,
        claim: ClaimRecord,
        verification: VerificationResult,
        memory_store: dict,
    ) -> ConflictReport:
        """
        Parameters
        ----------
        claim        : Extracted & normalised claim
        verification : Verification result for the claim
        memory_store : Live memory store dict  {key → MemoryEntry list}

        Returns
        -------
        ConflictReport with the relationship classification.
        """
        key = self._make_key(claim.subject, claim.predicate)
        existing_entries = memory_store.get(key, [])

        # Filter to active entries only for conflict checking
        active_entries = [e for e in existing_entries if e.get("status") in ("active",)]

        if not existing_entries:
            return ConflictReport(
                claim_id=claim.id,
                relationship="NOVEL",
                conflicting_entry_keys=[],
                existing_best_confidence=0.0,
                existing_best_object="",
                details="No existing memory entry for this (subject, predicate) pair.",
            )

        # Find best existing active entry (highest confidence)
        best_entry = max(active_entries, key=lambda e: e.get("confidence", 0.0)) if active_entries else None
        if best_entry is None and existing_entries:
            best_entry = max(existing_entries, key=lambda e: e.get("confidence", 0.0))

        best_obj = best_entry.get("object", "") if best_entry else ""
        best_conf = best_entry.get("confidence", 0.0) if best_entry else 0.0
        best_sources = best_entry.get("sources", []) if best_entry else []

        new_obj = claim.object
        new_obj_norm = ClaimExtractorAgent._normalise_object(new_obj)
        best_obj_norm = ClaimExtractorAgent._normalise_object(best_obj)

        # ── REFUTES claims are NEVER duplicates or corroborations ─────────
        # A REFUTES label means the source is actively contradicting the
        # existing memory, even if the object text happens to match.
        if claim.label == "REFUTES":
            new_conf = verification.adjusted_confidence
            conf_delta = abs(new_conf - best_conf)
            if conf_delta <= 0.10:
                relationship = "EQUAL_CONFLICT"
                detail = (
                    f"REFUTES claim '{new_obj}' vs existing '{best_obj}'. "
                    f"Similar confidence levels (Δ={conf_delta:.3f}) — ambiguous."
                )
            else:
                relationship = "CONTRADICTION"
                detail = (
                    f"REFUTES claim '{new_obj}' vs existing '{best_obj}'. "
                    f"New conf={new_conf:.3f}, existing conf={best_conf:.3f}."
                )
            return ConflictReport(
                claim_id=claim.id,
                relationship=relationship,
                conflicting_entry_keys=[key],
                existing_best_confidence=best_conf,
                existing_best_object=best_obj,
                details=detail,
            )

        # ── Exact duplicate (same source, same value) ─────────────────────
        if new_obj_norm == best_obj_norm and claim.source_id in best_sources:
            return ConflictReport(
                claim_id=claim.id,
                relationship="DUPLICATE",
                conflicting_entry_keys=[key],
                existing_best_confidence=best_conf,
                existing_best_object=best_obj,
                details=f"Exact duplicate from same source '{claim.source_id}'.",
            )

        # ── Corroboration (semantically equal, different source) ──────────
        if ClaimExtractorAgent.objects_are_semantically_equal(new_obj, best_obj, self.SEMANTIC_THRESHOLD):
            return ConflictReport(
                claim_id=claim.id,
                relationship="CORROBORATION",
                conflicting_entry_keys=[key],
                existing_best_confidence=best_conf,
                existing_best_object=best_obj,
                details=(
                    f"Claim semantically matches existing memory "
                    f"('{best_obj}') from a different source — corroborates."
                ),
            )

        # ── Contradiction: check confidence delta ─────────────────────────
        new_conf = verification.adjusted_confidence
        conf_delta = abs(new_conf - best_conf)

        if conf_delta <= 0.10:
            relationship = "EQUAL_CONFLICT"
            detail = (
                f"Conflicting object '{new_obj}' vs existing '{best_obj}'. "
                f"Similar confidence levels (Δ={conf_delta:.3f}) — ambiguous."
            )
        else:
            relationship = "CONTRADICTION"
            detail = (
                f"Conflicting object '{new_obj}' vs existing '{best_obj}'. "
                f"New conf={new_conf:.3f}, existing conf={best_conf:.3f}."
            )

        return ConflictReport(
            claim_id=claim.id,
            relationship=relationship,
            conflicting_entry_keys=[key],
            existing_best_confidence=best_conf,
            existing_best_object=best_obj,
            details=detail,
        )

    @staticmethod
    def _make_key(subject: str, predicate: str) -> str:
        return f"{subject.strip().lower()}||{predicate.strip().lower()}"
