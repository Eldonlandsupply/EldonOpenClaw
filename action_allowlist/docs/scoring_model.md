# Top 100 Action Scoring Model

## Purpose

Every action in the allowlist must earn its place. The scoring model provides a deterministic, auditable ranking that answers one question:

> Of all possible things OpenClaw could automate or surface, which 100 produce the most value for Eldon Land Supply?

---

## Scoring Formula

```
composite_score = (
    (profit_impact_score * 2.5)
  + (value_score        * 2.0)
  + (frequency_score    * 1.5)
  + (time_saved_score   * 1.5)
  + (confidence_score   * 1.0)
  - (risk_score         * 2.0)
) / 10.5
```

All input scores are integers 1–10. Composite score range: ~0–10.

### Weight Rationale

| Factor | Weight | Reasoning |
|---|---|---|
| profit_impact | 2.5x | Revenue and cost avoidance is the point of the company |
| value_score | 2.0x | Overall strategic value beyond pure profit |
| frequency | 1.5x | High-frequency automations compound their savings |
| time_saved | 1.5x | Executive and org time is a hard constraint |
| confidence | 1.0x | Unproven value claims should not rocket up the list |
| risk | -2.0x | High-risk actions are penalized aggressively |

### Risk Penalty Detail

Risk score measures the consequence of the action going wrong:

| Risk Score | Meaning |
|---|---|
| 1–2 | Low: worst case is an awkward email or wasted compute |
| 3–4 | Moderate: could cause confusion, require cleanup |
| 5–6 | High: could damage relationship, delay project, or expose data |
| 7–10 | Critical: financial, legal, or reputational harm possible |

Actions with risk_score ≥ 7 are automatically ineligible for `auto_execute` mode.
Actions with risk_score ≥ 9 require `approval_required` or `manual_only` mode.

---

## Bucket Allocation

The Top 100 is divided into four hard buckets:

| Bucket | Slots | Description |
|---|---|---|
| CEO_LEVERAGE | 25 | Actions that directly protect, amplify, or optimize CEO time and decisions |
| REVENUE_ACCELERATION | 30 | Actions tied to pipeline, collections, proposals, relationships, and deal velocity |
| ADMIN_ELIMINATION | 20 | Actions that remove repetitive or low-value work from the organization |
| EXECUTION_CONTROL | 25 | Actions that track, follow up, escalate, and prevent dropped balls |

Rationale: Revenue-facing actions get the most slots because that is where the money is. CEO leverage is second because CEO capacity is the binding constraint on company speed.

---

## Tiebreaker Rules

When two actions have equal composite scores:

1. Higher `profit_impact_score` wins
2. Higher `frequency_score` wins
3. Lower `risk_score` wins
4. Earlier `action_id` wins (stability)

---

## Disqualification Rules

An action is disqualified from the Top 100 if any of the following are true:

- `status` not in `[approved, enabled]`
- `owner` is null or blank
- `trigger_definition` is null or vague (e.g., "when needed")
- `required_inputs` is empty and action is not `recommend_only`
- `execution_mode` is `auto_execute` and `risk_score >= 7`
- `confidence_score <= 3`

These are not soft suggestions. A disqualified action goes to `action_backlog.json` with a checklist item to fix the gap.

---

## Re-ranking Cadence

- Full re-rank: monthly (first Monday)
- Triggered re-rank: on any new action added, any action status change, or any score change
- Score changes require a note in the `notes` field with date and reason

---

## Anti-Gaming Rules

- An action cannot jump more than 20 rank positions in a single review cycle without a written justification in `notes`
- Actions in the top 10 undergo manual CEO review at each monthly cycle
- Any action with `profit_impact_score = 10` that has not been executed in 90 days gets a review flag
