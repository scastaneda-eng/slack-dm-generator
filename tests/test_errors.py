"""Tests for friendly_slack_error()."""
from unittest.mock import MagicMock

from slack_sdk.errors import SlackApiError

from errors import friendly_slack_error


def _err(code):
    response = MagicMock()
    response.get.side_effect = lambda key, default=None: {"error": code}.get(key, default)
    return SlackApiError(message=code, response=response)


def test_known_code_includes_hint():
    msg = friendly_slack_error(_err("token_revoked"))
    assert msg.startswith("token_revoked — ")
    assert "auth_user.py" in msg


def test_unknown_code_passes_through_bare():
    msg = friendly_slack_error(_err("some_brand_new_error"))
    assert msg == "some_brand_new_error"


def test_missing_error_field_returns_unknown():
    response = MagicMock()
    response.get.side_effect = lambda key, default=None: default
    err = SlackApiError(message="?", response=response)
    assert friendly_slack_error(err) == "unknown"
