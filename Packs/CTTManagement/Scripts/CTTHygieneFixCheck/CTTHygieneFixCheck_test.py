import pytest
from CTTHygieneFixCheck import (
    build_digest,
    case_close_note,
    check_builtin,
    check_endpoint,
    check_item,
    check_listed,
    check_policy,
    check_registry,
    decide,
    owner_tags,
    parse_issue,
    registry_people,
    resolution_kind,
)

REGISTRY = [
    {"tag": "jva", "owner_email": "jvanhecke@x.com", "owner_name": "Joris Vanhecke", "role": "admin", "tag_kind": "primary"},
    {"tag": "sfi", "owner_email": "sfi@x.com", "owner_name": "Sam Fi", "role": "dc"},
]


def issue(name, description, **extra):
    return {"id": 61001, "name": name, "description": description, "_insert_time": 1_000, **extra}


TAG01 = issue(
    "CTT - Hygiene - CTT-TAG-01 - Object created without owner tag",
    "jvanhecke@x.com created Playbook 'somebook': no owner tag prefix. Rename it to start with your own tag "
    "(guideline CTT-TAG-01). [owner: jvanhecke@x.com]",
)
LAB01 = issue(
    "CTT - Hygiene - CTT-LAB-01 - Endpoint outside owner's lab range",
    "Endpoint lnx-2: IP 10.9.1.2 is in an unassigned lab range. Owner: sfi@x.com (endpoint tag). Move it "
    "(guideline CTT-LAB-01). [owner: sfi@x.com]",
)


def test_parse_issue_reads_guideline_object_and_owner():
    item = parse_issue(TAG01)
    assert (item["guideline"], item["kind"], item["name"], item["owner"]) == (
        "CTT-TAG-01",
        "Playbook",
        "somebook",
        "jvanhecke@x.com",
    )
    lab = parse_issue(LAB01)
    assert (lab["endpoint"], lab["owner"]) == ("lnx-2", "sfi@x.com")


def test_parse_issue_skips_inventory_issues_and_others():
    inv = issue("CTT - Hygiene - CTT-TAG-01 - Objects without a registered owner tag (x)", "The inventory check found 3 item(s)")
    assert parse_issue(inv) is None
    old_sweep = issue("CTT - Hygiene - CTT-CASE-01 - Stale open Security cases (unassigned)", "Daily sweep found 1000 item(s)")
    assert parse_issue(old_sweep) is None
    assert parse_issue(issue("Collection error in the instance X", "boom")) is None


def test_parse_issue_unknown_owner_falls_back_to_assignee():
    raw = issue("CTT - Hygiene - CTT-LAB-01 - x", "Endpoint a: y. [owner: unknown]", assigned_user_mail="Sfi@x.com")
    assert parse_issue(raw)["owner"] == "sfi@x.com"


def test_check_registry():
    people = registry_people(REGISTRY)
    item = {"email": "sfi@x.com", "owner": "sfi@x.com"}
    assert check_registry(item, people)[0] == "fixed"
    assert check_registry({"email": "new@x.com", "owner": ""}, people)[0] == "open"


def test_check_listed_object_gone_or_still_there():
    item = parse_issue(TAG01)
    assert check_listed(item, {"Playbook": {"other"}}) == (
        "fixed",
        "playbook 'somebook' no longer exists under that name (renamed or deleted)",
    )
    assert check_listed(item, {"Playbook": {"somebook"}})[0] == "open"


@pytest.mark.parametrize(
    "found,verdict",
    [
        (None, "fixed"),
        ({"packID": "Core", "detached": True}, "open"),
        ({"packID": "Core", "detached": None}, "fixed"),
        ({"packID": "", "system": False}, "open"),
    ],
)
def test_check_builtin(found, verdict):
    item = {"kind": "Playbook", "name": "A successful SSO sign-in from TOR", "endpoint": "", "email": "", "title": ""}
    assert check_builtin(item, found, {"jva"})[0] == verdict


def test_check_builtin_custom_object_renamed_with_owner_tag():
    item = {"kind": "Playbook", "name": "JVA - my copy", "endpoint": "", "email": "", "title": ""}
    assert check_builtin(item, {"packID": ""}, {"jva"})[0] == "fixed"


