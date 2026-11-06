import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

CONFIG_LIST = "CTT - Config"
DAY_MS = 86_400_000
SGT = timezone(timedelta(hours=8))

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
        "hygiene_open": [
            "dataset = issues",
            'filter xdm.issue.name ~= "^CTT - Hygiene - "',
            "dedup xdm.issue.id by desc _insert_time",
            'filter xdm.issue.status.progress != "RESOLVED"',
            'alter guideline = arrayindex(regextract(xdm.issue.name, "(CTT-[A-Z]+-[0-9]+)"), 0)',
            'alter owner = arrayindex(regextract(xdm.issue.description, "\\[owner: ([^\\]]+)\\]"), 0)',
            "comp count() as n by guideline, owner",
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
            "comp count_distinct(conversation_id) as plans, count() as actions, count_distinct(user) as people by agent_name",
            "sort desc plans",
            "limit 5",
        ],
    }.items()
}
# XSIAM 8.15 stores conversation_id but its query validator rejects the field ("unknown field").
# There, a run is estimated as one person's activity with an agent within a 10-minute window.
AGENTS_FALLBACK = (
    "dataset = agentix_agents_actions | bin _time span = 10m"
    ' | alter run_key = concat(user, "|", to_string(_time))'
    " | comp count_distinct(run_key) as runs, count() as actions, count_distinct(user) as people by agent_name"
    " | sort desc runs | limit 5"
)


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


def fmt_counts(counts: dict[str, int], limit: int = 6) -> str:
    return ", ".join(f"{k} {v}" for k, v in list(counts.items())[:limit]) or "none"


def top_rows(rows: list[dict], field: str, n: int) -> list[dict]:
    """XQL results do not keep the query's sort order once returned, so sort here."""
    return sorted(rows, key=lambda r: -int(r.get(field) or 0))[:n]


def dataset_summary(datasets: list[dict]) -> tuple[float, int, list[str]]:
    sized = [d for d in datasets if isinstance(d, dict) and d.get("Average Daily Size")]
    sized.sort(key=lambda d: -float(d.get("Average Daily Size") or 0))
    daily = sum(float(d.get("Average Daily Size") or 0) for d in sized)
    top = [f"{d.get('Dataset Name')} ({human_bytes(d.get('Average Daily Size'))}/day)" for d in sized[:3]]
    return daily, len(sized), top


def health_light(open_issues: int) -> str:
    return "🟢" if open_issues == 0 else "🟡" if open_issues < 10 else "🔴"


def owner_label(owner: str) -> str:
    owner = (owner or "unknown").strip()
    if owner.lower() in ("null", "none", ""):
        owner = "unknown"
    return owner.split("@")[0] if "@" in owner else owner


def plural(n: Any, one: str, many: str = "") -> str:
    return f"{n} {one if str(n) == '1' else many or one + 's'}"


def thousands(n: Any) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


def build_canvas(r: dict, days: int, now: datetime, tenant_url: str = "") -> str:
    """Plain text for the 'Tenant Status' canvas: the Slack workflow shows content without
    rendering Markdown, so the layout is emoji headers, short lines and bullets."""
    hygiene = r["hygiene_open"]
    open_issues = total(hygiene)
    owners: dict[str, int] = {}
    for k, v in by(hygiene, "owner", title=False).items():
        owners[owner_label(k)] = owners.get(owner_label(k), 0) + v
    owners = dict(sorted(owners.items(), key=lambda kv: -kv[1]))
    playbooks = top_rows(r["playbooks"], "runs", 50)
    logins = r["logins"][0] if r["logins"] else {}
    builders = ", ".join(f"{c.get('user_name')} ({c.get('changes')})" for c in top_rows(r["changers"], "changes", 5)) or "none"
    lines = [
        "CTT TENANT STATUS",
        f"Updated {now.strftime('%a %d %b %Y %H:%M')} SGT by the CTT Management pack",
        *([tenant_url] if tenant_url else []),
        "",
        f"{health_light(open_issues)} HYGIENE",
        f"• Open hygiene issues: {open_issues} ({fmt_counts(by(hygiene, 'guideline', title=False))})",
        f"• Most to fix: {fmt_counts(owners, 5)}",
        "• Each issue is assigned to its owner. Fix the object; the inventory check closes its own issues.",
        "",
        f"📊 LAST {days} DAYS",
        f"• Cases: {total(r['cases'])} new ({fmt_counts(by(r['cases'], 'xdm.case.domain'))}); "
        f"{thousands(r['open_cases'])} open now, {thousands(r.get('new_cases_24h', '?'))} new in 24h",
        f"• Issues: {total(r['issues'])} new ({fmt_counts(by(r['issues'], 'xdm.issue.severity'))})",
        f"• People signed in: {logins.get('users', 0)} ({logins.get('logins', 0)} sign-ins)",
        f"• Most active builders: {builders}",
        "",
        "⚙️ AUTOMATION",
        f"• Playbook runs: {total(playbooks, 'runs')} ({total(playbooks, 'failed')} failed)",
    ]
    top_pb = top_rows(playbooks, "runs", 8)
    if top_pb:
        lines.append("• Top playbooks:")
        lines += [
            f"   {p.get('playbook_name')}: {p.get('runs')} runs"
            + (f", {p.get('failed')} failed" if int(p.get("failed") or 0) else "")
            for p in top_pb
        ]
    commands = top_rows(r["commands"], "runs", 5)
    lines.append("• Top scripts and commands: " + (", ".join(f"{c.get('name')} ({c.get('runs')})" for c in commands) or "none"))
    unit = next((u for u in ("plans", "runs") if any(u in a for a in r["agents"])), "actions")
    agents = top_rows(r["agents"], unit, 5)
    if agents:
        lines.append("• Top AI agents:")
        for a in agents:
            count = (
                f"{plural(a.get('plans'), 'plan')}, "
                if unit == "plans"
                else f"about {plural(a.get('runs'), 'run')}, "
                if unit == "runs"
                else ""
            )
            people = plural(a.get("people"), "person", "people")
            lines.append(f"   {a.get('agent_name')}: {count}{plural(a.get('actions'), 'action')} by {people}")
    else:
        lines.append("• AI agents: no activity")
    lines += [
        "",
        "📥 DATA AND INTEGRATIONS",
        f"• Ingested: about {human_bytes(r['daily_bytes'])}/day across {r['datasets_with_data']} datasets",
        f"• Biggest datasets: {', '.join(r['top_datasets']) or 'none'}",
        f"• Integrations active: {thousands(r.get('integrations_active', '?'))}",
    ]
    if r.get("quota"):
        lines.append(f"• XQL compute today: {r['quota']['used']:.1f} of {r['quota']['license']:.0f} CU")
    lines += [
        "",
        "💻 ENDPOINTS",
        f"• Endpoints: {total(r['endpoints'])} ({fmt_counts(by(r['endpoints'], 'endpoint_status'))})",
    ]
    return "\n".join(lines)


