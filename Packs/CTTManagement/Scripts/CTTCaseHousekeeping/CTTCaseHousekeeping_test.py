from CTTCaseHousekeeping import (
    DAY_MS,
    DEFAULTS,
    HOUR_MS,
    ENDPOINT_OWNER_QUERY,
    build_digest,
    decide_dm,
    host_endpoint_ids,
    lab_octets,
    pick_owner,
    plan_case,
    prune_state,
    registry_maps,
)

NOW = 1_800_000_000_000
REGISTRY = [
    {
        "tag": "jvanhecke",
        "owner_email": "jva@x.com",
        "owner_name": "Joris V",
        "slack_id": "U1",
        "role": "admin",
        "lab_octet": "20",
        "tag_kind": "primary",
        "active": "true",
    },
    {"tag": "jva", "owner_email": "jva@x.com", "role": "admin", "lab_octet": "20", "tag_kind": "extra", "active": "true"},
    {
        "tag": "bob",
        "owner_email": "bob@x.com",
        "owner_name": "Bob",
        "slack_id": "",
        "role": "dc",
        "lab_octet": "21",
        "tag_kind": "primary",
        "active": "true",
    },
    {"tag": "ctt", "owner_email": "ctt@x.com", "role": "central", "tag_kind": "central", "active": "true"},
]
TAGS, OCTETS, PEOPLE = registry_maps(REGISTRY)


def test_generated_query():
    assert "dataset = endpoints" in ENDPOINT_OWNER_QUERY
    assert "ctt_object_owners" in ENDPOINT_OWNER_QUERY


def test_registry_maps():
    assert TAGS["jva"] == "jva@x.com" and "ctt" not in TAGS
    assert OCTETS == {"20": "jva@x.com", "21": "bob@x.com"}
    assert PEOPLE["jva@x.com"]["slack_id"] == "U1"


def test_hosts_and_octets():
    case = {"hosts": ["win-1:abc123", "10.21.0.5:10.21.0.5"], "description": "10.20.1.2 connected to 8.8.8.8"}
    assert host_endpoint_ids(case) == ["abc123"]
    assert lab_octets(case) == ["21", "20"]


def test_pick_owner_order():
    assert pick_owner(["jva - my rule"], ["bob@x.com"], ["21"], TAGS, OCTETS) == ("jva@x.com", "correlation rule tag")
    assert pick_owner(["Port scan"], ["bob@x.com"], ["20"], TAGS, OCTETS) == ("bob@x.com", "endpoint owner")
    assert pick_owner([], ["unknown"], ["21", "21", "20"], TAGS, OCTETS) == ("bob@x.com", "lab range")
    assert pick_owner([], [], ["99"], TAGS, OCTETS) == ("", "")


def test_plan_case():
    cfg = dict(DEFAULTS)
    old = {"creation_time": NOW - 8 * DAY_MS}
    assert plan_case(old, {}, NOW, cfg, None) == ["close"]
    assert plan_case({**old, "starred": True}, {}, NOW, cfg, None) == []
    young = {"creation_time": NOW - 2 * DAY_MS}
    assert plan_case(young, {}, NOW, cfg, NOW - 2 * HOUR_MS) == ["assign"]
    assert plan_case(young, {}, NOW, cfg, NOW - 30 * HOUR_MS) == ["assign", "suggest"]
    assert plan_case({**young, "assigned_user_mail": "a@x.com"}, {"suggested": 1}, NOW, cfg, None) == []
    assert plan_case(young, {"owner_checked": NOW - HOUR_MS}, NOW, cfg, NOW) == []
    assert plan_case({"creation_time": NOW - 2 * HOUR_MS}, {}, NOW, cfg, None) == []


def test_decide_dm():
    notify = {"mode": "allowlist", "allowlist": ["jva@x.com"], "max_dms_per_owner_per_day": 3}
    assert decide_dm("jva@x.com", PEOPLE["jva@x.com"], notify, 0) == (True, "sent")
    assert decide_dm("jva@x.com", PEOPLE["jva@x.com"], notify, 3)[0] is False
    assert decide_dm("bob@x.com", PEOPLE["bob@x.com"], {"mode": "all"}, 0)[1] == "no Slack ID in the registry"


def test_build_digest():
    case = {
        "case_id": 12,
        "case_name": "Suspicious port scan",
        "creation_time": NOW - 2 * DAY_MS,
        "xdr_url": "https://t/incident-view?caseId=12",
    }
    text = build_digest("Joris", {"assign": [case], "suggest": [case] * 8}, NOW)
    assert "ASSIGNED TO YOU (1)" in text and "CLOSE IF DONE (8)" in text
    assert "• #12 Suspicious port scan (2d)" in text and "https://t/incident-view?caseId=12" in text
    assert "… and 2 more" in text
    assert all(len(line) <= 46 or line.startswith("  https://") for line in text.splitlines())


def test_prune_state():
    assert prune_state({"1": {}, "2": {}}, {"2"}) == {"2": {}}
