import CTTInventoryCheck
from CTTInventoryCheck import (
    collect_objects,
    find_owner,
    owner_index,
    reported_names,
    check_object,
    group_findings,
    inventory_entry,
    issue_body,
    parse_tag,
    plan,
    registry_index,
)

REGISTRY = registry_index(
    [
        {"tag": "alice", "owner_email": "alice@x.com", "role": "admin", "active": "true"},
        {"tag": "ali", "owner_email": "alice@x.com", "role": "admin", "active": "true"},
        {"tag": "bob", "owner_email": "bob@x.com", "role": "dc", "active": "false"},
        {"tag": "ctt", "owner_email": "", "role": "central", "active": "true"},
    ]
)


def test_parse_tag_separators():
    assert parse_tag("alice - Phishing") == "alice"
    assert parse_tag("alice_GetUsers") == "alice"
    assert parse_tag("SF-Labs") == "sf"
    assert parse_tag("TypeSafe Jev - Assessment") is None
    assert parse_tag("Untagged") is None


def test_untagged_object_uses_creator_as_owner():
    f = check_object({"kind": "Script", "name": "GetStuff", "creator": "Carol@x.com"}, REGISTRY)
    assert f == [
        {"kind": "Script", "name": "GetStuff", "guideline": "CTT-TAG-01", "owner": "carol@x.com", "detail": "no tag prefix"}
    ]


def test_unregistered_prefix():
    f = check_object({"kind": "Job", "name": "zed - nightly"}, REGISTRY)
    assert f[0]["owner"] == "unknown"
    assert "not a registered tag" in f[0]["detail"]


def test_playbook_tag_field_accepts_alias():
    ok = check_object({"kind": "Playbook", "name": "alice - Triage", "tags": ["ALI"]}, REGISTRY)
    missing = check_object({"kind": "Playbook", "name": "alice - Triage", "tags": ["demo"]}, REGISTRY)
    assert ok == []
    assert missing[0]["guideline"] == "CTT-TAG-02"


def test_central_playbook_needs_no_tag_field():
    assert check_object({"kind": "Playbook", "name": "CTT - Registry Sync", "tags": []}, REGISTRY) == []


def test_inactive_owner():
    f = check_object({"kind": "Script", "name": "bob_Thing"}, REGISTRY)
    assert [x["guideline"] for x in f] == ["CTT-LIFE-02"]


def test_group_and_plan():
    findings = [
        {"kind": "Script", "name": "a", "guideline": "CTT-TAG-01", "owner": "u", "detail": "no tag prefix"},
        {"kind": "Script", "name": "b", "guideline": "CTT-TAG-01", "owner": "u", "detail": "no tag prefix"},
    ]
    groups = group_findings(findings)
    key = "CTT-TAG-01|u"
    keys = groups[key]["keys"]
    assert list(groups) == [key]
    assert len(keys) == 2
    assert plan(groups, {}) == ([key], [], [])
    same = {key: {"fingerprint": groups[key]["fingerprint"], "keys": keys}, "CTT-CASE-01|x": {"keys": ["old"]}}
    assert plan(groups, same) == ([], ["CTT-CASE-01|x"], [])
    shrunk = {key: {"fingerprint": "older", "keys": [*keys, "deadbeef"]}}
    assert plan(groups, shrunk) == ([], [], [key])
    grew = {key: {"fingerprint": "older", "keys": keys[:1]}}
    assert plan(groups, grew) == ([key], [key], [])


def test_changing_detail_is_not_a_change():
    day1 = group_findings(
        [{"kind": "Case", "name": "#7 Lab", "guideline": "CTT-CASE-01", "owner": "u", "detail": "no change for 8 days"}]
    )
    day2 = group_findings(
        [{"kind": "Case", "name": "#7 Lab", "guideline": "CTT-CASE-01", "owner": "u", "detail": "no change for 9 days"}]
    )
    assert day1["CTT-CASE-01|u"]["fingerprint"] == day2["CTT-CASE-01|u"]["fingerprint"]


def test_issue_body():
    group = {"guideline": "CTT-TAG-01", "owner": "u@x.com", "items": [f"Script '{i}': no tag prefix" for i in range(70)]}
    issue = issue_body(group, 1)["request_data"]["issue"]
    assert issue["name"] == "CTT - Hygiene - CTT-TAG-01 - Objects without a registered owner tag (u@x.com)"
    assert issue["issue_domain"] == "Health"
    assert issue["severity"] == "MEDIUM"
    assert "and 10 more" in issue["description"]
    assert issue["description"].endswith("[owner: u@x.com]")


def test_inventory_entry():
    assert inventory_entry({"kind": "Script", "name": "ali_Thing"}, REGISTRY) == {
        "kind": "Script",
        "name": "ali_Thing",
        "tag": "ali",
        "owner": "alice@x.com",
    }
    assert inventory_entry({"kind": "Job", "name": "CTT - Sync"}, REGISTRY)["owner"] == "central"
    assert inventory_entry({"kind": "Script", "name": "Loose", "creator": "Z@x.com"}, REGISTRY)["owner"] == "z@x.com"


def test_system_creators_are_unknown():
    f = check_object({"kind": "Playbook", "name": "Old", "creator": "DBot@demisto.com", "tags": []}, REGISTRY)
    assert f[0]["owner"] == "unknown"


