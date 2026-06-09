## Presentation

[Trust-Aware Memory Intelligence System.pdf](https://github.com/user-attachments/files/28749568/Trust-Aware.Memory.Intelligence.System.pdf)

---
# 🧠 Trust-Aware Memory Intelligence System
### GenAI Hackathon — Multi-Agent Memory Pipeline

---

## Overview

A **multi-agent AI system** that ingests a stream of noisy, conflicting, and evolving claims and transforms them into a structured, provenance-aware memory store that improves over time.

The system answers: _"Why do I believe this fact right now, and how has that belief changed over time?"_

---

## Architecture

```
Claims Stream (JSONL)
        │
        ▼
┌─────────────────────┐
│  Claim Extractor    │  Parses & normalises each claim, handles null timestamps
│  Agent              │  Detects semantic duplicates (e.g. "$5M" vs "five million")
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Verification Agent │  Scores trustworthiness:
│                     │  confidence = source_reliability × label_weight
│                     │  Penalises NOT VERIFIABLE, missing timestamps
└─────────┬───────────┘
          │
          ▼
┌──────────────────────────┐
│ Contradiction Detection  │  Classifies: NOVEL | DUPLICATE | CORROBORATION
│ Agent                    │            | CONTRADICTION | EQUAL_CONFLICT
└─────────┬────────────────┘
          │
          ▼
┌─────────────────────┐
│  Memory Curator     │  Decides: ACCEPTED | MERGED | UPDATED
│  Agent              │          DOWNGRADED | REJECTED | FORGOTTEN
└─────────┬───────────┘
          │
          ▼
   memory_store.json   ←→   change_log.json   ←→   pipeline_trace.json
          │
          ▼
   Streamlit Dashboard (dashboard.py)
```

---

## File Structure

```
Hkthn/
├── agents/
│   ├── __init__.py
│   ├── claim_extractor.py        # Agent 1: Parse & normalise
│   ├── verification_agent.py     # Agent 2: Trust scoring
│   ├── contradiction_detector.py # Agent 3: Conflict classification
│   └── memory_curator.py         # Agent 4: Memory decisions
├── memory/
│   ├── __init__.py
│   └── memory_store.py           # JSON-backed store + provenance queries
├── main.py                       # Pipeline orchestrator
├── dashboard.py                  # Streamlit UI
├── requirements.txt
├── claims 1 1 (1).jsonl          # Input dataset (50 claims)
├── schema 1 1.json               # Schema reference
└── README.md
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the pipeline
```bash
python main.py
```
This will create:
- `memory_store.json` — Current state of all memory entries
- `change_log.json`   — Every decision the system made, with reasoning
- `pipeline_trace.json` — Per-claim diagnostic trace

### 3. Launch the dashboard
```bash
streamlit run dashboard.py
```

---

## Memory Entry Schema

| Field | Type | Description |
|---|---|---|
| `subject` | string | Entity the fact is about |
| `predicate` | string | Relationship / property |
| `object` | string | Asserted value |
| `confidence` | float 0–1 | How strongly we believe this |
| `status` | enum | `active` / `outdated` / `rejected` / `low_confidence` / `forgotten` |
| `sources` | list | Source IDs that support this value |
| `first_seen` | ISO8601 | When first observed |
| `last_updated` | ISO8601 | Last modification time |
| `corroboration_count` | int | Independent sources agreeing |

---

## Change Log Actions

| Action | When |
|---|---|
| `ACCEPTED` | New fact, credible source, no conflict |
| `MERGED` | Semantically equivalent claim from new source (confidence boosted) |
| `UPDATED` | Higher-confidence source provides a new value |
| `DOWNGRADED` | Credible contradiction reduces existing confidence |
| `REJECTED` | Low-trust or low-confidence contradicting claim |
| `FORGOTTEN` | Memory overflow eviction of weakest low-confidence entries |

---

## Decision Rules

### Confidence Calculation
```
initial_confidence = source_reliability × label_weight
  where label_weight: SUPPORTS=1.0, REFUTES=0.6, NOT ENOUGH INFO=0.4

adjusted_confidence = initial_confidence
  × 0.5  (if NOT VERIFIABLE)
  × 0.9  (if timestamp missing)
```

### Curator Decision Tree
```
Is it a DUPLICATE?          → REJECT (no memory change)
Is it CORROBORATION?        → MERGE  (confidence boosted by diminishing returns)
Is it NOVEL?
  └─ trustworthy + SUPPORTS → ACCEPT as active
  └─ low trust / NEI        → ACCEPT as low_confidence
  └─ REFUTES with no prior  → REJECT
Is it CONTRADICTION?
  └─ REFUTES claim
      └─ untrusted source   → REJECT (ignore)
      └─ trusted source     → DOWNGRADE existing
  └─ SUPPORTS claim
      └─ new conf > old     → UPDATE  (old → outdated)
      └─ new conf < old     → REJECT  new claim
Is it EQUAL_CONFLICT?       → DOWNGRADE both sides
Memory overflow?            → FORGET weakest low_confidence entries
```

---

## Dashboard Tabs

| Tab | What you see |
|---|---|
| 🧠 Memory Explorer | Filterable card view of all memory entries with confidence bars |
| 📜 Change Log | Colour-coded timeline of every decision with Δ confidence |
| 🔍 Provenance Viewer | Select any subject+predicate → full belief evolution + line chart |
| 📊 Analytics | Action & status distributions, confidence histogram, source table |
| 💡 Explain Belief | Natural-language explanation: "Why do I believe X right now?" |

---

## Edge Cases Handled

| Edge Case | Handling |
|---|---|
| Same fact, different wording | Semantic similarity (SequenceMatcher ≥ 0.82) → MERGED |
| Repeated contradictions | Each assessed independently; low-trust ones REJECTED |
| High-confidence incorrect claims | Threat score computed; only downgraded if credible |
| Missing timestamps | Sorted last, confidence penalised ×0.9 |
| Equal-confidence conflicts | EQUAL_CONFLICT → both sides downgraded |
| Adversarial inputs | source_reliability < 0.30 → ADVERSARIAL verdict → REJECTED |
| Memory overflow | Weakest `low_confidence` entries (conf < 0.20) FORGOTTEN |
