from CTTHygieneTriage import decide, fallback_message, find_owner, owner_entry, strip_marker

REGISTRY = [
    {"tag": "jva", "owner_email": "j@x.com", "owner_name": "Joris V", "slack_id": "U1", "role": "admin", "tag_kind": "extra"},
    {
        "tag": "jvanhecke",
        "owner_email": "j@x.com",
        "owner_name": "Joris V",
        "slack_id": "U1",
        "role": "admin",
        "tag_kind": "primary",
    },
    {"tag": "bob", "owner_email": "b@x.com", "owner_name": "Bob B", "slack_id": "U2", "role": "dc", "tag_kind": "primary"},
    {"tag": "nos", "owner_email": "n@x.com", "owner_name": "No Slack", "slack_id": "", "role": "dc", "tag_kind": "primary"},
]


def test_find_owner_from_marker_and_fields():
    assert find_owner({"details": "Something happened. [owner: J@X.com]"}) == "j@x.com"
    assert find_owner({"CustomFields": {"actor_effective_username": "b@x.com"}}) == "b@x.com"
    assert find_owner({"details": "no marker"}) == ""


def test_strip_marker():
    assert strip_marker("Text here. [owner: j@x.com]") == "Text here."


def test_owner_entry_prefers_primary_tag():
    assert owner_entry(REGISTRY, "j@x.com")["tag"] == "jvanhecke"
    assert owner_entry(REGISTRY, "zz@x.com") == {}


def test_decide():
    assert decide("unknown", {}, "all", 0, 3)[:2] == (False, False)
    assert decide("NULL".lower(), {}, "all", 0, 3)[:2] == (False, False)
    assert decide("z@x.com", {}, "all", 0, 3)[:2] == (True, False)
    assert decide("n@x.com", REGISTRY[3], "all", 0, 3)[:2] == (True, False)
    assert decide("b@x.com", REGISTRY[2], "off", 0, 3)[:2] == (True, False)
    assert decide("b@x.com", REGISTRY[2], "admins_only", 0, 3)[:2] == (True, False)
    assert decide("j@x.com", REGISTRY[1], "admins_only", 0, 3)[:2] == (True, True)
    assert decide("b@x.com", REGISTRY[2], "all", 3, 3)[:2] == (True, False)
    assert decide("b@x.com", REGISTRY[2], "all", 2, 3) == (True, True, "assigned and notified")
    assert decide("b@x.com", REGISTRY[2], "allowlist", 0, 3, ["j@x.com"])[:2] == (True, False)
    assert decide("j@x.com", REGISTRY[1], "allowlist", 0, 3, ["J@x.com"])[:2] == (True, True)


def test_fallback_message_shape():
    msg = fallback_message(
        "Bob", "Object created without owner tag", "Bob created Playbook 'X'.", "CTT-TAG-01", "Prefix object names"
    )
    assert msg.startswith("Hi Bob,")
    assert "*" not in msg
    assert "Fix:\n• Follow guideline CTT-TAG-01: Prefix object names." in msg
    assert "https://" not in msg
