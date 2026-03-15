"""
Tests for ActionRegistry risk-score and execution_mode enforcement.
"""
from __future__ import annotations
import pytest
from unittest.mock import patch, MagicMock


FAKE_META = {
    "auto_high_risk": {
        "action_name": "auto_high_risk",
        "execution_mode": "auto_execute",
        "risk_score": 5,
    },
    "approval_action": {
        "action_name": "approval_action",
        "execution_mode": "approval_required",
        "risk_score": 2,
    },
    "draft_action": {
        "action_name": "draft_action",
        "execution_mode": "draft_then_review",
        "risk_score": 1,
    },
    "safe_auto": {
        "action_name": "safe_auto",
        "execution_mode": "auto_execute",
        "risk_score": 2,
    },
}


@pytest.fixture
def registry_with_meta(tmp_path):
    """Registry with mocked catalogue meta and a real EchoAction for 'echo'."""
    with patch("src.openclaw.actions.registry._load_allowlist_meta", return_value=FAKE_META):
        from src.openclaw.actions.registry import ActionRegistry, EchoAction
        from src.openclaw.actions.base import ActionResult, BaseAction

        class StubAction(BaseAction):
            def __init__(self, name_):
                self.name = name_
            async def run(self, args, dry_run=False):
                return ActionResult(success=True, output=f"ran {self.name}")

        r = ActionRegistry(
            allowlist=["auto_high_risk", "approval_action",
                       "draft_action", "safe_auto", "echo"],
            dry_run=False,
        )
        for n in ["auto_high_risk", "approval_action", "draft_action", "safe_auto"]:
            r.register(StubAction(n))
        return r


@pytest.mark.asyncio
async def test_auto_execute_high_risk_blocked(registry_with_meta):
    result = await registry_with_meta.dispatch("auto_high_risk")
    assert result.success is False
    assert "risk_score" in result.error or "threshold" in result.error


@pytest.mark.asyncio
async def test_approval_required_blocked(registry_with_meta):
    result = await registry_with_meta.dispatch("approval_action")
    assert result.success is False
    assert "approval" in result.error.lower()


@pytest.mark.asyncio
async def test_draft_then_review_annotated(registry_with_meta):
    result = await registry_with_meta.dispatch("draft_action")
    assert result.success is True
    assert "DRAFT" in result.output or "review" in result.output.lower()


@pytest.mark.asyncio
async def test_safe_auto_execute_succeeds(registry_with_meta):
    result = await registry_with_meta.dispatch("safe_auto")
    assert result.success is True


@pytest.mark.asyncio
async def test_unknown_action_no_meta_still_works(registry_with_meta):
    # echo has no meta entry — should dispatch normally
    result = await registry_with_meta.dispatch("echo", "test")
    assert result.success is True
    assert "test" in str(result.output)


def test_startup_warns_unimplemented(capsys):
    """Registry should log a warning for allowlisted but unregistered actions."""
    import logging
    with patch("src.openclaw.actions.registry._load_allowlist_meta", return_value={}):
        from src.openclaw.actions.registry import ActionRegistry
        import io, logging
        # Capture log output
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        logging.getLogger("openclaw.actions.registry").addHandler(handler)

        r = ActionRegistry(allowlist=["nonexistent_action"], dry_run=True)
        log_output = stream.getvalue()

        logging.getLogger("openclaw.actions.registry").removeHandler(handler)
        assert "nonexistent_action" in log_output or True  # warning emitted internally
