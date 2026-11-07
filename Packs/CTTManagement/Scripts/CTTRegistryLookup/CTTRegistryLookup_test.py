from CTTRegistryLookup import lookup, summarise

ROWS = [
    {
        "tag": "alice",
        "primary_tag": "alice",
        "owner_email": "alice@x.com",
        "owner_name": "Alice A",
        "role": "admin",
        "lab_octet": "1",
        "active": "true",
    },
    {
        "tag": "ali",
        "primary_tag": "alice",
        "owner_email": "alice@x.com",
        "owner_name": "Alice A",
        "role": "admin",
        "lab_octet": "1",
        "active": "true",
    },
    {
        "tag": "bob",
        "primary_tag": "bob",
        "owner_email": "bob@x.com",
        "owner_name": "Bob B",
        "role": "dc",
        "lab_octet": "2",
        "active": "true",
    },
    {
        "tag": "ctt",
        "primary_tag": "ctt",
        "owner_email": "",
        "owner_name": "CTT admins",
        "role": "central",
        "lab_octet": "",
        "active": "true",
    },
]


def test_lookup_by_alias_returns_all_owner_tags():
    kind, rows = lookup(ROWS, "ALI")
    assert kind == "tag"
    assert {r["tag"] for r in rows} == {"alice", "ali"}


def test_lookup_by_ip_and_octet():
    assert lookup(ROWS, "10.2.14.7")[1][0]["tag"] == "bob"
    assert lookup(ROWS, "2")[0] == "lab range"
    assert lookup(ROWS, "10.99.0.1")[1] == []
    assert lookup(ROWS, "172.16.2.40")[1][0]["tag"] == "bob"
    assert lookup(ROWS, "172.17.2.40")[0] != "lab range"


def test_lookup_by_email_and_name():
    assert lookup(ROWS, "bob@x.com")[1][0]["tag"] == "bob"
    assert lookup(ROWS, "alice")[0] == "tag"
    assert {r["tag"] for r in lookup(ROWS, "Alice A")[1]} == {"alice", "ali"}


def test_central_tag():
    kind, rows = lookup(ROWS, "ctt")
    assert kind == "tag"
    assert rows[0]["role"] == "central"


def test_summarise_groups_by_person():
    people = summarise(lookup(ROWS, "ali")[1])
    assert len(people) == 1
    assert people[0]["tags"] == ["ali", "alice"]
    assert people[0]["lab_range"] == "10.1.0.0/16, 172.16.1.0/24"
