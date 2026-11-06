import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import time
from typing import Any

CONFIG_LIST = "CTT - Config"
DAY_MS = 86_400_000

QUERIES = {
    key: " | ".join(stages)
    for key, stages in {
        "cases": [
            "dataset = cases",
            "dedup xdm.case.id by desc _insert_time",
            "comp count() as n by xdm.case.domain",
        ],
        "issues": [
            "dataset = issues",
            "dedup xdm.issue.id by desc _insert_time",
            "comp count() as n by xdm.issue.domain, xdm.issue.severity",
        ],
        "hygiene": [
            "dataset = issues",
            'filter xdm.issue.name ~= "^CTT - Hygiene - "',
            "dedup xdm.issue.id by desc _insert_time",
            'alter guideline = arrayindex(regextract(xdm.issue.name, "(CTT-[A-Z]+-[0-9]+)"), 0)',
            "comp count() as n by guideline",
        ],
        "playbooks": [
            "dataset = playbook_runs",
            'comp count() as runs, sum(if(playbook_status = "failed", 1, 0)) as failed by playbook_name',
            "sort desc runs",
            "limit 50",
        ],
        "commands": [
            "dataset = scripts_and_commands_metrics",
            "comp count() as runs, sum(if(is_error = true, 1, 0)) as errors by name, type",
            "sort desc runs",
            "limit 5",
        ],
        "logins": [
            "dataset = management_auditing",
            'filter management_auditing_type = ENUM.MANAGEMENT_AUDIT_AUTHENTICATION and subtype in ("Login", "SSO")',
            'filter email contains "@"',
            "comp count() as logins, count_distinct(email) as users",
        ],
        "changers": [
            "dataset = management_auditing",
            "filter management_auditing_result = ENUM.MANAGEMENT_AUDIT_SUCCESS",
            'filter email contains "@" and management_auditing_type != ENUM.MANAGEMENT_AUDIT_AUTHENTICATION',
            'filter subtype ~= "^(Add|Upload|Copy|Create|New|Edit|Delete|Change|Update|Install)"',
            "comp count() as changes by user_name",
            "sort desc changes",
            "limit 5",
        ],
        "endpoints": [
            "dataset = endpoints",
            "comp count() as n by endpoint_status",
        ],
        "agents": [
            "dataset = agentix_agents_actions",
            "comp count() as actions, count_distinct(user) as people by agent_name",
            "sort desc actions",
            "limit 5",
        ],
    }.items()
}


# ---------- pure helpers (unit tested) ----------


def human_bytes(n: float | None) -> str:
    value = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def total(rows: list[dict], field: str = "n") -> int:
    return int(sum(int(r.get(field) or 0) for r in rows))


def by(rows: list[dict], key: str, field: str = "n", title: bool = True) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in rows:
        k = str(r.get(key) or "unknown")
        k = k.title() if title else k
        out[k] = out.get(k, 0) + int(r.get(field) or 0)
    return dict(sorted(out.items(), key=lambda kv: -kv[1]))


def fmt_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{k} {v}" for k, v in counts.items()) or "none"


def top_rows(rows: list[dict], field: str, n: int) -> list[dict]:
    """XQL results do not keep the query's sort order once returned, so sort here."""
    return sorted(rows, key=lambda r: -int(r.get(field) or 0))[:n]


def build_message(stats: dict, days: int) -> str:
    r = dict(stats)
    r["playbooks"] = top_rows(r["playbooks"], "runs", 50)
    r["commands"] = top_rows(r["commands"], "runs", 5)
    r["changers"] = top_rows(r["changers"], "changes", 5)
    r["agents"] = top_rows(r["agents"], "actions", 5)
    lines = [f"*CTT weekly stats* (last {days} days)", ""]
    case_domains = fmt_counts(by(r["cases"], "xdm.case.domain"))
    lines.append(f":briefcase: *Cases:* {total(r['cases'])} new ({case_domains}); {r['open_cases']} open now")
    lines.append(
        f":rotating_light: *Issues:* {total(r['issues'])} new; by severity {fmt_counts(by(r['issues'], 'xdm.issue.severity'))}; "
        f"by domain {fmt_counts(by(r['issues'], 'xdm.issue.domain'))}"
    )
    runs = total(r["playbooks"], "runs")
    failed = total(r["playbooks"], "failed")
    top = ", ".join(f"{p.get('playbook_name')} ({p.get('runs')})" for p in r["playbooks"][:3]) or "none"
    lines.append(f":gear: *Playbook runs:* {runs} ({failed} failed). Busiest: {top}")
    cmds = ", ".join(f"{c.get('name')} ({c.get('runs')})" for c in r["commands"]) or "none"
    lines.append(f":hammer_and_wrench: *Top scripts/commands:* {cmds}")
    lines.append(
        f":inbox_tray: *Data ingested:* about {human_bytes(r['daily_bytes'])}/day across {r['datasets_with_data']} datasets. "
        f"Biggest: {', '.join(r['top_datasets']) or 'none'}"
    )
    if r.get("quota"):
        q = r["quota"]
        lines.append(f":abacus: *XQL compute:* {q.get('used', 0):.1f} of {q.get('license', 0):.0f} CU used today")
    logins = r["logins"][0] if r["logins"] else {}
    lines.append(f":busts_in_silhouette: *People:* {logins.get('users', 0)} signed in ({logins.get('logins', 0)} sign-ins)")
    changers = ", ".join(f"{c.get('user_name')} ({c.get('changes')})" for c in r["changers"]) or "none"
    lines.append(f":building_construction: *Most active builders:* {changers}")
    lines.append(f":computer: *Endpoints:* {total(r['endpoints'])} ({fmt_counts(by(r['endpoints'], 'endpoint_status'))})")
    agents = ", ".join(f"{a.get('agent_name')} ({a.get('people')} people)" for a in r["agents"]) or "none"
    lines.append(f":robot_face: *AI agents:* {total(r['agents'], 'actions')} actions. Most used: {agents}")
    lines.append(
        f":broom: *Hygiene issues raised:* {total(r['hygiene'])} ({fmt_counts(by(r['hygiene'], 'guideline', title=False))})"
    )
    return "\n".join(lines)


