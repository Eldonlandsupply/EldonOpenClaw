"""Tests for cross-connector message deduplication."""
from __future__ import annotations
import time


def test_first_message_not_duplicate():
    from src.openclaw.main import MessageDeduplicator
    d = MessageDeduplicator(window_s=60)
    assert d.is_duplicate("telegram", "hello") is False


def test_same_message_same_connector_duplicate():
    from src.openclaw.main import MessageDeduplicator
    d = MessageDeduplicator(window_s=60)
    d.is_duplicate("telegram", "hello")
    assert d.is_duplicate("telegram", "hello") is True


def test_same_message_different_connector_not_duplicate():
    from src.openclaw.main import MessageDeduplicator
    d = MessageDeduplicator(window_s=60)
    d.is_duplicate("telegram", "hello")
    assert d.is_duplicate("gmail", "hello") is False


def test_expired_message_not_duplicate():
    from src.openclaw.main import MessageDeduplicator
    d = MessageDeduplicator(window_s=1)
    d.is_duplicate("telegram", "hello")
    time.sleep(1.1)
    assert d.is_duplicate("telegram", "hello") is False
