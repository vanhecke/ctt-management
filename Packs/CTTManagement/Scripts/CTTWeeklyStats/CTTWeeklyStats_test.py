from CTTWeeklyStats import QUERIES, build_message, by, dataset_summary, human_bytes, total


def test_human_bytes():
    assert human_bytes(512) == "512 B"
    assert human_bytes(2048) == "2.0 KB"
    assert human_bytes(5 * 1024**3) == "5.0 GB"
    assert human_bytes(None) == "0 B"


def test_total_and_by():
    rows = [
        {"xdm.case.domain": "SECURITY", "n": 3},
        {"xdm.case.domain": "HEALTH", "n": 5},
        {"xdm.case.domain": "SECURITY", "n": 1},
    ]
    assert total(rows) == 9
    assert by(rows, "xdm.case.domain") == {"Health": 5, "Security": 4}


def test_dataset_summary():
    daily, count, top = dataset_summary(
        [
            {"Dataset Name": "a", "Average Daily Size": 1024},
            {"Dataset Name": "b", "Average Daily Size": 4096},
            {"Dataset Name": "c", "Average Daily Size": None},
        ]
    )
    assert daily == 5120
    assert count == 2
    assert top[0] == "b (4.0 KB/day)"


def test_build_message_with_empty_stats():
    stats = {key: [] for key in QUERIES}
    stats.update(open_cases=0, daily_bytes=0, datasets_with_data=0, top_datasets=[], quota={"used": 1.5, "license": 200})
    msg = build_message(stats, 7)
    assert msg.startswith("*CTT weekly stats* (last 7 days)")
    assert "*Cases:* 0 new (none); 0 open now" in msg
    assert "1.5 of 200 CU" in msg


def test_build_message_sorts_top_lists():
    stats = {key: [] for key in QUERIES}
    stats.update(open_cases=1, daily_bytes=0, datasets_with_data=0, top_datasets=[])
    stats["playbooks"] = [{"playbook_name": "small", "runs": 1, "failed": 0}, {"playbook_name": "big", "runs": 3, "failed": 1}]
    msg = build_message(stats, 7)
    assert "Busiest: big (3), small (1)" in msg
    assert "4 (1 failed)" in msg
