# Action Scoring Model

## Composite Score Formula

```
composite = (
    profit_impact_score * 0.30
  + time_saved_score    * 0.20
  + frequency_score     * 0.15
  + value_score         * 0.15
  + confidence_score    * 0.10
  + (10 - risk_score)   * 0.10
)
```

Penalties:
- execution_mode == manual_only: -2.0
- no owner assigned: -1.5
- no trigger_definition: -1.0

Score range: 0–10. Top 100 maintained by composite score descending.

## Weight Rationale
Profit impact weighted heaviest (30%) — this is a profit-maximization system, not an activity tracker.
Time saved second (20%) — executive leverage is the primary mechanism for profit impact.
Frequency third (15%) — high-frequency automations compound in value.
Risk inverted (10%) — penalizes risky automations that require oversight.
