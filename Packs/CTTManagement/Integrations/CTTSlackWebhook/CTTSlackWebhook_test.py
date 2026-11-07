import pytest
from CommonServerPython import DemistoException
from CTTSlackWebhook import build_payload, validate_url


def test_build_payload_fills_all_variables():
    assert build_payload("msg_person", "hi", slack_user_id="U1", default_user_id="U0", default_channel_id="C0") == {
        "action": "msg_person",
        "slack_user_id": "U1",
        "slack_channel_id": "C0",
        "content": "hi",
        "fixed_url": "-",
        "not_violation_url": "-",
        "issue_url": "-",
    }
    canvas = build_payload("canvas_update", "# Status", default_user_id="U0", default_channel_id="C0")
    assert canvas["slack_user_id"] == "U0"
    assert canvas["slack_channel_id"] == "C0"


@pytest.mark.parametrize(
    "action,user,content,message",
    [
        ("shout", "", "x", "Unknown action"),
        ("msg_person", "", "x", "needs slack_user_id"),
        ("channel_update_topic", "", "", "content is empty"),
        ("channel_update_topic", "", "topic", "placeholder user ID"),
    ],
)
def test_build_payload_rejects(action, user, content, message):
    with pytest.raises(DemistoException, match=message):
        build_payload(action, content, user)


def test_validate_url():
    assert validate_url("https://hooks.slack.com/triggers/X/1/abc") == "ok"
    with pytest.raises(DemistoException):
        validate_url("https://example.com/hook")


def test_build_payload_url_key_only_when_given():
    assert "url" not in build_payload("msg_person", "hi", "U1", default_channel_id="C0")
    assert build_payload("msg_person", "hi", "U1", default_channel_id="C0", url="https://t/1")["url"] == "https://t/1"


def test_health_issue_dm_carries_the_three_button_urls():
    buttons = {"fixed_url": "https://t/f", "not_violation_url": "https://t/n", "issue_url": "https://t/i"}
    payload = build_payload("msg_person_health_issue", "hi", "U1", default_channel_id="C0", buttons=buttons)
    assert payload["action"] == "msg_person_health_issue"
    assert {k: payload[k] for k in buttons} == buttons


def test_health_issue_dm_needs_every_button_url():
    with pytest.raises(DemistoException, match="not_violation_url, issue_url"):
        build_payload("msg_person_health_issue", "hi", "U1", default_channel_id="C0", buttons={"fixed_url": "https://t/f"})
