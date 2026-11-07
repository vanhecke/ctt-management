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


def section(label: str, text: str, width: int = WIDTH, indent: int = 8) -> list[str]:
    """A labelled block: the label in the first 8 columns, the text wrapped beside it."""
    out = []
    for i, part in enumerate(t for t in (text or "").splitlines() if t.strip()):
        bullet = part.lstrip().startswith(("• ", "- "))
        part = "• " + part.lstrip()[2:] if bullet else part
        wrapped = textwrap.wrap(part, width - indent, subsequent_indent="  " if bullet else "") or [part]
        for j, line in enumerate(wrapped):
            lead = label.ljust(indent) if i == 0 and j == 0 else " " * indent
            out.append(lead + line)
    return out


def template_body(first_name: str, found: str, guideline_id: str, guideline_title: str, fix: str) -> str:
    """The deterministic DM: greeting, FOUND, RULE and FIX blocks."""
    fixes = "\n".join(f"• {f}" for f in (fix or "").splitlines() if f.strip())
    lines = [f"Hi {first_name or 'there'},", ""]
    lines += section("FOUND", found) + [""]
    lines += section("RULE", f"{guideline_id} · {guideline_title}".strip(" ·")) + [""]
    lines += section("FIX", fixes or "• See the issue for details")
    return "\n".join(lines)


def build_dm(
    guideline_id: str,
    body: str,
    issue_id: str,
    url: str,
    prewrapped: bool = False,
    note: str = "",
    links: dict | None = None,
    buttons: bool = False,
) -> str:
    """ASCII layout for the code block the CTT workflow puts a DM in: header box, an optional note
    (a re-ask after the owner said "fixed"), the message, and a footer. With answer links the footer
    says how to answer: the Fixed! / Not a violation buttons when the workflow shows them, else the
    links themselves."""
    url = url or ""
    links = {k: v for k, v in (links or {}).items() if v}
    body = body.replace(url, "").rstrip() if url else body
    parts = [header("CTT HYGIENE", guideline_id or "CTT"), ""]
    if note:
        parts += [wrap_body(note), ""]
    parts += [body if prewrapped else wrap_body(body), "", "─" * WIDTH]
    issue_line = f"Issue #{issue_id} · assigned to you" if issue_id else "Issue assigned to you"
    if links and buttons:
        parts += [
            wrap_body("Fixed it? Press Fixed! below. Intended or wrong? Press Not a violation."),
            "Checked guidelines also close by themselves.",
            issue_line,
        ]
    elif links:
        parts += [
            "Fixed it? Confirm here:",
            links.get("fixed", ""),
            "",
            "Not a violation? Tell us here:",
            links.get("not_violation", ""),
            "",
        ]
        parts += [issue_line] + ([url] if url else [])
    else:
        parts += ["Intended? Reply in the CTT channel.", issue_line] + ([url] if url else [])
    return "\n".join(p for p in parts if p is not None)


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
        url = args.get("issue_url", "")
        note = args.get("note") or ""
        links = {"fixed": args.get("fixed_url") or "", "not_violation": args.get("not_violation_url") or ""}
        has_links = all(links.values())
        buttons = has_links and argToBoolean(args.get("buttons") or "false") and bool(url)
        layout = {"note": note, "links": links if has_links else None, "buttons": buttons}
        if args.get("content"):
            # Already laid out by the caller (the case housekeeping and hygiene digests).
            content = args["content"]
        elif usable_ai_message(message):
            content = build_dm(args.get("guideline_id", ""), message.strip(), args.get("issue_id", ""), url, **layout)
        else:
            body = template_body(
                args.get("first_name", ""),
                args.get("found", ""),
                args.get("guideline_id", ""),
                args.get("guideline_title", ""),
                args.get("fix", ""),
            )
            content = build_dm(args.get("guideline_id", ""), body, args.get("issue_id", ""), url, prewrapped=True, **layout)
        send = {"action": "msg_person", "slack_user_id": slack_id, "content": content, "url": url}
        if buttons:
            send.update(
                action="msg_person_health_issue",
                fixed_url=links["fixed"],
                not_violation_url=links["not_violation"],
                issue_url=url,
            )
        res = demisto.executeCommand("ctt-slack-webhook-send", send)
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
