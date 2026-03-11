# OpenClaw Runtime Behavior: Action Allowlist Integration

## Decision Logic (Every Message or Event)

```
1. Receive input (message, scheduled trigger, event)
2. Check: does an approved action exist for this?
   YES → check execution_mode → execute/draft/recommend/queue
   NO  → handle as LLM conversation
         → log pattern to candidate detection
3. Log outcome to audit_log.jsonl
4. If repeated manual pattern detected → flag as automation candidate
```

## Priority Order for Action Matching

1. Exact `action_name` match in allowlist
2. Keyword/pattern match against `trigger_definition`
3. Category match (e.g., "follow-up" → REVENUE_ACCELERATION)
4. Fall through to LLM (no action matched)

## Execution Mode Behavior at Runtime

| Mode | What OpenClaw Does |
|---|---|
| `auto_execute` | Runs the action and logs it. No human required. |
| `draft_then_review` | Generates output. Queues for review. Does NOT send or commit. |
| `recommend_only` | Surfaces the recommendation to the user. Logs whether acted on. |
| `approval_required` | Halts. Presents to `approver`. Escalates to CEO after 24h. |
| `manual_only` | Generates a task prompt or checklist item. Does not execute. |

## CEO Time Protection Logic

OpenClaw evaluates every inbound request against this filter before routing:

1. **Is this CEO-level?** (decision only CEO can make, relationship only CEO holds)
   → Surface to CEO immediately
2. **Can this be drafted and reviewed in <5 min by CEO?**
   → Draft it. Put in review queue.
3. **Can this be delegated?**
   → Route to appropriate owner with context.
4. **Is this informational only?**
   → Log it. Do not surface unless related to open critical item.
5. **Is this low-value busywork?**
   → Execute automatically or dismiss silently. Never surface to CEO.

## Candidate Detection Loop

OpenClaw passively monitors for:
- The same request type made ≥3 times in 30 days
- Any recurring task performed manually
- Any repeated admin burden described in conversation

When detected:
1. Create entry in `action_candidates.json`
2. Generate checklist item in `action_checklist.json`
3. Surface to CEO in next weekly brief: "3 new automation candidates identified this week"

## Audit Logging (Every Run)

Append to `audit_log.jsonl`:

```json
{
  "ts": "2025-01-15T08:00:01Z",
  "action_id": "ACT-0002",
  "action_name": "daily_priority_brief",
  "trigger": "scheduled",
  "mode": "auto_execute",
  "outcome": "success",
  "output_summary": "Brief delivered: 3 decisions, 2 risks, 4 open commitments",
  "approved_by": null
}
```

## What OpenClaw Must Surface vs. Suppress

**Always surface:**
- Critical blockers (permit stalls, overdue invoices >30 days, contract expiry <30 days)
- Approval requests pending >24h
- New high-value leads
- CEO commitments unactioned >7 days
- Budget overruns >20%

**Suppress and handle automatically:**
- Routine status checks
- Low-tier follow-up drafting
- Standard document reminders
- CRM hygiene tasks
- Routine meeting prep

**Never surface without context:**
- FYI emails
- Completed tasks
- Low-confidence detections
