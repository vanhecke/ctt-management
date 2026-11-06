import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import hashlib
import json
import re
import time
from typing import Any

CONFIG_LIST = "CTT - Config"
STATE_LIST = "CTT - Sweep State"
TAG_RE = re.compile(r"^\s*([A-Za-z0-9]{2,16})\s*[-_]")
ISSUE_PREFIX = "CTT - Hygiene"
TITLES = {
    "CTT-TAG-01": "Objects without a registered owner tag",
    "CTT-TAG-02": "Playbooks missing the owner tag field",
    "CTT-LIFE-02": "Objects owned by an inactive DC",
    "CTT-CASE-01": "Stale open Security cases",
}
DAY_MS = 86_400_000


# ---------- pure helpers (unit tested) ----------


def parse_tag(name: str) -> str | None:
    m = TAG_RE.match(name or "")
    return m.group(1).lower() if m else None


def registry_index(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("tag", "")).lower(): r for r in rows if r.get("tag")}


def check_object(obj: dict, registry: dict[str, dict]) -> list[dict]:
    """obj: kind, name, creator (email or ''), tags (list, playbooks only). Returns findings."""
    name = obj.get("name") or ""
    tag = parse_tag(name)
    entry = registry.get(tag or "")
    base = {"kind": obj["kind"], "name": name}
    if not entry:
        detail = "no tag prefix" if not tag else f"prefix '{tag}' is not a registered tag"
        return [{**base, "guideline": "CTT-TAG-01", "owner": (obj.get("creator") or "unknown").lower(), "detail": detail}]
    findings = []
    owner = entry.get("owner_email") or "central"
    if entry.get("active") == "false":
        findings.append({**base, "guideline": "CTT-LIFE-02", "owner": owner, "detail": f"tag '{tag}' belongs to an inactive DC"})
    if obj["kind"] == "Playbook" and entry.get("role") != "central":
        owner_tags = {t for t, r in registry.items() if r.get("owner_email") == entry.get("owner_email")}
        if not {str(t).lower() for t in (obj.get("tags") or [])} & owner_tags:
            findings.append(
                {**base, "guideline": "CTT-TAG-02", "owner": owner, "detail": f"Tags field lacks the owner's tag ({tag})"}
            )
    return findings


