from CTTHygieneTriage import compose, decide, fallback_message, find_owner, owner_entry, owner_tags, rename_target, strip_marker

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
    assert fix == [
        'Rename it to "jvanhecke - Local Analysis alert Investigation_copy"',
        "Or add jvanhecke to the playbook's Tags field; then the name needs no prefix",
        "Or use another of your tags: jva",
    ]
    script = "j@x.com created Script 'GetUsers': no tag prefix. Rename it to start with your own tag (guideline CTT-TAG-01)."
    _, fix = compose("CTT-TAG-01", "Object created without owner tag", script, ["jvanhecke"], "20")
    assert fix == [
        'Rename it to "jvanhecke_GetUsers"',
        "Or add jvanhecke to the script's Tags field; then the name needs no prefix",
    ]


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


def test_compose_inventory_policy_and_endpoints():
    tag02 = (
        "The inventory check found 1 item(s) for owner s@x.com that break guideline CTT-TAG-02.\n"
        "- Policy rule 'SF - Labs': its scope targets endpoint in PC1, not one of the owner's tags\n[owner: s@x.com]"
    )
    _, fix = compose("CTT-TAG-02", "Owner tag missing from a tag field or policy scope", tag02, ["sfi"], "")
    assert fix == ["Scope each policy rule to your endpoint tag (target: endpoint tag sfi) instead of endpoint names"]
    lab02 = (
        "The inventory check found 1 item(s) for owner s@x.com that break guideline CTT-LAB-02.\n"
        "- Endpoint 'PC1': no registered endpoint or server tag\n[owner: s@x.com]"
    )
    found, fix = compose("CTT-LAB-02", "Endpoints without an owner tag", lab02, ["sfi"], "")
    assert found == "The inventory check found 1 item(s): Endpoint 'PC1': no registered endpoint or server tag."
    assert fix[0] == "Add sfi as an endpoint tag on each endpoint (Endpoints > All Endpoints > Endpoint Tags)"


def test_compose_groups_inventory_items():
    """Items of one kind with the same finding share a line; a shared owner reason is said once."""
    details = (
        "The inventory check found 4 item(s) for owner s@x.com that break guideline CTT-LAB-02.\n"
        + "".join(
            f"- Endpoint '{n}': no registered endpoint or server tag; owner: creator of installer XDR_Windows\n"
            for n in ("PC1", "PC2", "PC3", "PC4")
        )
        + "[owner: s@x.com]"
    )
    found, _ = compose("CTT-LAB-02", "Endpoints without an owner tag", details, ["sfi"], "")
    assert found == (
        "The inventory check found 4 item(s): Endpoints 'PC1', 'PC2', 'PC3', 'PC4': no registered endpoint or server tag."
        " Why you: creator of installer XDR_Windows."
    )
    mixed = (
        "The inventory check found 3 item(s) for owner s@x.com that break guideline CTT-TAG-01.\n"
        "- Policy profile 'SF - Labs': prefix 'sf' is not a registered tag\n"
        "- Policy rule 'SF - Labs': prefix 'sf' is not a registered tag\n"
        "- Policy rule 'SF - Test': prefix 'sf' is not a registered tag\n[owner: s@x.com]"
    )
    found, _ = compose("CTT-TAG-01", "Objects without a registered owner tag", mixed, ["sfi"], "")
    assert found == (
        "The inventory check found 3 item(s): Policy profile 'SF - Labs': prefix 'sf' is not a registered tag;"
        " Policy rules 'SF - Labs', 'SF - Test': prefix 'sf' is not a registered tag."
    )
