from datetime import datetime

from CTTTenantStatus import QUERIES, build_canvas, build_topic, by, dataset_summary, health_light, human_bytes, owner_label, total

NOW = datetime(2026, 11, 9, 9, 0)


def empty_stats(**extra):
    stats = {key: [] for key in QUERIES}
    stats.update({"open_cases": 0, "daily_bytes": 0, "datasets_with_data": 0, "top_datasets": [], **extra})
    return stats


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
    assert by([{"guideline": "CTT-CEN-01", "n": 2}], "guideline", title=False) == {"CTT-CEN-01": 2}


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


def test_health_light_and_owner_label():
    assert health_light(0) == "🟢"
    assert health_light(3) == "🟡"
    assert health_light(12) == "🔴"
    assert owner_label("jvanhecke@paloaltonetworks.com") == "jvanhecke"
    assert owner_label("") == "unknown"


def test_canvas_with_empty_stats():
    canvas = build_canvas(empty_stats(quota={"used": 1.5, "license": 200}), 7, NOW, "https://tenant")
    assert canvas.startswith("CTT TENANT STATUS")
    assert "Updated Mon 09 Nov 2026 09:00 SGT" in canvas
    assert "\nhttps://tenant\n" in canvas
    assert "• Open hygiene issues: 0 (none)" in canvas
    assert "1.5 of 200 CU" in canvas
    assert "**" not in canvas
    assert "#" not in canvas


def test_canvas_counts_hygiene_by_guideline_and_owner():
    stats = empty_stats()
    stats["hygiene_open"] = [
        {"guideline": "CTT-TAG-01", "owner": "j@x.com", "n": 3},
        {"guideline": "CTT-CEN-01", "owner": "b@x.com", "n": 1},
        {"guideline": "CTT-TAG-01", "owner": "b@x.com", "n": 2},
    ]
    canvas = build_canvas(stats, 7, NOW)
    assert "🟡 HYGIENE" in canvas
    assert "• Open hygiene issues: 6 (CTT-TAG-01 5, CTT-CEN-01 1)" in canvas
    assert "• Most to fix: j 3, b 3" in canvas


def test_topic_is_short():
    stats = empty_stats(open_cases=23, daily_bytes=1024**3)
    stats["endpoints"] = [{"endpoint_status": "CONNECTED", "n": 4}]
    topic = build_topic(stats, NOW)
    assert topic.startswith("🟢 CTT Mon 09 Nov: 0 open hygiene issues | 23 open cases | 4 endpoints connected | 1.0 GB/day")
    assert len(topic) <= 250