OWNERS = owner_index(
    [
        {
            "object_kind": "Integrations",
            "object_name": "Tor Exit Addresses Feed_instance_1",
            "creator": "",
            "last_editor": "bob@x.com",
        },
        {"object_kind": "Playbook", "object_name": "FW Alert Triage", "creator": "alice@x.com", "last_editor": ""},
        {"object_kind": "Playbook", "object_name": "Bot made", "creator": "DBot", "last_editor": ""},
    ]
)


def test_find_owner_prefers_the_api_creator():
    assert find_owner({"kind": "Playbook", "name": "FW Alert Triage", "creator": "carol@x.com"}, OWNERS) == "carol@x.com"


def test_find_owner_falls_back_to_the_audit_log():
    assert (
        find_owner({"kind": "Integration instance", "name": "tor exit addresses feed_instance_1", "creator": ""}, OWNERS)
        == "bob@x.com"
    )
    assert find_owner({"kind": "Playbook", "name": "FW Alert Triage", "creator": "DBot@demisto.com"}, OWNERS) == "alice@x.com"
    assert find_owner({"kind": "Playbook", "name": "Bot made", "creator": ""}, OWNERS) == "unknown"
    assert find_owner({"kind": "Job", "name": "nothing", "creator": ""}, OWNERS) == "unknown"


def test_check_object_uses_the_owner_index():
    f = check_object(
        {"kind": "Integration instance", "name": "Tor Exit Addresses Feed_instance_1", "creator": ""}, REGISTRY, OWNERS
    )
    assert f[0]["owner"] == "bob@x.com"


def test_reported_names_only_from_rule_issues():
    issues = [
        {
            "name": "CTT - Hygiene - CTT-TAG-01 - Object created without owner tag",
            "description": "a@x.com created Playbook 'FW Alert Triage': no tag prefix.",
        },
        {
            "name": "CTT - Hygiene - CTT-TAG-01 - Objects without a registered owner tag (a@x.com)",
            "description": "The inventory check found 1 item(s) ... Script 'AddIOC'",
        },
        {"name": "Something else", "description": "'Other'"},
    ]
    assert reported_names(issues) == {"fw alert triage"}


def test_tagged_in_tags_field_needs_no_prefix():
    """CTT-TAG-01: a registered tag in the Tags field of a playbook, script or job counts as the owner tag."""
    pb = {"kind": "Playbook", "name": "Local Analysis copy", "creator": "", "tags": ["Alice"]}
    assert check_object(pb, REGISTRY) == []
    assert inventory_entry(pb, REGISTRY)["owner"] == "alice@x.com"
    script = {"kind": "Script", "name": "TypeSafeJevMarketplaceAssessment", "creator": "", "tags": ["Content Management", "ALI"]}
    assert check_object(script, REGISTRY) == []
    assert inventory_entry(script, REGISTRY)["owner"] == "alice@x.com"
    assert check_object({**script, "kind": "Job"}, REGISTRY) == []
    # A kind without a Tags field, or an unregistered tag, still needs the prefix.
    assert check_object({**pb, "tags": ["zed"]}, REGISTRY)[0]["guideline"] == "CTT-TAG-01"
    assert check_object({**pb, "kind": "Integration instance"}, REGISTRY)[0]["guideline"] == "CTT-TAG-01"
    assert check_object({**script, "tags": ["Content Management"]}, REGISTRY)[0]["guideline"] == "CTT-TAG-01"
    # The tag's owner is still checked: bob is inactive.
    assert [f["guideline"] for f in check_object({**pb, "tags": ["bob"]}, REGISTRY)] == ["CTT-LIFE-02"]


def test_collect_objects_skips_platform_objects_and_lists_collectors(monkeypatch):
    """testmodule and the user hook scripts exist on every tenant under fixed names; data collectors
    come from the audit log query (created and never edited or deleted)."""
    replies = {
        "/playbook/search": {"playbooks": []},
        "/automation/search": {
            "scripts": [
                {"name": "CommonServerUserPython"},
                {"name": "CommonUserServer"},
                {"name": "GetLabUsers", "user": "a@x.com", "tags": ["ali"]},
            ]
        },
        "/jobs/search": {"data": [{"name": "Nightly", "owner": "b@x.com", "tags": ["bob"]}]},
        "/settings/integration/search": {
            "instances": [
                {"name": "testmodule", "brand": "testmodule"},
                {"name": "Rasterize_default_instance", "brand": "Rasterize"},
            ]
        },
        "/public_api/v1/correlations/get": {"objects": []},
        "/public_api/v1/xql/get_datasets": [],
    }
    monkeypatch.setattr(CTTInventoryCheck, "core_post", lambda uri, body: replies[uri])
    monkeypatch.setattr(CTTInventoryCheck, "run_xql", lambda query, days: [{"object_name": "asean_test1", "creator": "s@x.com"}])
    errors: list[str] = []
    objects = collect_objects(errors)
    assert errors == []
    assert [(o["kind"], o["name"]) for o in objects] == [
        ("Script", "GetLabUsers"),
        ("Job", "Nightly"),
        ("Integration instance", "Rasterize_default_instance"),
        ("Data collector", "asean_test1"),
    ]
    assert objects[0]["tags"] == ["ali"]
    assert objects[1]["tags"] == ["bob"]
    collector = check_object(objects[-1], REGISTRY)
    assert collector[0]["guideline"] == "CTT-TAG-01"
    assert collector[0]["owner"] == "s@x.com"