def dataset_summary(datasets: list[dict]) -> tuple[float, int, list[str]]:
    sized = [d for d in datasets if isinstance(d, dict) and d.get("Average Daily Size")]
    sized.sort(key=lambda d: -float(d.get("Average Daily Size") or 0))
    daily = sum(float(d.get("Average Daily Size") or 0) for d in sized)
    top = [f"{d.get('Dataset Name')} ({human_bytes(d.get('Average Daily Size'))}/day)" for d in sized[:3]]
    return daily, len(sized), top


# ---------- tenant I/O ----------


def core_post(uri: str, body: dict) -> Any:
    res = demisto.executeCommand("core-api-post", {"uri": uri, "body": json.dumps(body)})
    if is_error(res):
        raise DemistoException(get_error(res))
    response = res[0]["Contents"].get("response", {})
    return response.get("reply", response) if isinstance(response, dict) else response


def run_xql(query: str, days: int, timeout: int = 300) -> list[dict]:
    qid = core_post(
        "/public_api/v1/xql/start_xql_query",
        {"request_data": {"query": query, "timeframe": {"relativeTime": days * DAY_MS}}},
    )
    deadline = time.time() + timeout
    while True:
        reply = core_post(
            "/public_api/v1/xql/get_query_results",
            {"request_data": {"query_id": qid, "pending_flag": True, "limit": 1000, "format": "json"}},
        )
        status = str(reply.get("status", "")).upper()
        if status == "SUCCESS":
            return (reply.get("results") or {}).get("data") or []
        if status not in ("PENDING", "") or time.time() > deadline:
            raise DemistoException(f"XQL query {status or 'timed out'}: {reply.get('error') or query[:80]}")
        time.sleep(5)


def main():  # pragma: no cover
    try:
        args = demisto.args()
        cfg = {}
        res = demisto.executeCommand("getList", {"listName": CONFIG_LIST})
        if not is_error(res):
            cfg = json.loads(res[0]["Contents"] or "{}").get("stats", {})
        days = int(args.get("period_days") or cfg.get("period_days", 7))
        channel = args.get("channel") or cfg.get("slack_channel", "")
        send = argToBoolean(args.get("send", "true"))

        stats: dict[str, Any] = {}
        errors = []
        for key, query in QUERIES.items():
            try:
                stats[key] = run_xql(query, days)
            except Exception as e:
                stats[key] = []
                errors.append(f"{key}: {e}")
        try:
            open_cases = core_post(
                "/public_api/v1/case/search",
                {
                    "request_data": {
                        "filters": [{"field": "status_progress", "operator": "nin", "value": ["Resolved"]}],
                        "search_from": 0,
                        "search_to": 1,
                    }
                },
            )
            stats["open_cases"] = open_cases.get("TOTAL_COUNT", "?")
        except Exception as e:
            stats["open_cases"] = "?"
            errors.append(f"open cases: {e}")
        try:
            daily, count, top = dataset_summary(core_post("/public_api/v1/xql/get_datasets", {"request_data": {}}) or [])
            stats.update(daily_bytes=daily, datasets_with_data=count, top_datasets=top)
        except Exception as e:
            stats.update(daily_bytes=0, datasets_with_data=0, top_datasets=[])
            errors.append(f"datasets: {e}")
        try:
            q = core_post("/public_api/v1/xql/get_quota", {"request_data": {}})
            stats["quota"] = {"used": float(q.get("daily_used_quota") or 0), "license": float(q.get("license_quota") or 0)}
        except Exception as e:
            errors.append(f"quota: {e}")

        message = build_message(stats, days)
        sent_to = ""
        if send and channel:
            send_args = {"channel": channel, "message": message}
            if cfg.get("slack_instance"):
                send_args["using"] = cfg["slack_instance"]
            else:
                send_args["using-brand"] = "SlackV3"
            res = demisto.executeCommand("send-notification", send_args)
            if is_error(res):
                errors.append(f"slack: {get_error(res)}")
            else:
                sent_to = channel
        md = message.replace("*", "**")
        md += (
            f"\n\nPosted to Slack channel {sent_to}."
            if sent_to
            else "\n\nNot posted to Slack (no channel configured or send=false)."
        )
        if errors:
            md += tableToMarkdown("Errors", [{"Error": e} for e in errors])
        return_results(
            CommandResults(readable_output=md, outputs_prefix="CTT.WeeklyStats", outputs={"message": message, "errors": errors})
        )
    except Exception as e:
        return_error(f"CTTWeeklyStats failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
