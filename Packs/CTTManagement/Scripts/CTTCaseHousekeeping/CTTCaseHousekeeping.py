import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import re
import textwrap
import time
from collections import Counter
from datetime import UTC, datetime
from typing import Any

CONFIG_LIST = "CTT - Config"
REGISTRY_LIST = "CTT - Registry"
STATE_LIST = "CTT - Case State"
NOTIFY_STATE = "CTT - Notify State"
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
PAGE = 100  # the public API refuses search sizes above 100
WIDTH = 46  # same box width as the hygiene DMs
TAG_RE = re.compile(r"^\s*([A-Za-z0-9]{2,16})\s*[-_]")
IP10_RE = re.compile(r"\b10\.(\d{1,3})\.\d{1,3}\.\d{1,3}\b")
NO_OWNER = {"", "unknown", "unassigned", "central", "null", "none"}
DEFAULTS = {
    "domains": ["Security"],
    "assign_after_hours": 24,
    "suggest_after_hours": 24,
    "close_after_days": 7,
    "skip_starred": True,
    "resolve_reason": "Resolved - Security Testing",
    "max_closes_per_run": 200,
    "max_assigns_per_run": 100,
    "retry_owner_hours": 24,
    "dry_run": False,
}

# BEGIN GENERATED ENDPOINT_OWNER_QUERY (tools/correlation_rules/gen_correlation_rules.py; do not edit)
ENDPOINT_OWNER_QUERY = (
    "dataset = endpoints\n"
    "| dedup endpoint_id by desc last_seen\n"
    '| alter etags = arrayconcat(json_extract_scalar_array(tags, "$.endpoint_tags"), json_extract_scalar_'
    'array(tags, "$.server_tags"))\n'
    '| alter etags = if(etags = null or array_length(etags) = 0, arraycreate("-"), etags)\n'
    '| alter policy_tag = lowercase(arrayindex(regextract(assigned_prevention_policy, "^\\s*([A-Za-z0-9]{2'
    ',16})\\s*[-_]"), 0)), package_tag = lowercase(arrayindex(regextract(installation_package, "^\\s*([A-Za'
    '-z0-9]{2,16})\\s*[-_]"), 0))\n'
    '| alter ip10 = arrayindex(arrayfilter(ip_address, "@element" ~= "^10\\."), 0)\n'
    '| alter ip_octet = arrayindex(regextract(ip10, "^10\\.(\\d+)\\."), 0)\n'
    "| arrayexpand etags\n"
    "| alter etag = lowercase(etags)\n"
    '| join type = left (dataset = ctt_registry | filter role != "central" | alter etag = ctt_tag, etag_o'
    "wner = owner_email | fields etag, etag_owner) as te te.etag = etag\n"
    "| comp max(etag_owner) as tag_owner by endpoint_id, endpoint_name, ip10, ip_octet, policy_tag, packa"
    "ge_tag, assigned_prevention_policy, installation_package\n"
    '| join type = left (dataset = ctt_registry | filter role != "central" | alter policy_tag = ctt_tag, '
    "policy_owner = owner_email | fields policy_tag, policy_owner) as tp tp.policy_tag = policy_tag\n"
    '| join type = left (dataset = ctt_registry | filter role != "central" | alter package_tag = ctt_tag,'
    " package_owner = owner_email | fields package_tag, package_owner) as tk tk.package_tag = package_tag"
    "\n"
    '| join type = left (dataset = ctt_registry | filter lab_octet != "" | comp max(owner_email) as range'
    "_owner by lab_octet | alter ip_octet = lab_octet | fields ip_octet, range_owner) as tr tr.ip_octet ="
    " ip_octet\n"
    '| join type = left (dataset = ctt_object_owners | filter object_kind = "Agent installer" and object_'
    'name !~= "^(?i)ctt\\s*[-_]" | alter installation_package = object_name, installer_owner = coalesce(cr'
    "eator, last_editor) | fields installation_package, installer_owner) as io io.installation_package = "
    "installation_package\n"
    '| join type = left (dataset = ctt_object_owners | filter object_kind = "Policy rule" and object_name'
    ' !~= "^(?i)(ctt\\s*[-_]|default)" | alter assigned_prevention_policy = object_name, policy_editor = l'
    "ast_editor | fields assigned_prevention_policy, policy_editor) as po po.assigned_prevention_policy ="
    " assigned_prevention_policy\n"
    '| alter installer_owner = if(installer_owner = "", null, installer_owner), policy_editor = if(policy'
    '_editor = "", null, policy_editor)\n'
    "| alter owner = coalesce(tag_owner, policy_owner, package_owner, installer_owner, policy_editor)\n"
    '| alter owner_source = if(tag_owner != null, "endpoint tag", if(policy_owner != null, "tag in its po'
    'licy name", if(package_owner != null, "tag in its installer name", if(installer_owner != null, conca'
    't("creator of installer ", installation_package), if(policy_editor != null, concat("last editor of p'
    'olicy ", assigned_prevention_policy), null)))))\n'
    '| alter owner_label = coalesce(owner, "unknown"), owner_note = if(owner != null, concat("Owner: ", o'
    'wner, " (", owner_source, ")."), "No owner found: add your tag to the endpoint.")\n'
    "| fields endpoint_id, endpoint_name, ip10, owner, owner_source"
)
# END GENERATED ENDPOINT_OWNER_QUERY


