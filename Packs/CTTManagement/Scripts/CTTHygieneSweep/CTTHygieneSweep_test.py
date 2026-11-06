from CTTHygieneSweep import (
    DAY_MS,
    check_case,
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


def test_check_case():
    now = 100 * DAY_MS
    stale = check_case({"case_id": 7, "case_name": "Lab", "modification_time": now - 10 * DAY_MS, "assigned_user": None}, now, 7)
    fresh = check_case({"case_id": 8, "modification_time": now - 2 * DAY_MS}, now, 7)
    assert stale["owner"] == "unassigned"
    assert "10 days" in stale["detail"]
    assert fresh is None


def test_group_and_plan():
    findings = [
        {"kind": "Script", "name": "a", "guideline": "CTT-TAG-01", "owner": "u", "detail": "no tag prefix"},
        {"kind": "Script", "name": "b", "guideline": "CTT-TAG-01", "owner": "u", "detail": "no tag prefix"},
    ]
    groups = group_findings(findings)
    key = "CTT-TAG-01|u"
    assert list(groups) == [key]
    assert plan(groups, {}) == ([key], [], [])
    same = {key: {"fingerprint": groups[key]["fingerprint"], "items": groups[key]["items"]}, "CTT-CASE-01|x": {"items": ["old"]}}
    assert plan(groups, same) == ([], ["CTT-CASE-01|x"], [])
    shrunk = {key: {"fingerprint": "older", "items": [*groups[key]["items"], "Script 'c': no tag prefix"]}}
    assert plan(groups, shrunk) == ([], [], [key])
    grew = {key: {"fingerprint": "older", "items": groups[key]["items"][:1]}}
    assert plan(groups, grew) == ([key], [key], [])


def test_issue_body():
    group = {"guideline": "CTT-TAG-01", "owner": "u@x.com", "items": [f"Script '{i}': no tag prefix" for i in range(70)]}
    issue = issue_body(group, 1)["request_data"]["issue"]
    assert issue["name"] == "CTT - Hygiene - CTT-TAG-01 - Objects without a registered owner tag (u@x.com)"
    assert issue["issue_domain"] == "Health"
    assert issue["severity"] == "MEDIUM"
    assert "and 10 more" in issue["description"]


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
