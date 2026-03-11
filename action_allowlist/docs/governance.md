# Action Allowlist Governance Rules

## Immutable Rules (Override Nothing)

1. **No action auto-sends email without CEO review** unless explicitly designated `auto_execute` by CEO in writing.
2. **No action modifies financial records** without `approval_required` mode.
3. **No action is deployed as `enabled`** without passing schema validation and scoring threshold.
4. **Every execution is logged** to `audit_log.jsonl`. No silent runs.
5. **Dry run is the default**. `auto_execute` is an explicit opt-in per action, not a system-wide default.

---

## Execution Mode Rules

### auto_execute
- Risk score must be ≤ 4
- Owner must be `OpenClaw`
- No external sends without CEO pre-authorization
- Must have a `failure_metric` defined

### draft_then_review
- Draft is created and queued, never sent without human approval
- Draft must be surfaced within the SLA in `success_metric`
- Stale drafts (>48h unreviewed) generate an escalation

### recommend_only
- System surfaces the recommendation; human decides and acts
- No downstream system is modified
- System records whether recommendation was acted upon

### approval_required
- System halts and presents to approver
- Approver must be a named human, not `OpenClaw`
- Timeout behavior: escalate to CEO after 24h

### manual_only
- System does not attempt any execution
- System may generate a checklist or reminder prompt
- Used for high-risk or relationship-sensitive actions

---

## Action Lifecycle

```
proposed → under_review → approved → enabled
                       → rejected
                       → archived

enabled → paused → enabled
enabled → deprecated → archived
```

- `proposed`: Candidate from backlog or human request
- `under_review`: CEO or operations is evaluating
- `approved`: Validated against schema and governance; not yet running
- `enabled`: Live and executing
- `paused`: Temporarily disabled (with reason and resume date)
- `deprecated`: Being phased out; no new runs
- `rejected`: Evaluated and not accepted (with reason)
- `archived`: Historical record only

---

## Review Requirements

| Condition | Action Required |
|---|---|
| Any `auto_execute` action | CEO review every 30 days |
| Any action with risk_score ≥ 6 | CEO sign-off before enable |
| Action not executed in 90 days | Status review |
| Failure metric triggered | Immediate review |
| Score change > 20 ranks | Written justification required |
| Integration dependency changes | Re-validate before next run |

---

## Failure Handling

All action failures are logged with:
- `action_id`
- `failure_timestamp`
- `failure_reason`
- `input_state` (sanitized, no secrets)
- `attempted_execution_mode`

Failures in `auto_execute` mode trigger:
1. Immediate fallback to `draft_then_review`
2. Alert to `owner`
3. Escalation to CEO if failure repeats 3+ times

---

## What OpenClaw Must Never Do Without Human Approval

- Send any external email
- Modify CRM records
- Submit or cancel any document
- Make any financial entry
- Contact any external party
- Schedule or cancel any meeting
- Delete or archive any data

Attempts to do any of the above without approval are logged as governance violations and surfaced in the daily brief.

---

## Audit Requirements

Every action execution records:
- `action_id`
- `execution_timestamp`
- `execution_mode_used`
- `trigger_source`
- `inputs_received`
- `output_summary` (not full content — summaries only)
- `human_approved_by` (if applicable)
- `outcome` (success | failure | partial)

Audit log is append-only. No modification of prior entries.