def test_check_policy():
    item = {"kind": "Policy rule", "name": "linux rule", "endpoint": "", "email": "", "title": ""}
    assert check_policy(item, None, {"jva"})[0] == "open"
    assert check_policy(item, {"action": "delete"}, {"jva"})[0] == "fixed"
    assert check_policy(item, {"action": "modify", "scope_tags": "JVA, other"}, {"jva"})[0] == "fixed"
    assert check_policy(item, {"action": "modify", "scope_tags": None, "scope_target": "endpoint name = x"}, {"jva"}) == (
        "open",
        "policy rule 'linux rule' still targets endpoint name = x",
    )


def test_check_endpoint():
    item = parse_issue(LAB01)
    assert check_endpoint(item, [])[0] == "fixed"
    assert check_endpoint(item, [{"violating": "0", "ip10": "10.23.1.2"}]) == (
        "fixed",
        "endpoint lnx-2 now has 10.23.1.2, in its owner's lab range",
    )
    assert check_endpoint(item, [{"violating": 1, "ip10": "10.9.1.2", "range_owner": None}])[0] == "open"


def test_owner_tags_adds_ctt_for_admins():
    assert owner_tags(REGISTRY, "jvanhecke@x.com") == {"jva", "ctt"}
    assert owner_tags(REGISTRY, "sfi@x.com") == {"sfi"}


def test_check_item_without_automatic_check():
    item = parse_issue(
        issue(
            "CTT - Hygiene - CTT-OWN-01 - Another owner's object changed",
            "a ran 'Edit' on Playbook 'SFI - x', which belongs to sfi",
        )
    )
    verdict, text = check_item(item, {})
    assert verdict == "unchecked"
    assert "CTT-OWN-01" in text


def test_decide_closes_with_a_note_saying_why():
    item = parse_issue(TAG01)
    auto = decide(item, "fixed", "playbook 'somebook' no longer exists", "check", 0)
    assert (auto["action"], auto["note"].startswith("Auto-closed by the CTT fix check: playbook 'somebook'")) == ("resolve", True)
    assert decide(item, "open", "x", "check", 0)["action"] == "none"
    assert decide(item, "unchecked", "x", "check", 0)["action"] == "none"
    confirmed = decide(item, "unchecked", "no check", "confirm", 0)
    assert confirmed["note"].startswith("Confirmed fixed by jvanhecke@x.com")
    assert decide(item, "open", "still there", "confirm", 0) == {
        "action": "keep",
        "note": "You said this is fixed, but the check still sees it: still there. Fix it, then press Fixed! again.",
    }
    fp = decide(item, "unchecked", "", "false_positive", 0)
    assert (fp["reason"], fp["note"].startswith("Marked not a violation by jvanhecke@x.com")) == (
        "Resolved - False Positive",
        True,
    )


def test_resolution_kind_reads_the_close_note():
    assert resolution_kind("Auto-closed by the CTT fix check: x") == "auto check"
    assert resolution_kind("Confirmed fixed by a@b") == "owner confirmed"
    assert resolution_kind("Marked not a violation by a@b") == "not a violation"
    assert resolution_kind("Resolved by the CTT inventory check: fixed") == "inventory check"
    assert resolution_kind("") == "manual"


def test_build_digest_lists_open_and_closed():
    item = parse_issue(TAG01)
    text = build_digest(
        "Joris", [{**item, "created": 1}], [{**item, "id": "60999", "how": "auto check"}], 3 * 86_400_000 + 1, "https://t"
    )
    assert "STILL OPEN (1)" in text
    assert "CLOSED SINCE YESTERDAY (1)" in text
    assert "https://t/issue-view/61001" in text
    assert "(3d)" in text
    assert all(len(line) <= 46 for line in text.splitlines() if not line.strip().startswith("https://"))


def test_case_close_note_only_when_all_issues_are_resolved():
    done = {"id": 1, "status.progress": "Resolved", "status.resolution_comment": "Auto-closed by the CTT fix check: x"}
    assert case_close_note([done]) == "All its CTT hygiene issues are resolved. #1: Auto-closed by the CTT fix check: x"
    assert case_close_note([done, {"id": 2, "status.progress": "In Progress"}]) is None
    assert case_close_note([]) is None
