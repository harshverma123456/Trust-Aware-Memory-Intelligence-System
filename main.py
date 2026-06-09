"""
main.py — Trust-Aware Memory Intelligence System
-------------------------------------------------
Orchestrates the full 4-agent pipeline:
  1. ClaimExtractorAgent
  2. VerificationAgent
  3. ContradictionDetectorAgent
  4. MemoryCuratorAgent

Reads  : claims 1 1 (1).jsonl
Writes : memory_store.json
         change_log.json
         pipeline_trace.json   (per-claim trace for debugging / dashboard)
"""

from __future__ import annotations

# ── Fix Windows cp1252 Unicode issues ───────────────────────────────────────
import sys, io
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import json
import os
from datetime import datetime, timezone

from agents.claim_extractor import ClaimExtractorAgent
from agents.verification_agent import VerificationAgent
from agents.contradiction_detector import ContradictionDetectorAgent
from agents.memory_curator import MemoryCuratorAgent
from memory.memory_store import MemoryStore


# ── Config ───────────────────────────────────────────────────────────────────

CLAIMS_FILE    = "claims 1 1 (1).jsonl"
STORE_FILE     = "memory_store.json"
LOG_FILE       = "change_log.json"
TRACE_FILE     = "pipeline_trace.json"


# ── Helpers ───────────────────────────────────────────────────────────────────

def load_claims(path: str) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def print_banner():
    print("=" * 65)
    print("  Trust-Aware Memory Intelligence System")
    print("  GenAI Hackathon 2024")
    print("=" * 65)


def print_claim_result(idx: int, claim_id: str, subject: str,
                       predicate: str, obj: str,
                       action: str, verification_verdict: str):
    # Use plain ASCII-safe markers instead of ANSI escape codes
    ACTION_MARKERS = {
        "ACCEPTED":   "[+]",
        "MERGED":     "[~]",
        "UPDATED":    "[^]",
        "DOWNGRADED": "[v]",
        "REJECTED":   "[x]",
        "FORGOTTEN":  "[_]",
        "NOOP":       "[ ]",
    }
    marker = ACTION_MARKERS.get(action, "[?]")
    # Sanitise strings — replace any non-encodable chars
    safe_obj     = obj[:35].encode("utf-8", errors="replace").decode("utf-8")
    safe_subject = subject[:20].encode("utf-8", errors="replace").decode("utf-8")
    print(
        f"  [{idx:02d}] {claim_id:5s} | {marker} {action:10s} | "
        f"[{verification_verdict:14s}] | {safe_subject:20s} | {safe_obj}"
    )


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_pipeline(claims_path: str = CLAIMS_FILE):
    print_banner()

    # Initialise agents and shared stores
    extractor   = ClaimExtractorAgent()
    verifier    = VerificationAgent()
    detector    = ContradictionDetectorAgent()
    mem_store   = MemoryStore(STORE_FILE, LOG_FILE)
    # Start fresh — the pipeline processes the full JSONL each run,
    # so loading previous state would cause duplicate/inflated entries.
    mem_store.store.clear()
    mem_store.log.clear()

    curator     = MemoryCuratorAgent(mem_store.store, mem_store.log)

    # Load & sort claims by timestamp (nulls go last)
    raw_claims = load_claims(claims_path)
    print(f"\n  Loaded {len(raw_claims)} claims from '{claims_path}'\n")

    # Pre-parse to sort (nulls last)
    parsed = []
    for raw in raw_claims:
        ts = raw.get("timestamp")
        sort_key = ts if ts else "9999"
        parsed.append((sort_key, raw))
    parsed.sort(key=lambda x: x[0])

    trace = []   # Full per-claim trace for the dashboard

    print(f"  {'#':>3}  {'ID':5s}  {'Action':10s}  {'Verdict':14s}  {'Subject':20s}  Object")
    print("  " + "-" * 80)

    for idx, (_, raw) in enumerate(parsed, 1):
        # ── Agent 1: Extract ─────────────────────────────────────────────
        claim = extractor.extract(raw)

        # ── Agent 2: Verify ──────────────────────────────────────────────
        verification = verifier.verify(claim)

        # ── Agent 3: Detect contradictions ───────────────────────────────
        conflict = detector.detect(claim, verification, mem_store.store)

        # ── Agent 4: Curate memory ────────────────────────────────────────
        action = curator.curate(claim, verification, conflict)

        # ── Console output ────────────────────────────────────────────────
        print_claim_result(
            idx, claim.id, claim.subject, claim.predicate, claim.object,
            action, verification.verdict,
        )

        # ── Trace record ──────────────────────────────────────────────────
        trace.append({
            "index": idx,
            "claim_id": claim.id,
            "timestamp": claim.timestamp.isoformat(),
            "timestamp_missing": claim.timestamp_missing,
            "source_id": claim.source_id,
            "source_reliability": claim.source_reliability,
            "label": claim.label,
            "verifiable": claim.verifiable,
            "claim_text": claim.claim,
            "subject": claim.subject,
            "predicate": claim.predicate,
            "object": claim.object,
            "initial_confidence": claim.initial_confidence,
            "adjusted_confidence": verification.adjusted_confidence,
            "verification_verdict": verification.verdict,
            "verification_flags": verification.flags,
            "conflict_relationship": conflict.relationship,
            "conflict_details": conflict.details,
            "existing_best_object": conflict.existing_best_object,
            "existing_best_confidence": conflict.existing_best_confidence,
            "action": action,
        })

    # ── Save outputs ──────────────────────────────────────────────────────────
    mem_store.save()
    with open(TRACE_FILE, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2, default=str)

    # ── Summary ───────────────────────────────────────────────────────────────
    stats = mem_store.summary_stats()
    print("\n" + "=" * 65)
    print("  PIPELINE COMPLETE")
    print("=" * 65)
    print(f"  Total memory entries : {stats['total_entries']}")
    print(f"  By status            : {stats['by_status']}")
    print(f"  Total change log     : {stats['total_log_entries']}")
    print(f"  By action            : {stats['by_action']}")
    print(f"\n  Outputs written:")
    print(f"    {STORE_FILE}")
    print(f"    {LOG_FILE}")
    print(f"    {TRACE_FILE}")
    print()

    # ── Explain a few key facts ───────────────────────────────────────────────
    print("=" * 65)
    print("  BELIEF EXPLANATIONS (sample)")
    print("=" * 65)
    for subject, predicate in [
        ("Startup A", "raised funding of"),
        ("GreenTech Corp", "was founded in"),
        ("Adrienne Bailon", "is a"),
        ("Homeland", "is based on"),
        ("Roman Atwood", "has"),
    ]:
        print()
        explanation = mem_store.explain(subject, predicate)
        # Sanitise for cp1252 terminals (fallback encoding)
        safe_explanation = explanation.encode("utf-8", errors="replace").decode("utf-8")
        print(safe_explanation)
        print("-" * 65)

    return mem_store


if __name__ == "__main__":
    claims_path = sys.argv[1] if len(sys.argv) > 1 else CLAIMS_FILE
    run_pipeline(claims_path)
