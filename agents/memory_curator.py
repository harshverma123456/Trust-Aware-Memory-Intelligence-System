"""
Memory Curator Agent
---------------------
The decision-making heart of the pipeline.  Given:
  - ClaimRecord        (what was claimed)
  - VerificationResult (how trustworthy is it)
  - ConflictReport     (how it relates to existing memory)

It mutates the memory_store and appends to the change_log.

Decision Table
--------------
  NOVEL + trustworthy + label SUPPORTS       → ACCEPTED
  NOVEL + untrustworthy / low conf           → REJECTED
  DUPLICATE                                  → (silent skip, no log entry)
  CORROBORATION                              → MERGED  (confidence boosted)
  CONTRADICTION + new > existing             → UPDATED (old → outdated)
  CONTRADICTION + new < existing             → REJECTED (or DOWNGRADED if close)
  EQUAL_CONFLICT                             → DOWNGRADED (both drop slightly)
  Memory overflow (>MAX_LOW_CONF entries)    → FORGOTTEN (weakest evicted)
  REFUTES claim that matches stored          → DOWNGRADED
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from agents.claim_extractor import ClaimRecord, ClaimExtractorAgent
from agents.verification_agent import VerificationResult
from agents.contradiction_detector import ConflictReport


# ── Constants ────────────────────────────────────────────────────────────────

MAX_LOW_CONFIDENCE_ENTRIES = 10   # Trigger memory overflow eviction
LOW_CONF_THRESHOLD = 0.30         # Below this an entry is "low confidence"
FORGET_THRESHOLD = 0.20           # Below this, an entry is eligible for eviction
CORROBORATION_BOOST = 0.05        # Confidence gain per corroborating source
DOWNGRADE_PENALTY = 0.08          # Confidence drop when a contradiction arrives
EQUAL_CONFLICT_PENALTY = 0.05     # Both sides drop on equal conflict


# ── Agent ────────────────────────────────────────────────────────────────────

class MemoryCuratorAgent:

    def __init__(self, memory_store: dict, change_log: list):
        """
        memory_store : shared dict  { key → [entry_dict, ...] }
        change_log   : shared list  [ log_entry_dict, ... ]
        """
        self.memory = memory_store
        self.log = change_log

    # ── Public entry point ───────────────────────────────────────────────────

    def curate(
        self,
        claim: ClaimRecord,
        verification: VerificationResult,
        conflict: ConflictReport,
    ) -> str:
        """Process one claim.  Returns the action taken (for display)."""

        action = self._decide_action(claim, verification, conflict)
        return action

    # ── Decision logic ───────────────────────────────────────────────────────

    def _decide_action(
        self,
        claim: ClaimRecord,
        verification: VerificationResult,
        conflict: ConflictReport,
    ) -> str:
        rel = conflict.relationship
        key = self._make_key(claim.subject, claim.predicate)
        now_ts = claim.timestamp.isoformat()

        # ── DUPLICATE: already stored from same source ────────────────────
        if rel == "DUPLICATE":
            # Silently skip — no memory change, but still log for traceability
            self._append_log(
                claim_id=claim.id,
                timestamp=now_ts,
                action="REJECTED",
                reason="Exact duplicate from same source; already in memory.",
                old_value=conflict.existing_best_object,
                new_value=claim.object,
                confidence_delta=0.0,
            )
            return "REJECTED"

        # ── CORROBORATION: same meaning, new source ───────────────────────
        if rel == "CORROBORATION":
            return self._corroborate(claim, verification, conflict, key, now_ts)

        # ── NOVEL claim ───────────────────────────────────────────────────
        if rel == "NOVEL":
            return self._handle_novel(claim, verification, key, now_ts)

        # ── CONTRADICTION (clear winner) ──────────────────────────────────
        if rel == "CONTRADICTION":
            return self._handle_contradiction(claim, verification, conflict, key, now_ts)

        # ── EQUAL_CONFLICT ────────────────────────────────────────────────
        if rel == "EQUAL_CONFLICT":
            return self._handle_equal_conflict(claim, verification, conflict, key, now_ts)

        return "NOOP"

    # ── Handlers ─────────────────────────────────────────────────────────────

    def _handle_novel(self, claim, verification, key, now_ts) -> str:
        conf = verification.adjusted_confidence

        if not verification.is_trustworthy or conf < LOW_CONF_THRESHOLD:
            # Store as low_confidence rather than outright rejecting
            # so it can be evicted during overflow
            status = "low_confidence"
            action = "ACCEPTED"
            reason = (
                f"Low-trust or low-confidence claim accepted with low_confidence status "
                f"(source_reliability={claim.source_reliability:.2f})."
            )
        elif claim.label == "REFUTES":
            # A refuting claim with no prior memory — store as rejected
            status = "rejected"
            action = "REJECTED"
            reason = "REFUTES claim arrived with no existing memory to contradict — stored as rejected."
            self._upsert_entry(key, claim, conf, status, now_ts)
            self._append_log(claim.id, now_ts, action, reason, None, claim.object, 0.0)
            self._maybe_run_overflow()
            return action
        elif claim.label == "NOT ENOUGH INFO":
            status = "low_confidence"
            action = "ACCEPTED"
            reason = "NOT ENOUGH INFO claim stored with low_confidence status."
        else:
            status = "active"
            action = "ACCEPTED"
            reason = (
                f"New fact accepted. "
                f"Source '{claim.source_id}' (reliability={claim.source_reliability:.2f}), "
                f"confidence={conf:.3f}."
            )

        self._upsert_entry(key, claim, conf, status, now_ts)
        self._append_log(claim.id, now_ts, action, reason, None, claim.object, conf)
        self._maybe_run_overflow()
        return action

    def _corroborate(self, claim, verification, conflict, key, now_ts) -> str:
        entries = self.memory.get(key, [])
        # Find the best matching active entry
        best = self._best_active(entries)
        if best is None:
            return self._handle_novel(claim, verification, key, now_ts)

        old_conf = best["confidence"]
        # Boost confidence (diminishing returns via log)
        corr_count = best.get("corroboration_count", 1)
        boost = CORROBORATION_BOOST / math.log2(corr_count + 2)
        new_conf = round(min(old_conf + boost, 1.0), 4)

        best["confidence"] = new_conf
        best["corroboration_count"] = corr_count + 1
        best["last_updated"] = now_ts
        if claim.source_id not in best["sources"]:
            best["sources"].append(claim.source_id)
        # Mark active if it was low_confidence and now confidence is sufficient
        if best["status"] == "low_confidence" and new_conf >= LOW_CONF_THRESHOLD:
            best["status"] = "active"

        reason = (
            f"Corroborating claim from '{claim.source_id}' "
            f"(corroboration #{corr_count + 1}). "
            f"Confidence {old_conf:.3f} → {new_conf:.3f}."
        )
        self._append_log(claim.id, now_ts, "MERGED", reason, best["object"], claim.object, new_conf - old_conf)
        return "MERGED"

    def _handle_contradiction(self, claim, verification, conflict, key, now_ts) -> str:
        entries = self.memory.get(key, [])
        best = self._best_active(entries)
        new_conf = verification.adjusted_confidence
        old_conf = conflict.existing_best_confidence

        if claim.label == "REFUTES":
            # Refuting claim — downgrade existing if credible enough, else reject
            if not verification.is_trustworthy:
                self._append_log(
                    claim.id, now_ts, "REJECTED",
                    f"Adversarial REFUTES claim from low-trust source '{claim.source_id}' ignored.",
                    conflict.existing_best_object, claim.object, 0.0,
                )
                return "REJECTED"
            # Credible refutation → downgrade existing
            if best:
                penalty = min(DOWNGRADE_PENALTY * claim.source_reliability, old_conf)
                best["confidence"] = round(max(best["confidence"] - penalty, 0.0), 4)
                best["last_updated"] = now_ts
                if best["confidence"] < LOW_CONF_THRESHOLD:
                    best["status"] = "low_confidence"
                reason = (
                    f"Credible REFUTES from '{claim.source_id}' "
                    f"(reliability={claim.source_reliability:.2f}). "
                    f"Existing confidence penalised by {penalty:.3f}."
                )
                self._append_log(claim.id, now_ts, "DOWNGRADED", reason,
                                 conflict.existing_best_object, claim.object, -penalty)
            return "DOWNGRADED"

        # SUPPORTS but different value — classic update or reject
        if new_conf > old_conf:
            # New claim wins → update
            if best:
                best["status"] = "outdated"
                best["last_updated"] = now_ts
            # Add new entry
            self._upsert_entry(key, claim, new_conf, "active", now_ts)
            reason = (
                f"Higher-confidence source '{claim.source_id}' "
                f"(conf={new_conf:.3f}) supersedes existing '{conflict.existing_best_object}' "
                f"(conf={old_conf:.3f})."
            )
            self._append_log(claim.id, now_ts, "UPDATED", reason,
                             conflict.existing_best_object, claim.object, new_conf - old_conf)
            return "UPDATED"
        else:
            # Existing wins — reject new claim
            if not verification.is_trustworthy:
                reason = (
                    f"Adversarial/low-trust claim from '{claim.source_id}' "
                    f"rejected. Existing memory (conf={old_conf:.3f}) preserved."
                )
            else:
                reason = (
                    f"New claim (conf={new_conf:.3f}) has lower confidence than "
                    f"existing memory (conf={old_conf:.3f}). Rejected."
                )
            # Still store the rejected claim for provenance
            self._upsert_entry(key, claim, new_conf, "rejected", now_ts)
            self._append_log(claim.id, now_ts, "REJECTED", reason,
                             conflict.existing_best_object, claim.object, 0.0)
            return "REJECTED"

    def _handle_equal_conflict(self, claim, verification, conflict, key, now_ts) -> str:
        entries = self.memory.get(key, [])
        best = self._best_active(entries)

        if best:
            new_conf = round(max(best["confidence"] - EQUAL_CONFLICT_PENALTY, 0.0), 4)
            old_conf = best["confidence"]
            best["confidence"] = new_conf
            best["last_updated"] = now_ts
            if new_conf < LOW_CONF_THRESHOLD:
                best["status"] = "low_confidence"

        self._upsert_entry(key, claim, verification.adjusted_confidence - EQUAL_CONFLICT_PENALTY,
                           "low_confidence", now_ts)
        reason = (
            f"Equal-confidence conflict between '{conflict.existing_best_object}' and "
            f"'{claim.object}'. Both confidence scores reduced. Memory is uncertain."
        )
        self._append_log(claim.id, now_ts, "DOWNGRADED", reason,
                         conflict.existing_best_object, claim.object, -EQUAL_CONFLICT_PENALTY)
        return "DOWNGRADED"

    # ── Memory overflow / FORGET ─────────────────────────────────────────────

    def _maybe_run_overflow(self):
        """If too many low-confidence entries exist, evict the weakest ones."""
        all_low = [
            (key, entry)
            for key, entries in self.memory.items()
            for entry in entries
            if entry.get("status") in ("low_confidence",)
               and entry.get("confidence", 1.0) < FORGET_THRESHOLD
        ]

        if len(all_low) <= MAX_LOW_CONFIDENCE_ENTRIES:
            return

        # Sort by confidence ascending, evict weakest
        all_low.sort(key=lambda x: x[1].get("confidence", 0))
        to_evict = all_low[: len(all_low) - MAX_LOW_CONFIDENCE_ENTRIES]

        now_ts = datetime.now(timezone.utc).isoformat()
        for key, entry in to_evict:
            entry["status"] = "forgotten"
            entry["last_updated"] = now_ts
            self._append_log(
                claim_id=entry.get("claim_id", "?"),
                timestamp=now_ts,
                action="FORGOTTEN",
                reason=(
                    f"Memory overflow eviction. Entry confidence={entry['confidence']:.3f} "
                    f"below forget threshold ({FORGET_THRESHOLD})."
                ),
                old_value=entry.get("object"),
                new_value=None,
                confidence_delta=-entry["confidence"],
            )

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _upsert_entry(self, key, claim: ClaimRecord, confidence: float, status: str, now_ts: str):
        """Add a new memory entry under `key`."""
        entry = {
            "claim_id": claim.id,
            "subject": claim.subject,
            "predicate": claim.predicate,
            "object": claim.object,
            "confidence": round(min(max(confidence, 0.0), 1.0), 4),
            "status": status,
            "sources": [claim.source_id],
            "first_seen": now_ts,
            "last_updated": now_ts,
            "corroboration_count": 1,
            "provenance": [
                {
                    "claim_id": claim.id,
                    "source_id": claim.source_id,
                    "source_reliability": claim.source_reliability,
                    "label": claim.label,
                    "timestamp": now_ts,
                    "action": "INITIAL",
                }
            ],
        }
        if key not in self.memory:
            self.memory[key] = []
        self.memory[key].append(entry)

    def _append_log(self, claim_id, timestamp, action, reason, old_value, new_value, confidence_delta):
        self.log.append({
            "claim_id": claim_id,
            "timestamp": timestamp,
            "action": action,
            "reason": reason,
            "old_value": old_value,
            "new_value": new_value,
            "confidence_delta": round(confidence_delta, 4),
        })

    @staticmethod
    def _best_active(entries: list) -> Optional[dict]:
        active = [e for e in entries if e.get("status") == "active"]
        if not active:
            return None
        return max(active, key=lambda e: e.get("confidence", 0.0))

    @staticmethod
    def _make_key(subject: str, predicate: str) -> str:
        return f"{subject.strip().lower()}||{predicate.strip().lower()}"
