from CTTRegistrySync import build_registry, csv_to_rows, rows_to_dicts, sheet_values, tags_to_remove, to_lookup_row

USERS = [
    ["tag", "octet", "owner_email", "owner_name", "slack_id", "ctt_admin", "active"],
    ["alice", "1", "Alice@Example.com", "Alice A", "U1", "yes", "yes"],
    ["bob", "2", "bob@example.com", "Bob B", "U2", "no", "yes"],
    ["", "", "", "", "", "", ""],
]
EXTRA = [
    ["tag", "owner_email", "owner_name", "original_tag"],
    ["ali", "alice@example.com", "Alice A", "alice"],
]


def test_rows_to_dicts_normalises_header_and_skips_blank_rows():
    rows = rows_to_dicts(USERS)
    assert len(rows) == 2
    assert rows[0]["owner_email"] == "Alice@Example.com"
    assert rows[0]["ctt_admin"] == "yes"


def test_sheet_values_reads_rowdata_values():
    sheet = {"rowData": [{"values": ["tag", "octet"]}, {"values": ["alice", "1"]}]}
    assert sheet_values(sheet) == [["tag", "octet"], ["alice", "1"]]


def test_build_registry_merges_extra_and_central_tags():
    records, errors = build_registry(rows_to_dicts(USERS), rows_to_dicts(EXTRA), ["CTT"])
    by_tag = {r["tag"]: r for r in records}
    assert errors == []
    assert set(by_tag) == {"alice", "ali", "bob", "ctt"}
    assert by_tag["alice"]["owner_email"] == "alice@example.com"
    assert by_tag["alice"]["role"] == "admin"
    assert by_tag["bob"]["role"] == "dc"
    assert by_tag["ali"]["tag_kind"] == "extra"
    assert by_tag["ali"]["lab_octet"] == "1"
    assert by_tag["ali"]["primary_tag"] == "alice"
    assert by_tag["ctt"]["role"] == "central"


def test_build_registry_reports_bad_rows():
    users = rows_to_dicts(
        [
            ["tag", "octet", "owner_email"],
            ["ok", "3", "a@x.com"],
            ["bad-tag", "4", "b@x.com"],
            ["ok", "5", "c@x.com"],
            ["dup", "3", "d@x.com"],
            ["nomail", "6", ""],
        ]
    )
    extra = rows_to_dicts([["tag", "owner_email", "original_tag"], ["orph", "z@x.com", "nobody"]])
    records, errors = build_registry(users, extra, [])
    assert [r["tag"] for r in records] == ["dup", "ok"]
    joined = " | ".join(errors)
    assert "Invalid tag 'bad-tag'" in joined
    assert "Duplicate tag 'ok'" in joined
    assert "Octet 3 is assigned to both" in joined
    assert "'nomail' has no owner_email" in joined
    assert "Extra tag 'orph' has no matching primary tag" in joined


def test_csv_fallback_with_original_tag_column():
    text = (
        "tag,octet,owner_email,owner_name,slack_id,ctt_admin,active,original_tag\n"
        "alice,1,alice@example.com,Alice,,yes,yes,\n"
        "ali,,alice@example.com,Alice,,,,alice\n"
    )
    records, errors = build_registry(rows_to_dicts(csv_to_rows(text)), [], ["ctt"])
    assert errors == []
    assert {r["tag"]: r["tag_kind"] for r in records} == {"alice": "primary", "ali": "extra", "ctt": "central"}


def test_inactive_user():
    users = rows_to_dicts([["tag", "owner_email", "active"], ["gone", "g@x.com", "no"]])
    records, _ = build_registry(users, [], [])
    assert records[0]["active"] == "false"


def test_tags_to_remove():
    existing = [{"ctt_tag": "alice"}, {"ctt_tag": "old"}, {"ctt_tag": ""}]
    assert tags_to_remove(existing, [{"tag": "alice"}]) == ["old"]


def test_to_lookup_row_renames_tag():
    row = to_lookup_row({"tag": "alice", "owner_email": "a@x.com"})
    assert row == {"ctt_tag": "alice", "owner_email": "a@x.com"}


def test_build_registry_stores_the_panw_email_for_an_sso_email():
    users = [USERS[0], ["jdoe", "3", "JDoe@asean.ctt", "J Doe", "U3", "no", "yes"]]
    extra = [EXTRA[0], ["jdo", "jdoe@paloaltonetworks.com", "J Doe", "jdoe"]]
    records, errors = build_registry(rows_to_dicts(users), rows_to_dicts(extra), [])
    assert errors == []
    assert {r["tag"]: r["owner_email"] for r in records} == {
        "jdoe": "jdoe@paloaltonetworks.com",
        "jdo": "jdoe@paloaltonetworks.com",
    }
