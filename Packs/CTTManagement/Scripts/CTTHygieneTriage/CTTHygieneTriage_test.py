from CTTHygieneTriage import (
    DAY_MS,
    compose,
    decide,
    fallback_message,
    find_duplicate,
    find_owner,
    object_key,
    owner_entry,
    owner_tags,
    rename_target,
    strip_marker,
)

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


def test_owner_tags_primary_first():
    assert owner_tags(REGISTRY, "j@x.com") == "jvanhecke, jva"
    assert owner_tags(REGISTRY, "") == ""


def test_rename_target():
    assert rename_target("Playbook", "Local Analysis", "jva") == "jva - Local Analysis"
    assert rename_target("Script", "GetUsers", "jva") == "jva_GetUsers"
    assert rename_target("POLICY_PROFILES", "SF - Labs", "sfi") == "sfi - Labs"


def test_compose_tag_rule():
    details = (
        "j@x.com created Playbook 'Local Analysis alert Investigation_copy': no tag prefix. "
        "Rename it to start with your own tag (guideline CTT-TAG-01)."
    )
    found, fix = compose("CTT-TAG-01", "Object created without owner tag", details, ["jvanhecke", "jva"], "20")
    assert found == 'Playbook "Local Analysis alert Investigation_copy" was created without your tag prefix.'
    assert fix == ['Rename it to "jvanhecke - Local Analysis alert Investigation_copy"', "Or use another of your tags: jva"]


def test_compose_owner_rule():
    details = "b@x.com ran 'Edit - Playbook' on Playbook 'jva - Demo', which belongs to j@x.com (guideline CTT-OWN-01)."
    found, fix = compose("CTT-OWN-01", "Another owner's object changed", details, ["bob"], "")
    assert found == 'You ran "Edit - Playbook" on Playbook "jva - Demo", which belongs to j@x.com.'
    assert fix[0] == "Ask j@x.com before changing their objects"


def test_compose_sweep_and_lab():
    details = (
        "The inventory check found 2 item(s) for owner j@x.com that break guideline CTT-TAG-01.\n"
        "- Script 'A': no tag prefix\n- Job 'B': no tag prefix"
    )
    found, fix = compose("CTT-TAG-01", "Objects without a registered owner tag (j@x.com)", details, ["jva"], "")
    assert found == "The inventory check found 2 item(s): Script 'A': no tag prefix; Job 'B': no tag prefix."
    assert fix == ['Rename each one with your tag, for example "jva - <name>"']
    found, fix = compose(
        "CTT-LAB-01",
        "Endpoint outside owner's lab range",
        "Endpoint PC1: IP 10.9.1.2 is in an unassigned lab range. Move it into your own range.",
        ["jva"],
        "20",
    )
    assert found == "Endpoint PC1: IP 10.9.1.2 is in an unassigned lab range."
    assert fix == ["Move it into your lab range 10.20.0.0/16 or 172.16.20.0/24"]


def test_compose_policy_scope():
    details = (
        "jva@x.com saved Policy rule 'jva - lab': it targets endpoint name = lnx-2.europe-west1-b.c.prod.internal "
        "instead of your endpoint tag. Scope policies to endpoints that carry your own tag (guideline CTT-TAG-02)."
    )
    found, fix = compose("CTT-TAG-02", "Policy rule not scoped by your tag", details, ["jva"], "")
    assert found == (
        'Policy rule "jva - lab" is not scoped by your tag: it targets endpoint name = '
        "lnx-2.europe-west1-b.c.prod.internal instead of your endpoint tag."
    )
    assert fix[0] == "Change its target to endpoints tagged jva"


LAB = "CTT - Hygiene - CTT-LAB-01 - Endpoint outside owner's lab range"
LAB_TEXT = "Endpoint PC1: IP 10.9.1.2 is in an unassigned lab range. Move it into your own range. [owner: j@x.com]"
NOW = 1_794_200_000_000


def test_object_key():
    assert object_key(LAB, LAB_TEXT) == ("CTT-LAB-01|endpoint|pc1", "endpoint PC1")
    gen = "CTT - Hygiene - CTT-GEN-01 - Active user not in registry"
    assert object_key(gen, "Bob@X.com signed in 3 times but has no registry row.")[0] == "CTT-GEN-01|user|bob@x.com"
    tag = "CTT - Hygiene - CTT-TAG-01 - Object created without owner tag"
    assert object_key(tag, "j@x.com created playbook 'My PB': no tag prefix.") == (
        "CTT-TAG-01|playbook|My PB",
        "playbook 'My PB'",
    )
    # Inventory check issues keep one issue per guideline and owner themselves.
    assert object_key("CTT - Hygiene - CTT-TAG-01 - Objects without a registered tag", "The inventory check found 3 items") == (
        "",
        "",
    )


def test_find_duplicate_open_issue():
    others = [
        {"id": 62180, "name": LAB, "description": LAB_TEXT.replace("10.9.1.2", "10.9.1.3"), "status.progress": "In Progress"},
        {
            "id": 61000,
            "name": LAB,
            "description": "Endpoint PC2: IP 10.9.1.9 is in an unassigned lab range.",
            "status.progress": "New",
        },
    ]
    dup, note = find_duplicate("62190", LAB, LAB_TEXT, others, NOW, 30)
    assert dup == "62180" and note.startswith("Duplicate of issue #62180, which is still open for the same endpoint PC1")
    # Only an older issue counts, so the first of a pair is never closed as a duplicate of the second.
    assert find_duplicate("62170", LAB, LAB_TEXT, others, NOW, 30) == ("", "")


def test_find_duplicate_false_positive_window():
    fp = {
        "id": 60000,
        "name": LAB,
        "description": LAB_TEXT,
        "status.progress": "Resolved",
        "status.resolution_reason": "RESOLVED_FALSE_POSITIVE",
        "resolution_status_modified_ts": NOW - 5 * DAY_MS,
    }
    dup, note = find_duplicate("62190", LAB, LAB_TEXT, [fp], NOW, 30)
    assert dup == "60000" and "marked a false positive on" in note and "30 days" in note
    assert find_duplicate("62190", LAB, LAB_TEXT, [fp], NOW, 3) == ("", "")
    fixed = dict(fp, **{"status.resolution_reason": "RESOLVED_OTHER"})
    assert find_duplicate("62190", LAB, LAB_TEXT, [fixed], NOW, 30) == ("", "")
