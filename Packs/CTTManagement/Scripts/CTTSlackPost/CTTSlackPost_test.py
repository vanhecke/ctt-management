import pytest
from CTTSlackPost import CUT_NOTE, prepare, send_args


def test_prepare_turns_literal_backslash_n_into_line_breaks():
    assert prepare("Title\\n\\nLine one\\nLine two") == "Title\n\nLine one\nLine two"


def test_prepare_keeps_real_line_breaks_and_trims_blank_edges():
    assert prepare("\nTitle\r\nLine\n\n") == "Title\nLine"


def test_prepare_cuts_long_messages_with_a_note():
    text = prepare("x" * 5000, max_chars=100)
    assert len(text) <= 100
    assert text.endswith(CUT_NOTE)


def test_prepare_rejects_empty_messages():
    with pytest.raises(Exception, match="empty"):
        prepare("  \\n ")


def test_send_args_uses_the_instance_channel_unless_given():
    assert send_args("hi") == {"action": "msg_channel", "content": "hi"}
    assert send_args("hi", "C123")["slack_channel_id"] == "C123"
