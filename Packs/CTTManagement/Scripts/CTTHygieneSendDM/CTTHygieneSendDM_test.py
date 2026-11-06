from CTTHygieneSendDM import bump, pick_message


def test_pick_message_prefers_ai_text_and_adds_link():
    assert pick_message("Hi Bob, fix it.", "template", "https://t/1") == "Hi Bob, fix it.\nhttps://t/1"
    assert pick_message("Hi Bob.\nhttps://t/1", "template", "https://t/1") == "Hi Bob.\nhttps://t/1"
    assert pick_message("  ", "Template text https://t/1", "https://t/1") == "Template text https://t/1"


def test_bump_counts_today_and_drops_old_days():
    state = {"2026-11-05": {"b@x.com": 3}, "2026-11-06": {"b@x.com": 1}}
    assert bump(state, "2026-11-06", "b@x.com") == {"2026-11-06": {"b@x.com": 2}}
    assert bump(state, "2026-11-07", "j@x.com") == {"2026-11-07": {"j@x.com": 1}}
