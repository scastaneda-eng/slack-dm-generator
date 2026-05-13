"""Tests for send_dms_as_users.send_one — recipient ID validation + send path."""
from unittest.mock import MagicMock

import pytest

import send_dms_as_users


@pytest.fixture
def fake_user_client(mocker):
    client = MagicMock()
    client.chat_postMessage.return_value = {"channel": "D123", "ts": "1234.5678"}
    mocker.patch.object(send_dms_as_users, "user_client", return_value=client)
    return client


def test_happy_path_returns_manifest_entry(fake_user_client):
    entry = send_dms_as_users.send_one("alice@x.com", "U01ABCDEFGH", "hello")

    assert entry == {
        "sender_email": "alice@x.com",
        "recipient_user_id": "U01ABCDEFGH",
        "channel_id": "D123",
        "ts": "1234.5678",
    }


def test_rejects_lowercase_recipient_id(fake_user_client):
    with pytest.raises(RuntimeError, match="doesn't look like a Slack user ID"):
        send_dms_as_users.send_one("alice@x.com", "u01abcdefgh", "hi")
    fake_user_client.chat_postMessage.assert_not_called()


def test_rejects_channel_id_as_recipient(fake_user_client):
    with pytest.raises(RuntimeError, match="doesn't look like a Slack user ID"):
        send_dms_as_users.send_one("alice@x.com", "C0123456789", "hi")


def test_accepts_workspace_id_prefix(fake_user_client):
    """Enterprise Grid uses W-prefixed IDs; the regex should accept them."""
    entry = send_dms_as_users.send_one("alice@x.com", "W01ABCDEFGH", "hi")
    assert entry["recipient_user_id"] == "W01ABCDEFGH"
