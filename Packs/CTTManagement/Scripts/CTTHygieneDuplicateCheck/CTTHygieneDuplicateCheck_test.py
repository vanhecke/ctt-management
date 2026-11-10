from CTTHygieneDuplicateCheck import DAY_MS, find_duplicate, object_key

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
    assert dup == "62180"
    assert note.startswith("Duplicate of issue #62180, which is still open for the same endpoint PC1")
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
    assert dup == "60000"
    assert "marked a false positive on" in note
    assert "30 days" in note
    assert find_duplicate("62190", LAB, LAB_TEXT, [fp], NOW, 3) == ("", "")
    fixed = dict(fp, **{"status.resolution_reason": "RESOLVED_OTHER"})
    assert find_duplicate("62190", LAB, LAB_TEXT, [fixed], NOW, 30) == ("", "")
