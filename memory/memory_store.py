"""
Memory Store
------------
Persistent JSON-backed memory store with helper methods for
querying, serialisation, and provenance lookup.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional


class MemoryStore:
    """
    In-memory dict backed by two JSON files:
      - memory_store.json  : current state of all entries
      - change_log.json    : append-only log of all decisions

    Internal structure
    ------------------
    self.store  : dict  { key → [entry_dict, ...] }
    self.log    : list  [ log_entry_dict, ... ]

    where key = "<subject_lower>||<predicate_lower>"
    """

    def __init__(self, store_path: str = "memory_store.json", log_path: str = "change_log.json"):
        self.store_path = store_path
        self.log_path = log_path
        self.store: dict[str, list[dict]] = {}
        self.log: list[dict] = []

    # ── Persistence ──────────────────────────────────────────────────────────

    def save(self):
        with open(self.store_path, "w", encoding="utf-8") as f:
            json.dump(self.store, f, indent=2, default=str)
        with open(self.log_path, "w", encoding="utf-8") as f:
            json.dump(self.log, f, indent=2, default=str)

    def load(self):
        if os.path.exists(self.store_path):
            with open(self.store_path, encoding="utf-8") as f:
                self.store = json.load(f)
        if os.path.exists(self.log_path):
            with open(self.log_path, encoding="utf-8") as f:
                self.log = json.load(f)

    # ── Query helpers ─────────────────────────────────────────────────────────

    def all_entries(self) -> list[dict]:
        """Flatten all entries across all keys."""
        out = []
        for key, entries in self.store.items():
            for e in entries:
                out.append({**e, "_key": key})
        return out

    def active_entries(self) -> list[dict]:
        return [e for e in self.all_entries() if e.get("status") == "active"]

    def get_by_subject(self, subject: str) -> list[dict]:
        result = []
        subject_lower = subject.lower()
        for key, entries in self.store.items():
            if key.startswith(subject_lower + "||"):
                result.extend(entries)
        return result

    def get_provenance(self, subject: str, predicate: str) -> list[dict]:
        """Return the full provenance chain for a (subject, predicate) pair."""
        key = f"{subject.strip().lower()}||{predicate.strip().lower()}"
        entries = self.store.get(key, [])
        claim_ids = {e.get("claim_id") for e in entries}
        return [lg for lg in self.log if lg.get("claim_id") in claim_ids]

    def explain(self, subject: str, predicate: str) -> str:
        """
        Human-readable explanation of why we believe the current best fact
        for a given (subject, predicate).
        """
        key = f"{subject.strip().lower()}||{predicate.strip().lower()}"
        entries = self.store.get(key, [])
        if not entries:
            return f"No memory found for '{subject}' — '{predicate}'."

        active = [e for e in entries if e.get("status") == "active"]
        best = max(active, key=lambda e: e.get("confidence", 0)) if active else None
        if not best:
            best = max(entries, key=lambda e: e.get("confidence", 0))

        lines = [
            f"BELIEF: '{subject}' {predicate} '{best['object']}'",
            f"  Confidence   : {best['confidence']:.3f}",
            f"  Status       : {best['status']}",
            f"  Sources      : {', '.join(best.get('sources', []))}",
            f"  Corroborated : {best.get('corroboration_count', 1)} time(s)",
            f"  First seen   : {best.get('first_seen', '?')}",
            f"  Last updated : {best.get('last_updated', '?')}",
            "",
            "HISTORY (from change log):",
        ]

        history = self.get_provenance(subject, predicate)
        for h in history:
            lines.append(
                f"  [{h['timestamp']}] {h['action']:12s} — {h['reason']}"
            )
        return "\n".join(lines)

    def summary_stats(self) -> dict:
        all_e = self.all_entries()
        from collections import Counter
        status_counts = Counter(e.get("status") for e in all_e)
        action_counts = Counter(lg.get("action") for lg in self.log)
        return {
            "total_entries": len(all_e),
            "by_status": dict(status_counts),
            "total_log_entries": len(self.log),
            "by_action": dict(action_counts),
        }
