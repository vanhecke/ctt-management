import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
from datetime import UTC, datetime

NOTIFY_STATE = "CTT - Notify State"


def pick_message(message: str, fallback: str, url: str) -> str:
    """The AI-written message when there is one, else the template; always ends with the link."""
    text = (message or "").strip() or (fallback or "").strip()
    if url and url not in text:
        text = f"{text}\n{url}"
    return text


def bump(state: dict, day: str, owner: str) -> dict:
    """Count today's DMs per owner; older days are dropped."""
    today = dict(state.get(day, {}))
    today[owner] = int(today.get(owner, 0)) + 1
    return {day: today}


def main():  # pragma: no cover
    try:
        args = demisto.args()
        slack_id = args.get("slack_user_id", "")
        owner = (args.get("owner_email") or "").lower()
        content = pick_message(args.get("message", ""), args.get("fallback_message", ""), args.get("issue_url", ""))
        if not slack_id:
            raise DemistoException("No Slack ID to send to.")
        res = demisto.executeCommand(
            "ctt-slack-webhook-send", {"action": "msg_person", "slack_user_id": slack_id, "content": content}
        )
        if is_error(res):
            raise DemistoException(f"ctt-slack-webhook-send failed: {get_error(res)}")
        day = datetime.now(UTC).strftime("%Y-%m-%d")
        state_res = demisto.executeCommand("getList", {"listName": NOTIFY_STATE})
        try:
            state = json.loads(state_res[0]["Contents"]) if not is_error(state_res) else {}
        except (ValueError, KeyError, TypeError):
            state = {}
        payload = json.dumps(bump(state if isinstance(state, dict) else {}, day, owner))
        if is_error(demisto.executeCommand("setList", {"listName": NOTIFY_STATE, "listData": payload})):
            demisto.executeCommand("createList", {"listName": NOTIFY_STATE, "listData": payload})
        return_results(
            CommandResults(
                readable_output=f"Sent this Slack DM to {owner} ({slack_id}):\n\n{content}",
                outputs_prefix="CTT.DM",
                outputs={"owner": owner, "slack_id": slack_id, "content": content},
            )
        )
    except Exception as e:
        return_error(f"CTTHygieneSendDM failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
