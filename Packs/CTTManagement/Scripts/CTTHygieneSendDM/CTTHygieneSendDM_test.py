from CTTHygieneSendDM import WIDTH, build_dm, bump, header, section, template_body, usable_ai_message, wrap_body


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
    assert lines[-3] == "Intended? Reply in the CTT channel."
    assert dm.count("https://t/1") == 1


def test_bump_counts_today_and_drops_old_days():
    state = {"2026-11-05": {"b@x.com": 3}, "2026-11-06": {"b@x.com": 1}}
    assert bump(state, "2026-11-06", "b@x.com") == {"2026-11-06": {"b@x.com": 2}}
    assert bump(state, "2026-11-07", "j@x.com") == {"2026-11-07": {"j@x.com": 1}}


def test_usable_ai_message():
    assert usable_ai_message("Hi Bob,\n\nFix:\n• Rename it.\n\nIf this was intended, reply in the CTT channel.")
    assert not usable_ai_message("Hi Bob,\n\nFix:\n• Rename the playbook to")
    assert not usable_ai_message("")


def test_section_wraps_beside_label():
    out = section("FIX", '• Rename it to "jvanhecke - Local Analysis alert Investigation_copy"')
    assert out[0].startswith("FIX     • Rename it to")
    assert all(line.startswith("          ") for line in out[1:])
    assert all(len(line) <= WIDTH for line in out)


def test_template_body():
    body = template_body(
        "Joris",
        'Playbook "X" was created without your tag prefix.',
        "CTT-TAG-01",
        "Prefix object names with your tag",
        'Rename it to "jva - X"\nOr use another of your tags: jvanhecke',
    )
    lines = body.splitlines()
    assert lines[0] == "Hi Joris,"
    assert lines[2].startswith("FOUND   Playbook")
    assert any(line.startswith("RULE    CTT-TAG-01 · Prefix object names") for line in lines)
    assert any(line.startswith("FIX     • Rename it to") for line in lines)
    assert any(line.startswith("        • Or use another of your tags") for line in lines)


def test_build_dm_with_buttons_explains_them_and_drops_the_link():
    links = {"fixed": "https://t/f", "not_violation": "https://t/n"}
    dm = build_dm("CTT-TAG-01", "Body.", "60900", "https://t/1", links=links, buttons=True)
    assert "Press Fixed! below" in dm
    assert "https://t/" not in dm


def test_build_dm_without_buttons_lists_the_answer_links():
    links = {"fixed": "https://t/f", "not_violation": "https://t/n"}
    dm = build_dm("CTT-TAG-01", "Body.", "60900", "https://t/1", links=links)
    assert dm.index("https://t/f") < dm.index("https://t/n") < dm.index("https://t/1")


def test_build_dm_puts_the_reask_note_first():
    dm = build_dm("CTT-TAG-01", "Body.", "60900", "", note="You said it was fixed, but playbook x still exists.")
    assert dm.index("You said it was fixed") < dm.index("Body.")
