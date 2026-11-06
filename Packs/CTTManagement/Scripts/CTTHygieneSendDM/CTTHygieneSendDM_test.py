from CTTHygieneSendDM import WIDTH, build_dm, bump, header, wrap_body


def test_header_is_a_closed_box():
    lines = header("CTT HYGIENE", "CTT-TAG-01").splitlines()
    assert len(lines) == 3
    assert all(len(line) == WIDTH for line in lines)
    assert lines[1].startswith("│  CTT HYGIENE")
    assert lines[1].endswith("CTT-TAG-01  │")


def test_wrap_body_keeps_bullets_and_blank_lines():
    text = "Hi Bob,\n\nFix:\n- " + "rename the playbook to start with your tag " * 2
    lines = wrap_body(text).splitlines()
    assert lines[1] == ""
    assert lines[3].startswith("• rename")
    assert lines[4].startswith("  ")
    assert all(len(line) <= WIDTH for line in lines)


def test_build_dm_moves_link_to_footer():
    dm = build_dm("CTT-TAG-01", "Hi Bob, see https://t/1 for details.", "60900", "https://t/1")
    lines = dm.splitlines()
    assert lines[-1] == "https://t/1"
    assert lines[-2] == "Issue #60900 · assigned to you"
    assert dm.count("https://t/1") == 1


def test_bump_counts_today_and_drops_old_days():
    state = {"2026-11-05": {"b@x.com": 3}, "2026-11-06": {"b@x.com": 1}}
    assert bump(state, "2026-11-06", "b@x.com") == {"2026-11-06": {"b@x.com": 2}}
    assert bump(state, "2026-11-07", "j@x.com") == {"2026-11-07": {"j@x.com": 1}}
