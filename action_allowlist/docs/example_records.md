# Example Action Records

---

## 1. Approved High-Value Action (auto_execute)

```json
{
  "action_id": "ACT-0002",
  "action_name": "daily_priority_brief",
  "action_category": "CEO_LEVERAGE",
  "action_description": "Generate a structured daily brief at 6:30 AM: top 3 decisions, top 3 revenue risks, top 3 open commitments, calendar summary.",
  "execution_mode": "auto_execute",
  "status": "enabled",
  "risk_score": 1,
  "composite_score": 8.4,
  "rank": 2,
  "owner": "OpenClaw",
  "trigger_type": "scheduled",
  "trigger_definition": "Daily at 06:30 local time"
}
```

Why this works: Low risk, high frequency, saves CEO time daily, requires no human input, fully auditable.

---

## 2. Draft-Only Action

```json
{
  "action_id": "ACT-0001",
  "action_name": "stale_deal_followup_prompt",
  "action_category": "REVENUE_ACCELERATION",
  "action_description": "Detect deals with no activity in 7+ days. Draft follow-up email. Surface for CEO review. Never auto-sends.",
  "execution_mode": "draft_then_review",
  "status": "approved",
  "risk_score": 2,
  "composite_score": 8.1,
  "owner": "CEO",
  "approver": "CEO"
}
```

Why draft-only: External emails carry relationship risk. CEO must approve tone and timing.

---

## 3. Approval-Required Action

```json
{
  "action_id": "ACT-0008",
  "action_name": "contract_expiry_alert",
  "action_category": "EXECUTION_CONTROL",
  "action_description": "Alert on contracts expiring in 90/60/30 days. Generate renewal checklist. Escalate to CEO at 30-day mark.",
  "execution_mode": "approval_required",
  "status": "approved",
  "risk_score": 2,
  "owner": "Operations",
  "approver": "CEO",
  "escalation_path": "CEO at 30 days"
}
```

Why approval-required: Contract renewals have financial and legal consequences. CEO must explicitly authorize the renewal process.

---

## 4. Rejected Low-Value Action

```json
{
  "action_id": "ACT-REJECTED-001",
  "action_name": "auto_organize_downloads_folder",
  "action_category": "ADMIN_ELIMINATION",
  "action_description": "Automatically sort files in the downloads folder into subfolders by type.",
  "status": "rejected",
  "rejection_reason": "Zero business impact. Saves <5 min/month. Creates risk of misplaced files. Not worth the dependency or maintenance overhead.",
  "rejected_at": "2025-01-15",
  "rejected_by": "CEO"
}
```

Rule applied: Activity ≠ value. Reject any action where the primary beneficiary is tidiness, not business outcomes.

---

## 5. Candidate Action (Needs Definition)

```json
{
  "candidate_id": "CAND-0042",
  "pattern_label": "crm_update_automation",
  "detection_count": 7,
  "status": "proposed",
  "detected_at": "2025-01-15T09:00:00Z",
  "notes": "Pattern 'update CRM' detected 7 times in 30 days via manual requests. Review for formalization.",
  "missing_before_approval": [
    "define exact trigger condition",
    "confirm CRM write permissions and connector",
    "assign owner",
    "define success metric",
    "risk assessment for CRM record mutation"
  ]
}
```

---

## 6. Checklist Item

```json
{
  "checklist_item_id": "CL-00091",
  "action_id": "ACT-0021",
  "action_name": "lead_routing_and_prioritization",
  "task_type": "confirm_dependencies",
  "task_description": "ACT-0021 depends on crm_connector which is not yet integrated. Confirm CRM API access and test read capability before enabling.",
  "severity": "critical",
  "status": "open",
  "assigned_to": "Operations",
  "blocker_type": "missing_integration",
  "blocker_description": "crm_connector not yet implemented in OpenClaw",
  "evidence_needed": "Successful test read from CRM API",
  "required_integration": "crm_connector",
  "created_at": "2025-01-15T08:00:00Z",
  "due_date": "2025-01-18",
  "resolution_notes": ""
}
```

---

## 7. Audit Log Entry

```jsonl
{"ts":"2025-01-15T06:30:01Z","action_id":"ACT-0002","action_name":"daily_priority_brief","trigger":"scheduled","mode":"auto_execute","outcome":"success","output_summary":"Brief delivered: 3 decisions [contract renewal, vendor deadline, stale deal ACT-0001], 2 risks [permit stall day 11, invoice overdue $14k], 4 open commitments","approved_by":null,"execution_ms":1240}
```
