import pytest
from CTTHygieneFixCheck import (
    build_digest,
    case_close_note,
    check_builtin,
    check_deleted,
    check_endpoint,
    check_item,
    check_listed,
    check_policy,
    check_untagged,
    check_untagged_policy,
    check_registry,
    decide,
    owner_tags,
    parse_issue,
    playbook_close,
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


OOTB = "CTT - Hygiene - CTT-OOTB-01 - Built-in or untagged content changed"


def ootb(subtype, kind, name, created=1_000):
    return parse_issue(
        issue(
            OOTB,
            f"juc@x.com ran '{subtype}' on {kind} '{name}' (object has no owner tag). Duplicate built-in content and "
            "change the copy under your own tag (guideline CTT-OOTB-01). [owner: juc@x.com]",
            _insert_time=created,
        )
    )


@pytest.mark.parametrize(
    "subtype, deleted",
    [("Delete Group", True), ("Delete - Playbook", True), ("Remove", True), ("Edit - Playbook", False), ("Edit", False)],
)
def test_parse_issue_flags_deletes(subtype, deleted):
    assert ootb(subtype, "ENDPOINT_GROUPS", "Workstation Group")["deleted"] is deleted


def test_check_deleted_closes_once_the_owner_was_told():
    item = ootb("Delete Group", "ENDPOINT_GROUPS", "Workstation Group", created=1_000)
    assert check_deleted(item, 1_000 + 60_000) == (
        "pending",
        "endpoint group 'Workstation Group' was deleted, so nothing is left to fix; the issue closes by itself within an hour",
    )
    assert check_deleted(item, 1_000 + 3_600_000) == (
        "fixed",
        "endpoint group 'Workstation Group' was deleted, so nothing is left to fix (the owner was told)",
    )
    # check_item routes deletes of any kind there, playbooks included
    pb = ootb("Delete - Playbook", "Playbook", "Test")
    assert check_item(pb, {"now_ms": 1_000 + 3_600_000})[0] == "fixed"


def test_check_untagged():
    item = ootb("Edit - Integrations", "Integrations", "Cortex Core - Platform_default_instance")
    names = {"Cortex Core - Platform_default_instance", "jva - mine"}
    assert check_untagged(item, None, {}, {"juc"})[0] == "unchecked"
    assert check_untagged(item, names, {}, {"juc"})[0] == "pending"
    assert check_untagged(item, {"jva - mine"}, {}, {"juc"}) == (
        "fixed",
        "integration instance 'Cortex Core - Platform_default_instance' no longer exists under that name (renamed or deleted)",
    )
    job = ootb("Edit", "Job", "nightly")
    assert check_untagged(job, {"nightly"}, {("Job", "nightly"): {"juc"}}, {"juc"})[0] == "fixed"


def test_check_item_routes_ootb_edits():
    ctx = {
        "names": {"Policy profile": {"SF - Labs"}},
        "field_tags": {},
        "policies": {"SF - Labs": {"action": "delete"}},
        "builtin": {},
        "tags": lambda owner: {"juc"},
    }
    assert check_item(ootb("Edit", "Policy profile", "SF - Labs"), ctx)[0] == "pending"
    assert check_item(ootb("Edit", "Policy rule", "SF - Labs"), ctx) == ("fixed", "policy rule 'SF - Labs' was deleted")
    assert check_untagged_policy(ootb("Edit", "Policy rule", "x"), None)[0] == "pending"
    # no complete list for correlation rules (built-in ones are left out): owner confirmation
    assert check_item(ootb("Edit", "Correlation rule", "r"), ctx)[0] == "unchecked"


def test_decide_pending_closes_on_confirmation_only():
    item = ootb("Edit", "Policy profile", "SF - Labs")
    assert decide(item, "pending", "x", "check", 0)["action"] == "none"
    confirmed = decide(item, "pending", "policy profile 'SF - Labs' still exists under that name", "confirm", 0)
    assert confirmed["action"] == "resolve"
    assert confirmed["note"].startswith("Confirmed fixed by juc@x.com")


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
    assert check_endpoint(item, [{"violating": "0", "lab_ip": "10.23.1.2"}]) == (
        "fixed",
        "endpoint lnx-2 now has 10.23.1.2, in its owner's lab range",
    )
    assert check_endpoint(item, [{"violating": 1, "lab_ip": "10.9.1.2", "range_owner": None}])[0] == "open"


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
        "note": (
            "You said this is fixed, but the check still sees it: still there. Fix it, then press Mark as Fixed again; "
            "it also closes by itself within an hour once it is fixed."
        ),
    }
    fp = decide(item, "unchecked", "", "false_positive", 0)
    assert (fp["reason"], fp["note"].startswith("Marked as false positive by jvanhecke@x.com")) == (
        "Resolved - False Positive",
        True,
    )


