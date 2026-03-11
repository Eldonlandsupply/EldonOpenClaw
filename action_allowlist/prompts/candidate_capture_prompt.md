# Candidate Action Capture Prompt

When you observe work being done manually that matches these patterns, capture it as a candidate action:

1. Task is repeated more than twice in a month
2. Task follows a predictable pattern (same inputs, same output type)
3. Task consumes more than 15 minutes and produces a standard output
4. Task is being done reactively rather than proactively

To capture, call: `scripts/capture_candidates.py "Action Name" "Description" "category"`

Categories: ceo_leverage | revenue_acceleration | admin_elimination | execution_control

A captured candidate is NOT executed. It enters the backlog for human review.
