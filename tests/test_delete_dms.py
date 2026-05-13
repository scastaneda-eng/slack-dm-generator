"""Tests for delete_dms.delete_one — the probe-and-delete logic."""
from unittest.mock import MagicMock, patch

import pytest
from slack_sdk.errors import SlackApiError

import delete_dms


def _slack_error(code):
    response = MagicMock()
    response.get.side_effect = lambda key, default=None: {"error": code}.get(key, default)
    response.headers = {}
    return SlackApiError(message=code, response=response)


@pytest.fixture
def fake_user_client(mocker):
    """Patch user_client to return a fresh MagicMock for each call."""
    client = MagicMock()
    client.chat_postMessage.return_value = {"channel": "D123", "ts": "9999.0001"}
    client.chat_delete.return_value = {"ok": True}
    mocker.patch.object(delete_dms, "user_client", return_value=client)
    return client


def test_happy_path_deletes_target_and_probe(fake_user_client):
    ok, info = delete_dms.delete_one("alice@x.com", "U01ABCDEFGH", "1234.5678")

    assert ok is True
    assert info == "D123"
    fake_user_client.chat_postMessage.assert_called_once_with(channel="U01ABCDEFGH", text=".")
    # Target first, then probe cleanup.
    assert fake_user_client.chat_delete.call_args_list[0].kwargs == {"channel": "D123", "ts": "1234.5678"}
    assert fake_user_client.chat_delete.call_args_list[1].kwargs == {"channel": "D123", "ts": "9999.0001"}


def test_probe_post_failure_returns_false(fake_user_client):
    fake_user_client.chat_postMessage.side_effect = _slack_error("channel_not_found")

    ok, info = delete_dms.delete_one("alice@x.com", "U01ABCDEFGH", "1234.5678")

    assert ok is False
    assert "probe post failed" in info
    assert "channel_not_found" in info
    fake_user_client.chat_delete.assert_not_called()


def test_target_delete_fails_but_probe_cleanup_succeeds(fake_user_client):
    fake_user_client.chat_delete.side_effect = [_slack_error("message_not_found"), {"ok": True}]

    ok, info = delete_dms.delete_one("alice@x.com", "U01ABCDEFGH", "1234.5678")

    assert ok is False
    assert "chat.delete failed" in info
    assert "message_not_found" in info


def test_target_succeeds_but_probe_cleanup_fails(fake_user_client):
    fake_user_client.chat_delete.side_effect = [{"ok": True}, _slack_error("not_authed")]

    ok, info = delete_dms.delete_one("alice@x.com", "U01ABCDEFGH", "1234.5678")

    assert ok is False
    assert "probe cleanup failed" in info
    assert "not_authed" in info


def test_both_deletes_fail_warns_about_orphan_probe(fake_user_client):
    fake_user_client.chat_delete.side_effect = [
        _slack_error("message_not_found"),
        _slack_error("not_authed"),
    ]

    ok, info = delete_dms.delete_one("alice@x.com", "U01ABCDEFGH", "1234.5678")

    assert ok is False
    assert "orphan probe message" in info
    assert "message_not_found" in info
    assert "not_authed" in info