def build_topic(r: dict, now: datetime) -> str:
    """One line for the channel topic (Slack allows 250 characters): tenant activity only."""
    endpoints = by(r["endpoints"], "endpoint_status")
    parts = [
        f"CTT {now.strftime('%a %d %b')}",
        f"{thousands(r['open_cases'])} open cases (+{thousands(r.get('new_cases_24h', '?'))} in 24h)",
        f"{endpoints.get('Connected', 0)} endpoints connected",
        f"{human_bytes(r['daily_bytes'])}/day ingested",
        f"{thousands(r.get('integrations_active', '?'))} integrations active",
    ]
    return " · ".join(parts)[:250]


def filtered_count(reply: dict) -> Any:
    value = reply.get("FILTER_COUNT")
    return value if value is not None else reply.get("TOTAL_COUNT", "?")


def active_integrations(instances: list[dict]) -> int:
    """Enabled integration instances, without the built-in ones every tenant has."""
    return sum(1 for i in instances if isinstance(i, dict) and str(i.get("enabled")).lower() == "true" and not i.get("isBuiltin"))


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


def collect(days: int, errors: list[str]) -> dict:
    stats: dict[str, Any] = {}
    for key, query in QUERIES.items():
        try:
            # Open hygiene issues are counted over 90 days; the rest over the reporting period.
            stats[key] = run_xql(query, 90 if key == "hygiene_open" else days)
        except Exception as e:
            stats[key] = []
            error = str(e)
            if key == "agents":
                try:
                    stats[key] = run_xql(AGENTS_FALLBACK, days)
                    continue
                except Exception as e2:
                    error = str(e2)
            errors.append(f"{key}: {error}")
    try:
        body = {
            "request_data": {
                "filters": [{"field": "status_progress", "operator": "nin", "value": ["Resolved"]}],
                "search_from": 0,
                "search_to": 1,
            }
        }
        # FILTER_COUNT is the count that matches the filters; TOTAL_COUNT counts every case.
        stats["open_cases"] = filtered_count(core_post("/public_api/v1/case/search", body))
        since = int(time.time() * 1000) - DAY_MS
        body["request_data"]["filters"] = [{"field": "creation_time", "operator": "gte", "value": since}]
        stats["new_cases_24h"] = filtered_count(core_post("/public_api/v1/case/search", body))
    except Exception as e:
        stats.setdefault("open_cases", "?")
        stats.setdefault("new_cases_24h", "?")
        errors.append(f"cases: {e}")
    try:
        res = core_post("/settings/integration/search", {"size": 1000})
        stats["integrations_active"] = active_integrations(res.get("instances") or [] if isinstance(res, dict) else [])
    except Exception as e:
        stats["integrations_active"] = "?"
        errors.append(f"integrations: {e}")
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
    return stats


def send(action: str, content: str, errors: list[str]) -> bool:
    res = demisto.executeCommand("ctt-slack-webhook-send", {"action": action, "content": content})
    if is_error(res):
        errors.append(f"slack {action}: {get_error(res)}")
        return False
    return True


def main():  # pragma: no cover
    try:
        args = demisto.args()
        cfg = {}
        res = demisto.executeCommand("getList", {"listName": CONFIG_LIST})
        if not is_error(res):
            cfg = json.loads(res[0]["Contents"] or "{}").get("status", {})
        days = int(args.get("period_days") or cfg.get("period_days", 7))
        do_send = argToBoolean(args.get("send", "true"))
        errors: list[str] = []
        stats = collect(days, errors)
        now = datetime.now(SGT)
        canvas = build_canvas(stats, days, now, (demisto.demistoUrls() or {}).get("server", ""))
        topic = build_topic(stats, now)
        sent = []
        if do_send and cfg.get("update_canvas", True) and send("canvas_update", canvas, errors):
            sent.append("canvas")
        if do_send and cfg.get("update_topic", True) and send("channel_update_topic", topic, errors):
            sent.append("topic")
        md = f"**Topic:** {topic}\n\n{canvas}\n\n" + (f"Updated in Slack: {', '.join(sent)}." if sent else "Not sent to Slack.")
        if errors:
            md += tableToMarkdown("Errors", [{"Error": e} for e in errors])
        return_results(
            CommandResults(
                readable_output=md,
                outputs_prefix="CTT.TenantStatus",
                outputs={"canvas": canvas, "topic": topic, "sent": sent, "errors": errors},
            )
        )
    except Exception as e:
        return_error(f"CTTTenantStatus failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