def test_resolution_kind_reads_the_close_note():
    assert resolution_kind("Auto-closed by the CTT fix check: x") == "auto check"
    assert resolution_kind("Confirmed fixed by a@b") == "owner confirmed"
    assert resolution_kind("Marked as false positive by a@b") == "false positive"
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


def test_playbook_close_uses_an_allowed_reason():
    assert playbook_close({"reason": "Resolved - Fixed", "note": "n"}) == {
        "close": True,
        "reason": "Resolved - Other",
        "note": "n",
    }
    assert playbook_close({"reason": "Resolved - False Positive", "note": "n"})["reason"] == "Resolved - False Positive"


def test_parse_issue_keeps_the_playbook_state():
    assert parse_issue({**TAG01, "playbook_run_status": "Waiting"})["playbook"] == "waiting"


def test_check_listed_tags_field():
    """CTT-TAG-01: a playbook, script or job with one of the owner's tags in its Tags field needs no name prefix."""
    item = {"guideline": "CTT-TAG-01", "kind": "Playbook", "name": "Local copy", "endpoint": "", "email": "", "title": ""}
    names = {"Playbook": {"Local copy"}, "Script": {"Local copy"}}
    verdict, text = check_listed(item, names, {("Playbook", "Local copy"): {"jvanhecke"}}, {"jvanhecke", "jva"})
    assert verdict == "fixed"
    assert text == "playbook 'Local copy' carries your tag jvanhecke in its Tags field"
    assert check_listed(item, names, {("Playbook", "Local copy"): {"bob"}}, {"jvanhecke"})[0] == "open"
    assert check_listed(item, names, {}, {"jvanhecke"})[0] == "open"
    # A script: the central tag counts for a CTT admin (owner_tags adds ctt); the Tags of a playbook
    # with the same name don't.
    script = dict(item, kind="Script")
    assert (
        check_listed(script, names, {("Script", "Local copy"): {"ctt", "content management"}}, {"jvanhecke", "ctt"})[0] == "fixed"
    )
    assert check_listed(script, names, {("Playbook", "Local copy"): {"jvanhecke"}}, {"jvanhecke"})[0] == "open"
    # CTT-TAG-04 (someone else's tag in the name) still needs the rename.
    tags04 = {("Playbook", "Local copy"): {"jvanhecke"}}
    assert check_listed(dict(item, guideline="CTT-TAG-04"), names, tags04, {"jvanhecke"})[0] == "open"


def test_parse_issue_maps_sso_accounts_to_the_registry_email():
    raw = issue("CTT - Hygiene - CTT-LAB-01 - x", "Endpoint a: y. [owner: unknown]", assigned_user_mail="Sfi@asean.ctt")
    assert parse_issue(raw)["owner"] == "sfi@paloaltonetworks.com"
    raw = issue("CTT - Hygiene - CTT-LAB-01 - x", "Endpoint a: y. [owner: sfi@asean.ctt]")
    assert parse_issue(raw)["owner"] == "sfi@paloaltonetworks.com"