# ---------- pure helpers (unit tested) ----------


def parse_tag(name: str) -> str | None:
    m = TAG_RE.match(name or "")
    return m.group(1).lower() if m else None


def host_endpoint_ids(case: dict) -> list[str]:
    """Endpoint IDs from the case's hosts ('hostname:endpoint_id'); 'ip:ip' entries have none."""
    out = []
    for h in case.get("hosts") or []:
        name, _, eid = str(h).rpartition(":")
        if eid and eid != name and not re.fullmatch(r"[\d.]+", eid):
            out.append(eid)
    return out


def lab_octets(case: dict) -> list[str]:
    """The x of every 10.x.y.z address in the case's hosts and description, in order."""
    text = " ".join([*(str(h).split(":")[0] for h in case.get("hosts") or []), str(case.get("description") or "")])
    return IP10_RE.findall(text)


def registry_maps(rows: list[dict]) -> tuple[dict[str, str], dict[str, str], dict[str, dict]]:
    """(tag -> owner email, lab octet -> owner email, owner email -> person entry)."""
    tags, octets, people = {}, {}, {}
    for r in rows:
        email = str(r.get("owner_email") or "").lower()
        if not email or r.get("active") == "false":
            continue
        if r.get("tag") and r.get("role") != "central":
            tags[str(r["tag"]).lower()] = email
        if r.get("lab_octet"):
            octets[str(r["lab_octet"])] = email
        if email not in people or r.get("tag_kind") == "primary":
            people[email] = r
    return tags, octets, people


def pick_owner(
    rule_names: list[str],
    endpoint_owners: list[str],
    octets: list[str],
    tag_owner: dict[str, str],
    octet_owner: dict[str, str],
) -> tuple[str, str]:
    """(owner email, how it was found). The tag of the rule behind the case's issues wins, then the
    owner of an endpoint in the case, then the lab range of a 10.x address. Within one source the
    most frequent owner wins."""
    candidates = [
        ("correlation rule tag", [tag_owner.get(parse_tag(n) or "", "") for n in rule_names]),
        ("endpoint owner", [o.lower() for o in endpoint_owners if o]),
        ("lab range", [octet_owner.get(o, "") for o in octets]),
    ]
    for source, owners in candidates:
        owners = [o for o in owners if o and o not in NO_OWNER and "@" in o]
        if owners:
            return Counter(owners).most_common(1)[0][0], source
    return "", ""


def plan_case(case: dict, state: dict, now_ms: int, cfg: dict, latest_issue_ms: int | None) -> list[str]:
    """Which actions are due for one open case: close, assign, suggest (each done once)."""
    if cfg["skip_starred"] and case.get("starred"):
        return []
    created = int(case.get("creation_time") or now_ms)
    if now_ms - created >= cfg["close_after_days"] * DAY_MS:
        return ["close"]
    actions = []
    if not case.get("assigned_user_mail") and now_ms - created >= cfg["assign_after_hours"] * HOUR_MS:
        checked = int(state.get("owner_checked") or 0)
        if not state.get("assigned") and now_ms - checked >= cfg["retry_owner_hours"] * HOUR_MS:
            actions.append("assign")
    quiet_since = latest_issue_ms or created
    if not state.get("suggested") and now_ms - quiet_since >= cfg["suggest_after_hours"] * HOUR_MS:
        actions.append("suggest")
    return actions


