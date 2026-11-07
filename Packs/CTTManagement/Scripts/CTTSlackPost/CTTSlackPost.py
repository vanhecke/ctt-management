import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

# Long messages are cut so one post stays readable in the channel; the full text belongs in
# Cortex (War Room, case or issue), not in Slack.
MAX_CHARS = 3900
CUT_NOTE = "\n… (cut: the full text is in Cortex)"


def prepare(message: str, max_chars: int = MAX_CHARS) -> str:
    """The text as Slack should show it. A War Room command passes "\\n" as two characters, so
    a literal backslash-n becomes a line break; scripts and playbooks pass real line breaks."""
    text = (message or "").replace("\r\n", "\n").replace("\\n", "\n").strip("\n")
    if not text.strip():
        raise DemistoException("message is empty.")
    if len(text) > max_chars:
        text = text[: max_chars - len(CUT_NOTE)].rstrip() + CUT_NOTE
    return text


def send_args(text: str, channel_id: str = "") -> dict:
    args = {"action": "msg_channel", "content": text}
    if channel_id:
        args["slack_channel_id"] = channel_id
    return args


def main():  # pragma: no cover
    args = demisto.args()
    try:
        text = prepare(args.get("message", ""))
        res = demisto.executeCommand("ctt-slack-webhook-send", send_args(text, (args.get("channel_id") or "").strip()))
        if is_error(res):
            raise DemistoException(get_error(res))
        sent = (res[0].get("EntryContext") or {}).get("CTTSlackWebhook.Sent") or {}
        channel = sent.get("target") if isinstance(sent, dict) else None
        return_results(
            CommandResults(
                readable_output=f"Posted {len(text)} characters to the CTT Slack channel{f' {channel}' if channel else ''}.",
                outputs_prefix="CTT.SlackPost",
                outputs={"channel": channel or args.get("channel_id") or "", "characters": len(text)},
            )
        )
    except Exception as e:
        return_error(f"CTTSlackPost: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
