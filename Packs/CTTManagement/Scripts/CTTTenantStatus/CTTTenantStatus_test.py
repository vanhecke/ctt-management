from datetime import datetime

from CTTTenantStatus import (
    QUERIES,
    active_integrations,
    build_canvas,
    build_topic,
    by,
    dataset_summary,
    health_light,
    human_bytes,
    owner_label,
    total,
)

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
    assert owner_label("NULL") == "unknown"


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


def test_topic_is_tenant_activity_only():
    stats = empty_stats(open_cases=1866, new_cases_24h=41, daily_bytes=15.3 * 1024**3, integrations_active=42)
    stats["endpoints"] = [{"endpoint_status": "CONNECTED", "n": 19}, {"endpoint_status": "DISCONNECTED", "n": 9}]
    topic = build_topic(stats, NOW)
    assert topic == (
        "CTT Mon 09 Nov · 1,866 open cases (+41 in 24h) · 19 endpoints connected · 15.3 GB/day ingested · 42 integrations active"
    )
    assert "hygiene" not in topic
    assert "canvas" not in topic
    assert len(topic) <= 250
    assert all(ord(ch) < 0x2000 or ch == "·" for ch in topic)


def test_canvas_automation_section():
    stats = empty_stats()
    stats["playbooks"] = [
        {"playbook_name": "FW Alert Triage", "runs": 40, "failed": 2},
        {"playbook_name": "CTT - Registry Sync", "runs": 24, "failed": 0},
    ]
    stats["agents"] = [{"agent_name": "Simple FW Alert Triager", "plans": 12, "actions": 80, "people": 2}]
    canvas = build_canvas(stats, 7, NOW)
    auto = canvas.split("⚙️ AUTOMATION", 1)[1].split("📥", 1)[0]
    assert "• Playbook runs: 64 (2 failed)" in auto
    assert "   FW Alert Triage: 40 runs, 2 failed" in auto
    assert "   CTT - Registry Sync: 24 runs" in auto
    assert "   Simple FW Alert Triager: 12 plans, 80 actions by 2 people" in auto
    endpoints = canvas.split("💻 ENDPOINTS", 1)[1]
    assert "agent" not in endpoints.lower()


def test_canvas_agents_without_plans():
    stats = empty_stats()
    stats["agents"] = [{"agent_name": "A", "runs": 1, "actions": 5, "people": 1}]
    assert "   A: about 1 run, 5 actions by 1 person" in build_canvas(stats, 7, NOW)


def test_most_to_fix_merges_unknown_owners():
    stats = empty_stats()
    stats["hygiene_open"] = [
        {"guideline": "CTT-LAB-01", "owner": "NULL", "n": 9},
        {"guideline": "CTT-TAG-01", "owner": "j@x.com", "n": 5},
        {"guideline": "CTT-TAG-01", "owner": "unknown", "n": 3},
    ]
    assert "• Most to fix: unknown 12, j 5" in build_canvas(stats, 7, NOW)


def test_active_integrations():
    instances = [{"enabled": "true"}, {"enabled": "false"}, {"enabled": "true", "isBuiltin": True}, {"enabled": True}]
    assert active_integrations(instances) == 2
