# Eldon Land Supply — Top 100 Action Allowlist

## What This Is

The formal catalog of the highest-value recurring actions OpenClaw is authorized to automate, draft, recommend, schedule, or surface across Eldon Land Supply.

This is not a list of people or domains.
This is a list of approved operational actions ranked by their business impact.

---

## Four Buckets

| Bucket | Slots | Purpose |
|---|---|---|
| `CEO_LEVERAGE` | 25 | Protect and amplify CEO time, decisions, and focus |
| `REVENUE_ACCELERATION` | 30 | Pipeline, proposals, collections, relationships |
| `ADMIN_ELIMINATION` | 20 | Remove repetitive low-value work from everyone |
| `EXECUTION_CONTROL` | 25 | Track, follow up, escalate, prevent dropped balls |

---

## Files

| File | Purpose |
|---|---|
| `action_schema.json` | Canonical field definitions and validation rules |
| `top_100_actions.json` | All ranked approved and enabled actions |
| `top_100_actions.csv` | Spreadsheet view of above |
| `action_candidates.json` | Detected patterns not yet formalized |
| `action_backlog.json` | Disqualified actions awaiting fixes |
| `action_checklist.json` | Items blocking action enablement |
| `action_checklist.csv` | Spreadsheet view of above |
| `audit_log.jsonl` | Append-only execution log |
| `config.yaml` | System configuration |

---

## Scripts

```powershell
# Validate all actions against schema
python .\scripts\validate_actions.py

# Score and rank all actions
python .\scripts\score_actions.py

# Generate checklist items for gaps
python .\scripts\generate_checklist.py

# Export CSV views
python .\scripts\export_views.py

# Detect automation candidates from logs
python .\scripts\capture_candidates.py --log-path data\audit_log.jsonl
```

---

## Adding a New Action

1. Add entry to `top_100_actions.json` with status `proposed`
2. Run `validate_actions.py` — fix any schema errors
3. Run `score_actions.py` — check composite score and rank
4. Run `generate_checklist.py` — see what fields are missing
5. Fix gaps, change status to `approved`
6. CEO reviews and sets `enabled: true` when ready

---

## Execution Modes

| Mode | Meaning |
|---|---|
| `auto_execute` | Runs automatically. Risk score must be ≤4. |
| `draft_then_review` | Creates draft, waits for human approval before any send/commit |
| `recommend_only` | Surfaces suggestion to human. No system action taken. |
| `approval_required` | Halts until named approver confirms. |
| `manual_only` | Generates prompt only. Human does the work. |

---

## Governance

See `docs/governance.md` for complete rules.

**Immutable rules:**
- No action auto-sends email without CEO pre-authorization
- No action modifies financial records without `approval_required` mode
- Every execution logged to `audit_log.jsonl`
- Dry run is the default system state

---

## Monthly Review

First Monday of each month:
1. Run `score_actions.py` — full re-rank
2. Run `generate_checklist.py` — surface new gaps
3. CEO reviews top 10 actions
4. Disqualified actions reviewed for resolution or archive
5. Candidates reviewed for formalization
