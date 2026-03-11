# Eldon Land Supply — Top 100 Action Allowlist

The formal catalog of the highest-value recurring actions OpenClaw is authorized to execute, draft, or recommend across Eldon Land Supply.

## Purpose
- What should OpenClaw do automatically?
- What should it draft but not send?
- What should it recommend to humans?
- What recurring work should be eliminated?

## Four Buckets
| Bucket | Focus |
|---|---|
| ceo_leverage | Protect and multiply CEO time and attention |
| revenue_acceleration | Move pipeline faster, close gaps, protect cash |
| admin_elimination | Remove recurring manual burden from the operation |
| execution_control | Ensure projects, deals, and commitments execute on time |

## Quick Start
```bash
cd action_allowlist

# Score and rank actions
python3 scripts/score_actions.py

# Validate all actions against schema
python3 scripts/validate_actions.py

# Generate checklist items for incomplete actions
python3 scripts/generate_checklist.py

# Export to CSV for review
python3 scripts/export_views.py

# Capture a new candidate action
python3 scripts/capture_candidates.py "Action Name" "Description" "category"
```

## Top 5 by Composite Score
1. Invoice Follow-Up (8.95)
2. Proposal Follow-Up Reminder (8.75)
3. Stale Deal Detection (8.70)
4. Daily Priority Brief (8.65)
5. Missing Signature Alert (8.15)

## Files
- `top_100_actions.json` — canonical action records
- `action_checklist.json` — auto-generated checklist for incomplete actions
- `action_backlog.json` — captured candidate actions awaiting review
- `audit_log.jsonl` — execution audit trail
- `config.yaml` — system configuration and safety gates
