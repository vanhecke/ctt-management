from CTTOwnerIndex import DAY_MS, HOUR_MS, OWNER_QUERY, merge, window_ms


def test_query_is_generated():
    assert "dataset = management_auditing" in OWNER_QUERY
    assert "comp earliest(actor) as first_actor" in OWNER_QUERY


def test_merge_keeps_known_creator_and_takes_new_editor():
    existing = [
        {
            "object_kind": "Agent installer",
            "object_name": "jva-win",
            "creator": "a@x.com",
            "last_editor": "a@x.com",
            "last_change": "2026-01-01T00:00:00Z",
        }
    ]
    fresh = [
        {
            "object_kind": "Agent installer",
            "object_name": "jva-win",
            "creator": "",
            "last_editor": "b@x.com",
            "last_change": "2026-11-06T09:00:00Z",
        }
    ]
    assert merge(existing, fresh) == [
        {
            "object_kind": "Agent installer",
            "object_name": "jva-win",
            "creator": "a@x.com",
            "last_editor": "b@x.com",
            "last_change": "2026-11-06T09:00:00Z",
        }
    ]


def test_merge_skips_unchanged_and_nameless_rows():
    row = {
        "object_kind": "Policy rule",
        "object_name": "jva - lab",
        "creator": "a@x.com",
        "last_editor": "a@x.com",
        "last_change": "2026-11-06T09:00:00Z",
    }
    assert merge([row], [dict(row)]) == []
    assert merge([], [{"object_kind": "Policy rule", "object_name": "", "creator": "a@x.com"}]) == []


def test_merge_adds_new_objects():
    fresh = [
        {
            "object_kind": "Playbook",
            "object_name": "FW Alert Triage",
            "creator": "a@x.com",
            "last_editor": "a@x.com",
            "last_change": "t",
        }
    ]
    assert merge([], fresh)[0]["creator"] == "a@x.com"


def test_window():
    assert window_ms(False, True, 365, 3) == 3 * HOUR_MS
    assert window_ms(True, True, 365, 3) == 365 * DAY_MS
    assert window_ms(False, False, 365, 3) == 365 * DAY_MS