def check_case(case: dict, now_ms: int, stale_days: int) -> dict | None:
    modified = case.get("modification_time") or case.get("creation_time") or now_ms
    idle_days = int((now_ms - modified) // DAY_MS)
    if idle_days < stale_days:
        return None
    return {
        "kind": "Case",
        "name": f"#{case.get('case_id')} {case.get('case_name', '')}".strip(),
        "guideline": "CTT-CASE-01",
        "owner": (case.get("assigned_user") or "unassigned").lower(),
        "detail": f"open, no change for {idle_days} days",
    }


def group_findings(findings: list[dict]) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for f in findings:
        key = f"{f['guideline']}|{f['owner']}"
        g = groups.setdefault(key, {"guideline": f["guideline"], "owner": f["owner"], "items": []})
        g["items"].append(f"{f['kind']} '{f['name']}': {f['detail']}")
    for g in groups.values():
        g["items"] = sorted(set(g["items"]))
        g["fingerprint"] = hashlib.sha256("\n".join(g["items"]).encode()).hexdigest()[:16]
    return groups


def plan(groups: dict[str, dict], state: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Returns (keys to raise, keys whose open issue should be resolved)."""
    raise_keys = [k for k, g in groups.items() if state.get(k, {}).get("fingerprint") != g["fingerprint"]]
    resolve_keys = [k for k in state if k not in groups or k in raise_keys]
    return sorted(raise_keys), sorted(resolve_keys)


def issue_body(group: dict, now_ms: int, max_items: int = 60) -> dict:
    gid = group["guideline"]
    items = group["items"]
    lines = "\n".join(f"- {i}" for i in items[:max_items])
    more = f"\n- ... and {len(items) - max_items} more" if len(items) > max_items else ""
    return {
        "request_data": {
            "issue": {
                "name": f"{ISSUE_PREFIX} - {gid} - {TITLES[gid]} ({group['owner']})",
                "description": f"Daily sweep found {len(items)} item(s) for owner {group['owner']} "
                f"that break guideline {gid}. See CTT-Guidelines.\n{lines}{more}",
                "observation_time": now_ms,
                "issue_domain": "Health",
                "category": "CTT Hygiene",
                "type": "Unclassified",
                "severity": "MEDIUM",
                "remediation": f"Fix the items listed, following guideline {gid} in CTT-Guidelines.",
                "tags": ["CTT", gid],
            }
        }
    }


# ---------- tenant I/O ----------


def _contents(res: list) -> Any:
    if is_error(res):
        raise DemistoException(get_error(res))
    response = res[0]["Contents"].get("response", {})
    return response.get("reply", response) if isinstance(response, dict) else response


def core_post(uri: str, body: dict) -> Any:
    return _contents(demisto.executeCommand("core-api-post", {"uri": uri, "body": json.dumps(body)}))


def core_get(uri: str) -> Any:
    return _contents(demisto.executeCommand("core-api-get", {"uri": uri}))


def get_list_json(name: str, default: Any) -> Any:
    res = demisto.executeCommand("getList", {"listName": name})
    if is_error(res) or not res[0].get("Contents") or "Item not found" in str(res[0].get("Contents")):
        return default
    try:
        return json.loads(res[0]["Contents"])
    except ValueError:
        return default


def save_list_json(name: str, data: Any) -> None:
    payload = json.dumps(data, indent=1)
    res = demisto.executeCommand("setList", {"listName": name, "listData": payload})
    if is_error(res):
        demisto.executeCommand("createList", {"listName": name, "listData": payload})


def collect_objects(errors: list[str]) -> list[dict]:
    objects: list[dict] = []

    def attempt(label: str, fn):
        try:
            objects.extend(fn())
        except Exception as e:
            errors.append(f"{label}: {e}")

    def playbooks():
        res = core_post("/playbook/search", {"query": "system:F", "size": 2000})
        return [
            {
                "kind": "Playbook",
                "name": p.get("name"),
                "creator": (p.get("OWNER") or {}).get("id", ""),
                "tags": p.get("tags") or [],
            }
            for p in res.get("playbooks") or []
            if not p.get("packID") and not p.get("system")
        ]

    def scripts():
        res = core_post("/automation/search", {"query": "system:F", "size": 2000})
        return [
            {"kind": "Script", "name": s.get("name"), "creator": s.get("user", "")}
            for s in res.get("scripts") or []
            if not s.get("packID") and not s.get("system")
        ]

    def jobs():
        res = core_post("/jobs/search", {"page": 0, "size": 500})
        return [{"kind": "Job", "name": j.get("name"), "creator": j.get("owner", "")} for j in res.get("data") or []]

    def instances():
        res = core_post("/settings/integration/search", {"size": 1000})
        return [
            {"kind": "Integration instance", "name": i.get("name"), "creator": ""}
            for i in res.get("instances") or []
            if not i.get("isBuiltin") and not i.get("packID")
        ]

    def correlation_rules():
        res = core_post("/public_api/v1/correlations/get", {"request_data": {"search_from": 0, "search_to": 1000}})
        rows = res.get("objects", []) if isinstance(res, dict) else []
        return [
            {
                "kind": "Correlation rule",
                "name": r.get("name"),
                "creator": r.get("created_by") if "@" in str(r.get("created_by")) else "",
            }
            for r in rows
        ]

    def lookups():
        res = core_post("/public_api/v1/xql/get_datasets", {"request_data": {}})
        return [
            {"kind": "Lookup dataset", "name": d.get("Dataset Name"), "creator": ""}
            for d in res or []
            if isinstance(d, dict) and str(d.get("Type", "")).upper() == "LOOKUP"
        ]

    for label, fn in [
        ("playbooks", playbooks),
        ("scripts", scripts),
        ("jobs", jobs),
        ("integration instances", instances),
        ("correlation rules", correlation_rules),
        ("lookups", lookups),
    ]:
        attempt(label, fn)
    return objects


def collect_open_security_cases(stale_days: int, now_ms: int) -> list[dict]:
    body = {
        "request_data": {
            "filters": [
                {"field": "status_progress", "operator": "nin", "value": ["Resolved"]},
                {"field": "case_domain", "operator": "in", "value": ["Security"]},
                {"field": "modification_time", "operator": "lte", "value": now_ms - stale_days * DAY_MS},
            ],
            "search_from": 0,
            "search_to": 500,
        }
    }
    return core_post("/public_api/v1/case/search", body).get("DATA") or []


def create_issue(group: dict, now_ms: int) -> str:
    reply = core_post("/public_api/v1/issue", issue_body(group, now_ms))
    return str((reply or {}).get("external_id") or "")


def resolve_issue(external_id: str, comment: str) -> None:
    if not external_id:
        return
    found = core_post(
        "/public_api/v1/issue/search",
        {"request_data": {"filters": [{"field": "external_id", "operator": "in", "value": [external_id]}]}},
    )
    for issue in (found or {}).get("DATA") or []:
        core_post(
            f"/public_api/v1/issue/{issue.get('id')}",
            {
                "request_data": {
                    "update_data": {
                        "status": "Resolved",
                        "status_resolution_reason": "Resolved - Other",
                        "status_resolution_comment": comment,
                    }
                }
            },
        )


def main():  # pragma: no cover
    try:
        args = demisto.args()
        dry_run = argToBoolean(args.get("dry_run", "false"))
        cfg = get_list_json(CONFIG_LIST, {})
        sweep_cfg = cfg.get("sweep", {})
        stale_days = int(args.get("stale_case_days") or sweep_cfg.get("stale_case_days", 7))
        max_new = int(sweep_cfg.get("max_new_issues_per_run", 50))
        registry_rows = get_list_json(cfg.get("registry", {}).get("output_list", "CTT - Registry"), [])
        if not registry_rows:
            raise DemistoException("The 'CTT - Registry' list is empty. Run the CTT - Registry Sync job first.")
        registry = registry_index(registry_rows)
        now_ms = int(time.time() * 1000)

        errors: list[str] = []
        findings: list[dict] = []
        for obj in collect_objects(errors):
            findings.extend(check_object(obj, registry))
        try:
            for case in collect_open_security_cases(stale_days, now_ms):
                f = check_case(case, now_ms, stale_days)
                if f:
                    findings.append(f)
        except Exception as e:
            errors.append(f"cases: {e}")

        groups = group_findings(findings)
        state = get_list_json(STATE_LIST, {})
        raise_keys, resolve_keys = plan(groups, state)
        raised, resolved = [], []
        if not dry_run:
            for key in resolve_keys:
                try:
                    resolve_issue(state[key].get("external_id", ""), "Superseded or fixed; found by the CTT daily sweep.")
                    resolved.append(key)
                except Exception as e:
                    errors.append(f"resolve {key}: {e}")
                state.pop(key, None)
            for key in raise_keys[:max_new]:
                try:
                    ext = create_issue(groups[key], now_ms)
                    state[key] = {
                        "fingerprint": groups[key]["fingerprint"],
                        "external_id": ext,
                        "count": len(groups[key]["items"]),
                    }
                    raised.append(key)
                except Exception as e:
                    errors.append(f"raise {key}: {e}")
            save_list_json(STATE_LIST, state)

        rows = [
            {"Guideline": g["guideline"], "Owner": g["owner"], "Items": len(g["items"]), "New issue": k in raise_keys}
            for k, g in sorted(groups.items())
        ]
        md = tableToMarkdown(
            f"CTT hygiene sweep{' (dry run)' if dry_run else ''}", rows, headers=["Guideline", "Owner", "Items", "New issue"]
        )
        md += f"\nRaised {len(raised)} issue(s), resolved {len(resolved)}."
        if errors:
            md += tableToMarkdown("Collection errors", [{"Error": e} for e in errors])
        return_results(
            CommandResults(
                readable_output=md,
                outputs_prefix="CTT.Sweep",
                outputs={"Findings": findings, "Raised": raised, "Resolved": resolved, "Errors": errors},
            )
        )
    except Exception as e:
        return_error(f"CTTHygieneSweep failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
