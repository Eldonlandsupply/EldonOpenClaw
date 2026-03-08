import pytest
from src.openclaw.messaging.config import MessagingConfig
from src.openclaw.messaging.notifier import Notifier
from src.openclaw.messaging.policy import MessagePolicy
from src.openclaw.messaging.templates import render

RECIPIENT = "+15555555555"

def make_config(**overrides):
    defaults = dict(
        enabled=True,
        provider="log_only",
        allowed_recipients=[RECIPIENT],
        rate_limit_per_hour=10,
        dedup_window_minutes=15,
        kill_switch=False,
    )
    defaults.update(overrides)
    return MessagingConfig(**defaults)

def test_render_test_template():
    assert render("test") == "[OpenClaw] Test alert: system wired correctly"

def test_render_critical_alert():
    out = render("critical_alert", message="disk full")
    assert "CRITICAL" in out and "disk full" in out

def test_render_unknown_template():
    with pytest.raises(ValueError):
        render("nonexistent")

def test_policy_allows_valid():
    p = MessagePolicy(make_config())
    ok, reason = p.allow(RECIPIENT, "hello")
    assert ok

def test_policy_blocks_kill_switch():
    p = MessagePolicy(make_config(kill_switch=True))
    ok, _ = p.allow(RECIPIENT, "hello")
    assert not ok

def test_policy_blocks_disabled():
    p = MessagePolicy(make_config(enabled=False))
    ok, _ = p.allow(RECIPIENT, "hello")
    assert not ok

def test_policy_blocks_non_allowlisted():
    p = MessagePolicy(make_config())
    ok, _ = p.allow("+19999999999", "hello")
    assert not ok

def test_policy_dedup():
    p = MessagePolicy(make_config())
    p.record_send(RECIPIENT, "hello")
    ok, reason = p.allow(RECIPIENT, "hello")
    assert not ok
    assert "duplicate" in reason

def test_policy_rate_limit():
    p = MessagePolicy(make_config(rate_limit_per_hour=2))
    p.record_send(RECIPIENT, "msg1")
    p.record_send(RECIPIENT, "msg2")
    ok, reason = p.allow(RECIPIENT, "msg3")
    assert not ok
    assert "rate limit" in reason

def test_notifier_send_test_template():
    n = Notifier.from_config(make_config())
    result = n.send("test")
    assert result is True

def test_notifier_blocked_when_disabled():
    n = Notifier.from_config(make_config(enabled=False))
    result = n.send("test")
    assert result is False

def test_notifier_dedup_suppression():
    n = Notifier.from_config(make_config())
    n.send("info", message="hello")
    result = n.send("info", message="hello")
    assert result is False
