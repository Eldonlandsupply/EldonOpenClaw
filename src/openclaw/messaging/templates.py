from datetime import datetime

TEMPLATES = {
    "critical_alert": "[OpenClaw] CRITICAL: {message}",
    "approval_needed": "[OpenClaw] Approval needed: {message}",
    "daily_update": "[OpenClaw] Daily update ({date}): {message}",
    "task_complete": "[OpenClaw] Task complete: {message}",
    "error_report": "[OpenClaw] Error: {message}",
    "info": "[OpenClaw] {message}",
    "test": "[OpenClaw] Test alert: system wired correctly",
}

def render(template_name: str, **kwargs) -> str:
    if template_name not in TEMPLATES:
        raise ValueError(f"Unknown template: {template_name}. Available: {list(TEMPLATES.keys())}")
    kwargs.setdefault("date", datetime.now().strftime("%Y-%m-%d"))
    return TEMPLATES[template_name].format(**kwargs)
