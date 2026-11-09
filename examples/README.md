# Examples

Use these scripts to send and clean up demo DMs. Copy and edit the
[one-message example](send_messages.example.json) for your first run.

| Script | What it does |
|---|---|
| `send_dms_as_users.py` | Send a list of DMs from different personas to a single recipient. Reads the message list from a JSON file. |
| `delete_dms.py` | Delete previously-sent DMs. Reads `(sender_email, ts)` tuples from a JSON file (e.g., the manifest written by `send_dms_as_users.py`). |

## The probe-and-delete trick (important if you write your own delete script)

A persona's user token has `chat:write` but **not** `im:read` or `im:write`.
That means it cannot call `conversations.open` or `im.list` to find the DM
channel ID — but `chat.delete` requires both `channel` and `ts`.

Workaround: post a one-character throwaway message via `chat.postMessage`
with `channel=<recipient_user_id>`. Slack auto-resolves the DM channel and
returns its ID in the response. Then call `chat.delete` on both the throwaway
and the real target. See `delete_dms.py` for the implementation.

## Usage

```bash
# 1. Write a JSON file describing what to send (see send_messages.example.json)
# 2. Send:
.venv/bin/python examples/send_dms_as_users.py --config send_messages.json --manifest demo-test-cleanup.json

# 3. Later, to delete:
.venv/bin/python examples/delete_dms.py --manifest demo-test-cleanup.json
```

Keep the cleanup file and give each batch a new filename. Sending again to
the same path replaces its previous cleanup record.