def decide_dm(owner: str, entry: dict, notify: dict, sent_today: int) -> tuple[bool, str]:
    """Whether to DM an owner, following notify.mode, the allowlist and the daily limit."""
    mode = notify.get("mode", "off")
    if not entry or not entry.get("slack_id"):
        return False, "no Slack ID in the registry"
    if mode == "off":
        return False, "DMs are off (notify.mode)"
    if mode == "allowlist" and owner not in {a.lower() for a in notify.get("allowlist") or []}:
        return False, "not on notify.allowlist"
    if mode == "admins_only" and entry.get("role") != "admin":
        return False, "DMs go to CTT admins only"
    if sent_today >= int(notify.get("max_dms_per_owner_per_day", 3)):
        return False, "daily DM limit reached"
    return True, "sent"


def _header(left: str, right: str) -> list[str]:
    inner = WIDTH - 2
    text = f"  {left}"
    text = text + " " * max(1, inner - len(text) - len(right) - 2) + right + "  "
    return ["╭" + "─" * inner + "╮", "│" + text[:inner].ljust(inner) + "│", "╰" + "─" * inner + "╯"]


def _case_line(case: dict, now_ms: int) -> list[str]:
    days = max(0, int((now_ms - int(case.get("creation_time") or now_ms)) // DAY_MS))
    text = f"• #{case.get('case_id')} {case.get('case_name') or ''} ({days}d)"
    lines = textwrap.wrap(text, WIDTH, subsequent_indent="  ") or [text]
    url = case.get("xdr_url")
    return [*lines[:2], *([f"  {url}"] if url else [])]


def build_digest(first_name: str, groups: dict[str, list[dict]], now_ms: int, max_items: int = 6) -> str:
    """One DM per owner with the cases assigned to them, those to consider closing and those closed."""
    titles = {
        "assign": (
            "ASSIGNED TO YOU",
            "Open for a day without an owner, so they are now yours. Resolve them as Security Testing when your test is done.",
        ),
        "suggest": ("CLOSE IF DONE", "No new issues for a day. Resolve them as Security Testing to stop new issues grouping in."),
        "close": ("CLOSED", "Open for 7 days, resolved as Security Testing."),
    }
    out = [*_header("CTT CASES", "CTT-CASE"), "", f"Hi {first_name or 'there'},"]
    for key in ("assign", "suggest", "close"):
        cases = groups.get(key) or []
        if not cases:
            continue
        title, note = titles[key]
        out += ["", f"{title} ({len(cases)})", *textwrap.wrap(note, WIDTH)]
        for case in cases[:max_items]:
            out += _case_line(case, now_ms)
        if len(cases) > max_items:
            out.append(f"• … and {len(cases) - max_items} more")
    out += ["", "─" * WIDTH, "Star a case to keep it open past 7 days.", "Questions? Ask in the CTT channel."]
    return "\n".join(out)


def prune_state(state: dict, open_ids: set[str]) -> dict:
    return {k: v for k, v in state.items() if k in open_ids}


# ---------- tenant I/O ----------


def core_post(uri: str, body: dict) -> Any:
    res = demisto.executeCommand("core-api-post", {"uri": uri, "body": json.dumps(body)})
    if is_error(res):
        raise DemistoException(f"core-api-post {uri} failed: {get_error(res)}")
    response = res[0]["Contents"].get("response", {})
    return response.get("reply", response) if isinstance(response, dict) else response


def get_list_json(name: str, default: Any) -> Any:
    res = demisto.executeCommand("getList", {"listName": name})
    if is_error(res) or not res[0].get("Contents") or "Item not found" in str(res[0].get("Contents")):
        return default
    try:
        return json.loads(res[0]["Contents"])
    except ValueError:
        return default


def save_list_json(name: str, data: Any) -> None:
    payload = json.dumps(data)
    if is_error(demisto.executeCommand("setList", {"listName": name, "listData": payload})):
        demisto.executeCommand("createList", {"listName": name, "listData": payload})


def open_cases(domains: list[str]) -> list[dict]:
    filters = [
        {"field": "status_progress", "operator": "nin", "value": ["Resolved"]},
        {"field": "case_domain", "operator": "in", "value": domains},
    ]
    cases: list[dict] = []
    for start in range(0, 5000, PAGE):
        body = {
            "request_data": {
                "filters": filters,
                "search_from": start,
                "search_to": start + PAGE,
                "sort": {"field": "creation_time", "keyword": "asc"},
            }
        }
        page = core_post("/public_api/v1/case/search", body).get("DATA") or []
        cases.extend(page)
        if len(page) < PAGE:
            break
    return cases


def issues_by_id(ids: list[int]) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for start in range(0, len(ids), PAGE):
        chunk = ids[start : start + PAGE]
        body = {
            "request_data": {
                "filters": [{"field": "id", "operator": "in", "value": chunk}],
                "search_from": 0,
                "search_to": PAGE,
            }
        }
        for issue in core_post("/public_api/v1/issue/search", body).get("DATA") or []:
            out[int(issue.get("id"))] = issue
    return out


def correlation_rule_names() -> dict[str, str]:
    names: dict[str, str] = {}
    for start in range(0, 3000, PAGE):
        res = core_post("/public_api/v1/correlations/get", {"request_data": {"search_from": start, "search_to": start + PAGE}})
        page = res.get("objects", []) if isinstance(res, dict) else []
        names.update({str(r.get("rule_id")): str(r.get("name") or "") for r in page})
        if len(page) < PAGE:
            break
    return names


def run_xql(query: str, timeout: int = 300) -> list[dict]:
    qid = core_post(
        "/public_api/v1/xql/start_xql_query",
        {"request_data": {"query": query, "timeframe": {"relativeTime": DAY_MS}}},
    )
    deadline = time.time() + timeout
    while True:
        res = core_post(
            "/public_api/v1/xql/get_query_results",
            {"request_data": {"query_id": qid, "pending_flag": True, "limit": 1000, "format": "json"}},
        )
        if res.get("status") == "SUCCESS":
            return (res.get("results") or {}).get("data") or []
        if res.get("status") not in ("PENDING", None) or time.time() > deadline:
            raise DemistoException(f"XQL query {res.get('status') or 'timed out'}")
        time.sleep(5)


def update_case(case_id: Any, data: dict) -> None:
    core_post(f"/public_api/v1/case/update/{case_id}", {"request_data": {"update_data": data}})


def main():  # pragma: no cover
    try:
        args = demisto.args()
        cfg_all = get_list_json(CONFIG_LIST, {})
        cfg = {**DEFAULTS, **(cfg_all.get("cases") or {})}
        dry_run = argToBoolean(args.get("dry_run")) if args.get("dry_run") not in (None, "") else bool(cfg["dry_run"])
        notify = cfg_all.get("notify") or {}
        tag_owner, octet_owner, people = registry_maps(get_list_json(REGISTRY_LIST, []))
        state = get_list_json(STATE_LIST, {})
        now_ms = int(time.time() * 1000)
        errors: list[str] = []

        cases = open_cases(cfg["domains"])
        open_ids = {str(c.get("case_id")) for c in cases}
        state = prune_state(state, open_ids)
        latest_ids = {str(c.get("case_id")): max(c.get("issue_ids") or [0]) for c in cases}
        latest = issues_by_id(sorted({i for i in latest_ids.values() if i}))

        plans = {}
        for c in cases:
            cid = str(c.get("case_id"))
            issue = latest.get(latest_ids[cid]) or {}
            latest_ms = issue.get("_insert_time") or issue.get("observation_time")
            plans[cid] = plan_case(c, state.get(cid, {}), now_ms, cfg, int(latest_ms) if latest_ms else None)

        closes = [c for c in cases if "close" in plans[str(c.get("case_id"))]][: int(cfg["max_closes_per_run"])]
        assigns = [c for c in cases if "assign" in plans[str(c.get("case_id"))]][: int(cfg["max_assigns_per_run"])]

        # Owners for the cases to assign: rule tags, endpoint owners, lab ranges.
        endpoint_owner: dict[str, str] = {}
        rule_names: dict[str, str] = {}
        if assigns:
            try:
                endpoint_owner = {str(r.get("endpoint_id")): str(r.get("owner") or "") for r in run_xql(ENDPOINT_OWNER_QUERY)}
            except Exception as e:
                errors.append(f"endpoint owners: {e}")
            try:
                rule_names = correlation_rule_names()
            except Exception as e:
                errors.append(f"correlation rules: {e}")
        recent_ids = sorted({i for c in assigns for i in sorted(c.get("issue_ids") or [])[-5:]})
        recent = issues_by_id(recent_ids) if assigns and rule_names else {}

        digest: dict[str, dict[str, list[dict]]] = {}
        rows = []
        for c in closes:
            cid = c.get("case_id")
            try:
                if not dry_run:
                    update_case(
                        cid,
                        {
                            "status_progress": "Resolved",
                            "resolve_reason": cfg["resolve_reason"],
                            "resolve_comment": (
                                f"Closed by CTT case housekeeping after {cfg['close_after_days']} days open (CTT-CASE-01). "
                                "Star a case to keep it open."
                            ),
                        },
                    )
                owner = str(c.get("assigned_user_mail") or "").lower()
                if owner:
                    digest.setdefault(owner, {}).setdefault("close", []).append(c)
                rows.append({"Case": cid, "Action": "closed", "Owner": owner or "-"})
            except Exception as e:
                errors.append(f"close {cid}: {e}")

        for c in assigns:
            cid = str(c.get("case_id"))
            names = [
                rule_names.get(str(recent.get(i, {}).get("detection.rule_id")), "") for i in sorted(c.get("issue_ids") or [])[-5:]
            ]
            owner, source = pick_owner(
                [n for n in names if n],
                [endpoint_owner.get(e, "") for e in host_endpoint_ids(c)],
                lab_octets(c),
                tag_owner,
                octet_owner,
            )
            entry = state.setdefault(cid, {})
            entry["owner_checked"] = now_ms
            if not owner:
                rows.append({"Case": cid, "Action": "no owner found", "Owner": "-"})
                continue
            try:
                if not dry_run:
                    update_case(cid, {"assigned_user": owner})
                entry["assigned"] = owner
                c["assigned_user_mail"] = owner
                digest.setdefault(owner, {}).setdefault("assign", []).append(c)
                rows.append({"Case": cid, "Action": f"assigned ({source})", "Owner": owner})
            except Exception as e:
                errors.append(f"assign {cid} to {owner}: {e}")

        assigned_now = {str(c.get("case_id")) for c in assigns if state.get(str(c.get("case_id")), {}).get("assigned")}
        for c in cases:
            cid = str(c.get("case_id"))
            owner = str(c.get("assigned_user_mail") or "").lower()
            if "suggest" not in plans[cid] or not owner:
                continue
            state.setdefault(cid, {})["suggested"] = now_ms
            if cid in assigned_now:
                continue  # the assignment line already asks to resolve it when done
            digest.setdefault(owner, {}).setdefault("suggest", []).append(c)
            rows.append({"Case": cid, "Action": "suggest closing", "Owner": owner})

        day = datetime.now(UTC).strftime("%Y-%m-%d")
        sent_state = get_list_json(NOTIFY_STATE, {})
        sent_today = (sent_state.get(day) or {}) if isinstance(sent_state, dict) else {}
        dms = []
        for owner, groups in sorted(digest.items()):
            entry = people.get(owner, {})
            ok, reason = decide_dm(owner, entry, notify, int(sent_today.get(owner, 0)))
            if ok and not dry_run:
                first = str(entry.get("owner_name") or "").split(" ")[0]
                content = build_digest(first, groups, now_ms)
                res = demisto.executeCommand(
                    "CTTHygieneSendDM", {"slack_user_id": entry.get("slack_id"), "owner_email": owner, "content": content}
                )
                if is_error(res):
                    errors.append(f"DM {owner}: {get_error(res)}")
                    reason = "send failed"
            dms.append(
                {
                    "Owner": owner,
                    "Cases": sum(len(v) for v in groups.values()),
                    "DM": reason if not dry_run or not ok else "would send",
                }
            )

        if not dry_run:
            save_list_json(STATE_LIST, state)
        summary = {
            "OpenCases": len(cases),
            "Closed": len(closes),
            "Assigned": sum(1 for r in rows if r["Action"].startswith("assigned")),
            "NoOwner": sum(1 for r in rows if r["Action"] == "no owner found"),
            "Suggested": sum(1 for r in rows if r["Action"] == "suggest closing"),
            "DryRun": dry_run,
        }
        md = tableToMarkdown(f"CTT case housekeeping{' (dry run)' if dry_run else ''}", summary)
        md += tableToMarkdown("DMs", dms) if dms else ""
        md += tableToMarkdown("Actions (first 50)", rows[:50]) if rows else ""
        if errors:
            md += tableToMarkdown("Errors", [{"Error": e} for e in errors[:30]])
        return_results(
            CommandResults(readable_output=md, outputs_prefix="CTT.CaseHousekeeping", outputs={**summary, "Errors": errors})
        )
    except Exception as e:
        return_error(f"CTTCaseHousekeeping failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
