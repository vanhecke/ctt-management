from CTTHygieneDispatch import pick, remember

ISSUES = [
    {"id": 1, "name": "CTT - Hygiene - CTT-TAG-01 - Object created without owner tag", "assigned_to": None},
    {"id": 2, "name": "CTT - Hygiene - CTT-CEN-01 - Centrally managed setting changed", "assigned_to": "j@x.com"},
    {"id": 3, "name": "Collector stopped sending", "assigned_to": None},
    {"id": 4, "name": "CTT - Hygiene - CTT-OWN-01 - Another owner's object changed", "assigned_to": None},
]


def test_pick_skips_assigned_foreign_and_done():
    assert pick(ISSUES, set(), 10) == ["1", "4"]
    assert pick(ISSUES, {"1"}, 10) == ["4"]
    assert pick(ISSUES, set(), 1) == ["1"]


def test_remember_keeps_order_and_dedupes():
    assert remember(["1", "2"], ["2", "3"]) == ["1", "2", "3"]
