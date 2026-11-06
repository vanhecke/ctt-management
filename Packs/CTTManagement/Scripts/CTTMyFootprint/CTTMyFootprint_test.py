from CTTMyFootprint import filter_for_owner, resolve_owner

ROWS = [
    {"tag": "alice", "owner_email": "alice@x.com"},
    {"tag": "ali", "owner_email": "alice@x.com"},
    {"tag": "bob", "owner_email": "bob@x.com"},
]
SWEEP = {
    "Inventory": [
        {"kind": "Script", "name": "ali_Thing", "tag": "ali", "owner": "alice@x.com"},
        {"kind": "Script", "name": "Loose", "tag": None, "owner": "alice@x.com"},
        {"kind": "Job", "name": "bob - nightly", "tag": "bob", "owner": "bob@x.com"},
    ],
    "Findings": [
        {"kind": "Script", "name": "Loose", "guideline": "CTT-TAG-01", "owner": "alice@x.com", "detail": "no tag prefix"},
        {"kind": "Job", "name": "bob - nightly", "guideline": "CTT-LIFE-02", "owner": "bob@x.com", "detail": "inactive"},
    ],
}


def test_resolve_owner_by_alias_and_email():
    assert resolve_owner(ROWS, "ALI") == ("alice@x.com", {"alice", "ali"})
    assert resolve_owner(ROWS, "bob@x.com") == ("bob@x.com", {"bob"})
    assert resolve_owner(ROWS, "nobody") == ("", set())
    assert resolve_owner(ROWS, "new@x.com") == ("new@x.com", set())


def test_filter_for_owner():
    inventory, findings = filter_for_owner(SWEEP, "alice@x.com", {"alice", "ali"})
    assert [i["name"] for i in inventory] == ["ali_Thing", "Loose"]
    assert [f["name"] for f in findings] == ["Loose"]
