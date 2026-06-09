"""
Claim Extractor Agent
---------------------
Parses raw JSONL claim records, normalises missing timestamps,
detects semantic near-duplicates using character-level similarity,
and produces a clean ClaimRecord dataclass for downstream agents.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional


# ── Dataclass ────────────────────────────────────────────────────────────────

@dataclass
class ClaimRecord:
    id: str
    timestamp: datetime
    timestamp_missing: bool
    source_id: str
    source_reliability: float
    verifiable: str          # "VERIFIABLE" | "NOT VERIFIABLE"
    label: str               # "SUPPORTS" | "REFUTES" | "NOT ENOUGH INFO"
    claim: str
    subject: str
    predicate: str
    object: str
    notes: str
    # Filled in by ClaimExtractorAgent
    normalised_object: str = field(default="")
    initial_confidence: float = field(default=0.0)


# ── Agent ────────────────────────────────────────────────────────────────────

class ClaimExtractorAgent:
    """Parses and normalises incoming claim dicts."""

    LABEL_WEIGHTS = {
        "SUPPORTS": 1.0,
        "NOT ENOUGH INFO": 0.4,
        "REFUTES": 0.6,        # Weight used for adversarial scoring
    }

    # Fallback base time for claims with null timestamps
    _FALLBACK_BASE = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    _fallback_counter = 0

    def extract(self, raw: dict) -> ClaimRecord:
        ts_raw = raw.get("timestamp")
        if ts_raw is None:
            self._fallback_counter += 1
            # Give it a synthetic timestamp far in the future so it is processed last
            ts = datetime(2025, 1, 1, 0, 0, self._fallback_counter, tzinfo=timezone.utc)
            ts_missing = True
        else:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            ts_missing = False

        label = raw.get("label", "NOT ENOUGH INFO")
        source_reliability = float(raw.get("source_reliability", 0.5))
        label_weight = self.LABEL_WEIGHTS.get(label, 0.4)

        if label == "SUPPORTS":
            initial_confidence = source_reliability * label_weight
        elif label == "REFUTES":
            # For REFUTES, confidence represents the threat level to existing memory
            initial_confidence = source_reliability * label_weight
        else:
            # NOT ENOUGH INFO — low confidence baseline
            initial_confidence = source_reliability * label_weight

        obj = raw.get("object") or ""

        record = ClaimRecord(
            id=raw["id"],
            timestamp=ts,
            timestamp_missing=ts_missing,
            source_id=raw.get("source_id", "Unknown"),
            source_reliability=source_reliability,
            verifiable=raw.get("verifiable", "NOT VERIFIABLE"),
            label=label,
            claim=raw.get("claim", ""),
            subject=raw.get("subject", ""),
            predicate=raw.get("predicate", ""),
            object=obj,
            notes=raw.get("notes", ""),
            normalised_object=self._normalise_object(obj),
            initial_confidence=initial_confidence,
        )
        return record

    # ── Number extraction for numeric-aware comparison ─────────────────────

    # Written-out numbers → digits mapping
    _WORD_NUMS = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
        "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
        "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90, "hundred": 100,
    }
    _MULTIPLIERS = {
        "thousand": 1_000, "million": 1_000_000, "billion": 1_000_000_000,
        "m": 1_000_000, "b": 1_000_000_000, "k": 1_000,
    }

    @classmethod
    def _extract_numbers(cls, text: str) -> set[float]:
        """Extract all numeric values from a string, handling $5M, five million, 15 million, etc."""
        s = text.lower().strip()
        nums: set[float] = set()

        # Pattern 1:  $5M, $50M, $8.5B, 10k etc.
        for m in re.finditer(r'\$?\s*(\d+(?:\.\d+)?)\s*([mkb])\b', s):
            val = float(m.group(1))
            mult = cls._MULTIPLIERS.get(m.group(2), 1)
            nums.add(val * mult)

        # Pattern 2:  plain numbers like "2021", "2010", "10", "15"
        for m in re.finditer(r'\b(\d+(?:\.\d+)?)\b', s):
            nums.add(float(m.group(1)))

        # Pattern 3:  written-out numbers with multiplier ("five million", "fifty million")
        for word, val in cls._WORD_NUMS.items():
            pattern = rf'\b{word}\s+(million|billion|thousand)\b'
            match = re.search(pattern, s)
            if match:
                mult = cls._MULTIPLIERS.get(match.group(1), 1)
                nums.add(val * mult)

        return nums

    @staticmethod
    def _normalise_object(obj: str) -> str:
        """Lower-case, strip punctuation and expand common abbreviations."""
        s = obj.lower().strip()
        # Expand written numbers
        s = s.replace("five million dollars", "$5m")
        s = s.replace("five million", "$5m")
        s = s.replace("eight million dollars", "$8m")
        s = s.replace("eight million", "$8m")
        # Remove trailing punctuation
        s = re.sub(r"[.,;:!?]+$", "", s)
        return s.strip()

    @staticmethod
    def semantic_similarity(a: str, b: str) -> float:
        """Character-level similarity ratio (0-1)."""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @classmethod
    def objects_are_semantically_equal(cls, obj_a: str, obj_b: str, threshold: float = 0.82) -> bool:
        """Return True if two object strings mean the same thing.

        Uses a numeric guard: if both strings contain numbers and those
        number sets differ, the objects are NOT equal — even when the
        surrounding text is very similar (e.g. '$8M in 2021' vs '$5M in 2021').
        """
        a = cls._normalise_object(obj_a)
        b = cls._normalise_object(obj_b)
        if a == b:
            return True

        # Numeric guard — different numbers means different facts
        nums_a = cls._extract_numbers(obj_a)
        nums_b = cls._extract_numbers(obj_b)
        if nums_a and nums_b and nums_a != nums_b:
            return False

        return SequenceMatcher(None, a, b).ratio() >= threshold

