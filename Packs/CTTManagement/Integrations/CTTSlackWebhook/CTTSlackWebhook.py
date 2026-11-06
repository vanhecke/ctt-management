import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

ACTIONS = ("msg_person", "msg_channel", "channel_update_topic", "canvas_update")
URL_PREFIX = "https://hooks.slack.com/"


def build_payload(
    action: str,
    content: str,
    slack_user_id: str = "",
    slack_channel_id: str = "",
    default_user_id: str = "",
    default_channel_id: str = "",
    url: str = "",
) -> dict:
    """The Slack workflow types its inputs and rejects an empty user or channel ID
    (invalid_workflow_input), even for actions that ignore them. Unused IDs are filled with the
    instance's channel ID and placeholder user ID; the workflow acts only on the ones it needs."""
    if action not in ACTIONS:
        raise DemistoException(f"Unknown action '{action}'. Use one of: {', '.join(ACTIONS)}.")
    if not content:
        raise DemistoException("content is empty.")
    if action == "msg_person" and not slack_user_id:
        raise DemistoException("msg_person needs slack_user_id.")
    user = slack_user_id or default_user_id
    channel = slack_channel_id or default_channel_id
    if not user or not channel:
        raise DemistoException("Set the instance's channel ID and placeholder user ID: the workflow needs both on every call.")
    payload = {"action": action, "slack_user_id": user, "slack_channel_id": channel, "content": content}
    if url:
        payload["url"] = url
    return payload


def validate_url(url: str) -> str:
    if not (url or "").startswith(URL_PREFIX):
        raise DemistoException(f"The webhook URL must start with {URL_PREFIX}")
    return "ok"


class Client(BaseClient):
    def send(self, payload: dict) -> dict:
        res = self._http_request("POST", full_url=self._base_url, json_data=payload, resp_type="response", ok_codes=(200,))
        try:
            return res.json()
        except ValueError:
            return {"ok": True, "raw": res.text[:200]}


def send_command(
    client: Client, args: dict, default_user_id: str, default_channel_id: str, send_url: bool = False
) -> CommandResults:
    payload = build_payload(
        args.get("action", ""),
        args.get("content", ""),
        args.get("slack_user_id", ""),
        args.get("slack_channel_id", ""),
        default_user_id,
        default_channel_id,
        args.get("url", "") if send_url else "",
    )
    reply = client.send(payload)
    if isinstance(reply, dict) and reply.get("ok") is False:
        raise DemistoException(f"Slack refused the workflow call: {reply.get('error')}")
    target = payload["slack_user_id"] if payload["action"] == "msg_person" else payload["slack_channel_id"]
    return CommandResults(
        readable_output=f"Slack workflow action **{payload['action']}** sent to {target} ({len(payload['content'])} characters).",
        outputs_prefix="CTTSlackWebhook.Sent",
        outputs={"action": payload["action"], "target": target, "reply": reply},
    )


def main():  # pragma: no cover
    params = demisto.params()
    url = (params.get("url") or {}).get("password") if isinstance(params.get("url"), dict) else params.get("url")
    command = demisto.command()
    try:
        if command == "test-module":
            # Validates the URL only: a real call would send a Slack message.
            return_results(validate_url(url))
        elif command == "ctt-slack-webhook-send":
            validate_url(url)
            client = Client(base_url=url, verify=not params.get("insecure"), proxy=params.get("proxy"))
            return_results(
                send_command(
                    client,
                    demisto.args(),
                    params.get("placeholder_user_id", ""),
                    params.get("channel_id", ""),
                    argToBoolean(params.get("send_url_key", False)),
                )
            )
        else:
            raise NotImplementedError(f"Command {command} is not implemented.")
    except Exception as e:
        return_error(f"CTT Slack Webhook: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
