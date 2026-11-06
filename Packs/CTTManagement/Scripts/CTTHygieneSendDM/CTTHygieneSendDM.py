import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import textwrap
from datetime import UTC, datetime

NOTIFY_STATE = "CTT - Notify State"
WIDTH = 46  # fits a Slack code block on a phone without wrapping


def wrap_body(text: str, width: int = WIDTH) -> str:
    """Wrap the message to the box width; bullets get a hanging indent, blank lines stay."""
    out = []
    for line in (text or "").strip().splitlines():
        line = line.rstrip()
        if not line:
            out.append("")
        elif line.lstrip().startswith(("• ", "- ", "* ")):
            item = "• " + line.lstrip()[2:].strip()
            out.extend(textwrap.wrap(item, width, subsequent_indent="  ") or [item])
        else:
            out.extend(textwrap.wrap(line, width) or [line])
    return "\n".join(out)


def header(left: str, right: str, width: int = WIDTH) -> str:
    inner = width - 2
    text = f"  {left}"
    text = text + " " * max(1, inner - len(text) - len(right) - 2) + right + "  "
    return "\n".join(["╭" + "─" * inner + "╮", "│" + text[:inner].ljust(inner) + "│", "╰" + "─" * inner + "╯"])


def build_dm(guideline_id: str, body: str, issue_id: str, url: str) -> str:
    """ASCII layout for the code block the CTT workflow puts a DM in: header box, the message, a
    footer with the issue number and the link (also sent separately when the instance allows)."""
    url = url or ""
    body = body.replace(url, "").rstrip() if url else body
    parts = [
        header("CTT HYGIENE", guideline_id or "CTT"),
        "",
        wrap_body(body),
        "",
        "─" * WIDTH,
        f"Issue #{issue_id} · assigned to you" if issue_id else "Issue assigned to you",
    ]
    if url:
        parts.append(url)
    return "\n".join(parts)


def usable_ai_message(message: str) -> bool:
    """False for an empty or cut-off AI answer (its last line does not end a sentence)."""
    lines = [line.strip() for line in (message or "").strip().splitlines() if line.strip()]
    return bool(lines) and lines[-1][-1] in ".?!)\"'"


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
        if not slack_id:
            raise DemistoException("No Slack ID to send to.")
        message = args.get("message") or ""
        body = message.strip() if usable_ai_message(message) else (args.get("fallback_message") or "").strip()
        url = args.get("issue_url", "")
        content = build_dm(args.get("guideline_id", ""), body, args.get("issue_id", ""), url)
        res = demisto.executeCommand(
            "ctt-slack-webhook-send", {"action": "msg_person", "slack_user_id": slack_id, "content": content, "url": url}
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
                readable_output=f"Sent this Slack DM to {owner} ({slack_id}):\n\n```\n{content}\n```",
                outputs_prefix="CTT.DM",
                outputs={"owner": owner, "slack_id": slack_id, "content": content},
            )
        )
    except Exception as e:
        return_error(f"CTTHygieneSendDM failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
