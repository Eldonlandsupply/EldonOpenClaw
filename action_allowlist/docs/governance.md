# Action Allowlist Governance

## Execution Mode Rules

| Mode | Rule |
|---|---|
| auto_execute | Risk score ≤ 3. No external sends. No financial commits. Logged always. |
| draft_then_review | Output staged for human review before any send. |
| recommend_only | OpenClaw surfaces recommendation. Human decides and acts. |
| approval_required | Named approver must confirm before execution. |
| manual_only | OpenClaw does not execute. Human task only. |

## High-Risk Rules
- Actions with risk_score ≥ 8 cannot be auto_execute — hard block in validator.
- External email sends require draft_then_review minimum.
- Financial transactions require approval_required minimum.
- Contract execution requires approval_required minimum.

## Lifecycle
proposed → under_review → approved → enabled → (paused | deprecated | archived)

Actions can be rejected at any stage. Rejection requires a reason in notes.

## Review Cadence
- All enabled actions reviewed every 30 days.
- Actions not executed in 30 days flagged for deprecation review.
- New candidates reviewed within 7 days of capture.

## Audit
Every execution logged to audit_log.jsonl with: action_id, timestamp, mode, input_summary, output_summary, executed_by, approved_by.
