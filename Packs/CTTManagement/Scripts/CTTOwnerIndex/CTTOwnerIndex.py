import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import time
from typing import Any

DATASET = "ctt_object_owners"
FIELDS = ["object_kind", "object_name", "creator", "last_editor", "last_change"]
KEYS = ["object_kind", "object_name"]
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
BATCH = 1000  # the add_data API takes about 1000 rows per call

# BEGIN GENERATED OWNER_QUERY (tools/correlation_rules/gen_correlation_rules.py; do not edit)
OWNER_QUERY = (
    "dataset = management_auditing\n"
    "| filter management_auditing_result = ENUM.MANAGEMENT_AUDIT_SUCCESS\n"
    '| filter email != null and email != "" and email not in ("Palo Alto Networks", "N/A", "Xpanse Develo'
    'pment", "Cortex Automation")\n'
    '| filter user_name = null or user_name !~= "^(Public API - [0-9]+|APIKeyUser_[0-9]+|XSIAM Automation'
    '|Cortex Automation)$"\n'
    '| alter actor_email = if(email contains "@", lowercase(email), null), actor_name = lowercase(user_na'
    "me)\n"
    '| alter object_kind = coalesce(arrayindex(regextract(subtype, "^[A-Za-z ]+ - (.+)$"), 0), replex(to_'
    'string(management_auditing_type), "^(MANAGEMENT_AUDIT_|management_auditing_type_)", ""))\n'
    '| alter action = if(subtype ~= "^(Add|Upload|Copy|Create|New|Save as new|Import)" or subtype ~= "^(C'
    'reate|Upload lookup|Addition)", "create", if(subtype ~= "(Delete|Remove)", "delete", if(subtype ~= "'
    '(Edit|Change|Update|Modif|Adopt|Detach|Enable|Disable|Rename|Scope Edit)", "modify", "other")))\n'
    "| alter object_name = coalesce(\n"
    '    arrayindex(regextract(description, "ClonedPlaybookName: (.+?), ID:"), 0),\n'
    '    arrayindex(regextract(description, "playbookName: (.+?), ID:"), 0),\n'
    '    arrayindex(regextract(description, "scriptName: (.+?), (?:removed from|ID):"), 0),\n'
    '    arrayindex(regextract(description, "aiTaskName: (.+?), "), 0),\n'
    '    arrayindex(regextract(description, "CredentialsName: (.+?), ID:"), 0),\n'
    '    arrayindex(regextract(description, "ModuleName: ([^,]+)"), 0),\n'
    '    arrayindex(regextract(description, "ModuleBrand: (.+?), ID:"), 0),\n'
    '    arrayindex(regextract(description, "Layout (?:created|edited|deleted) - Name: (.+?), ID:"), 0),\n'
    '    arrayindex(regextract(description, "CaseField (?:created|edited|deleted) - Name: (.+?), Type:"),'
    " 0),\n"
    '    arrayindex(regextract(description, "Name: (.+?), JobID:"), 0),\n'
    '    arrayindex(regextract(description, "JobID: [^,]+, Name: (.+?), ID:"), 0),\n'
    '    arrayindex(regextract(description, "^name: (.+?), ID:"), 0),\n'
    '    arrayindex(regextract(description, "^Name: (.+?), ID:"), 0),\n'
    "    arrayindex(regextract(description, \"dashboard '(.+?)'\"), 0),\n"
    '    arrayindex(regextract(description, "(?:BIOC|Correlations? rule|IOC|Analytics BIOC|Attack Surface'
    ' Rule) [a-z]+ - name: (.+?),? id: "), 0),\n'
    '    arrayindex(regextract(description, " profile (.+?) was (?:created|edited|deleted)"), 0),\n'
    '    arrayindex(regextract(description, "policy rule (.+?) (?:with target|updated|scope updated|was d'
    'eleted|was created|created|was)"), 0),\n'
    '    arrayindex(regextract(description, "^Rule (.+?) status changed"), 0),\n'
    '    arrayindex(regextract(description, "Security Control: [^,]+, (.+)$"), 0),\n'
    "    arrayindex(regextract(description, \"Connector Template '?(.+?)'? (?:created|deleted|modified)\"),"
    " 0),\n"
    "    arrayindex(regextract(description, \"Endpoint group '(.+?)'\"), 0),\n"
    '    arrayindex(regextract(description, "lookup dataset called (\\S+)"), 0),\n'
    '    arrayindex(regextract(description, "Dataset (\\S+) of type"), 0),\n'
    "    arrayindex(regextract(description, \"(?:query|macro) '(.+?)'\"), 0),\n"
    "    arrayindex(regextract(description, \"report template\\(?s?\\)? '(.+?)'\"), 0),\n"
    "    arrayindex(regextract(description, \"Cloud Security Rule '(.+?)'\"), 0),\n"
    "    arrayindex(regextract(description, \"installation package '(.+?)'\"), 0),\n"
    '    arrayindex(regextract(description, "script, name: (.+?), description"), 0),\n'
    '    arrayindex(regextract(description, "^Edit (.+?), script id"), 0),\n'
    '    if(description ~= "^Next-Generation Firewall Data Collection", null, arrayindex(regextract(descr'
    'iption, " Data Collection for (.+?) (?:created|edited|deleted)"), 0)),\n'
    '    if(object_kind in ("Agent", "Action", "KnowledgeSource", "JobCenter"), arrayindex(regextract(des'
    'cription, "^(.+?)(?:, ID: .*)?$"), 0), null)\n'
    "  )\n"
    '| alter obj_tag = lowercase(arrayindex(regextract(object_name, "^\\s*([A-Za-z0-9]{2,16})\\s*[-_]"), 0)'
    ")\n"
    '| alter object_kind = if(object_kind = "RULES", if(description ~= "^Correlations? rule", "Correlatio'
    'n rule", if(description ~= "^BIOC", "BIOC rule", if(description ~= "^IOC", "IOC rule", "Detection ru'
    'le"))), if(object_kind = "DISTRIBUTIONS", "Agent installer", if(object_kind = "POLICY_RULES", "Polic'
    'y rule", if(object_kind = "POLICY_PROFILES", "Policy profile", if(object_kind = "DASHBOARD", "Dashbo'
    'ard", if(object_kind = "LOOKUPS", "Lookup dataset", if(object_kind = "DATASETS", "Dataset", if(objec'
    't_kind = "CLOUDSEC_RULE", "Cloud security rule", if(object_kind in ("SAAS_COLLECTION", "COLLECTION")'
    ', "Data collector", object_kind)))))))))\n'
    '| join type = left (dataset = ctt_registry | filter owner_email != "" | alter is_adm = if(role = "ad'
    'min", 1, 0) | comp max(is_adm) as reg_actor_admin by owner_email | alter reg_actor_email = owner_ema'
    "il | fields reg_actor_email, reg_actor_admin) as ra ra.reg_actor_email = actor_email\n"
    '| join type = left (dataset = ctt_registry | filter owner_email != "" | alter is_adm = if(role = "ad'
    'min", 1, 0), reg_name_key = lowercase(owner_name) | comp max(is_adm) as reg_name_admin, max(owner_em'
    "ail) as reg_name_email by reg_name_key | fields reg_name_key, reg_name_admin, reg_name_email) as rn "
    "rn.reg_name_key = actor_name\n"
    "| alter actor = coalesce(reg_actor_email, reg_name_email, actor_email, actor_name), actor_is_admin ="
    " coalesce(reg_actor_admin, reg_name_admin, 0), actor_registered = if(coalesce(reg_actor_email, reg_n"
    'ame_email) != null, "yes", "no")\n'
    '| filter object_kind not in ("AITask", "CaseField", "IssueField", "Credentials", "KnowledgeSource", '
    '"Investigation", "Indicator", "Entry", "War Room", "Whitelist", "Content", "Execute")\n'
    '| filter object_name != null and object_name != "" and action in ("create", "modify")\n'
    '| alter is_create = if(action = "create", 1, 0)\n'
    "| comp earliest(actor) as first_actor, latest(actor) as last_editor, max(is_create) as has_create, m"
    "ax(_time) as last_ts by object_kind, object_name\n"
    '| alter creator = if(has_create = 1, first_actor, ""), last_change = format_timestamp("%Y-%m-%dT%H:%'
    'M:%SZ", last_ts)\n'
    "| fields object_kind, object_name, creator, last_editor, last_change"
)
# END GENERATED OWNER_QUERY


# ---------- pure helpers (unit tested) ----------


def row_key(row: dict) -> tuple[str, str]:
    return (str(row.get("object_kind") or ""), str(row.get("object_name") or ""))


def merge(existing: list[dict], fresh: list[dict]) -> list[dict]:
    """Rows to upsert. A fresh row keeps the creator already known (the incremental window rarely
    holds an object's create event), and takes the newest editor and change time. Rows that
    did not change are left out."""
    known = {row_key(r): r for r in existing}
    out = []
    for f in fresh:
        old = known.get(row_key(f), {})
        row = {
            "object_kind": str(f.get("object_kind") or ""),
            "object_name": str(f.get("object_name") or ""),
            "creator": str(old.get("creator") or f.get("creator") or ""),
            "last_editor": str(f.get("last_editor") or old.get("last_editor") or ""),
            "last_change": max(str(f.get("last_change") or ""), str(old.get("last_change") or "")),
        }
        if not row["object_name"]:
            continue
        if any(str(old.get(k) or "") != row[k] for k in FIELDS):
            out.append(row)
    return out


def window_ms(backfill: bool, has_rows: bool, backfill_days: int, hours: int) -> int:
    return backfill_days * DAY_MS if backfill or not has_rows else hours * HOUR_MS


# ---------- tenant I/O ----------


def core_post(uri: str, body: dict) -> Any:
    res = demisto.executeCommand("core-api-post", {"uri": uri, "body": json.dumps(body)})
    if is_error(res):
        raise DemistoException(f"core-api-post {uri} failed: {get_error(res)}")
    response = res[0]["Contents"].get("response", {})
    return response.get("reply", response) if isinstance(response, dict) else response


def ensure_lookup() -> bool:
    datasets = core_post("/public_api/v1/xql/get_datasets", {"request_data": {}})
    names = {d.get("Dataset Name") or d.get("dataset_name") for d in (datasets or []) if isinstance(d, dict)}
    if DATASET in names:
        return False
    core_post(
        "/public_api/v1/xql/add_dataset",
        {"request_data": {"dataset_name": DATASET, "dataset_type": "lookup", "dataset_schema": dict.fromkeys(FIELDS, "text")}},
    )
    return True


def read_lookup() -> list[dict]:
    res = core_post("/public_api/v1/xql/lookups/get_data", {"request_data": {"dataset_name": DATASET, "limit": 10000}})
    rows = res.get("data", []) if isinstance(res, dict) else (res or [])
    return [r for r in rows if isinstance(r, dict)]


def run_xql(query: str, relative_ms: int, timeout: int = 600) -> list[dict]:
    qid = core_post(
        "/public_api/v1/xql/start_xql_query",
        {"request_data": {"query": query, "timeframe": {"relativeTime": relative_ms}}},
    )
    deadline = time.time() + timeout
    while True:
        res = core_post(
            "/public_api/v1/xql/get_query_results",
            {"request_data": {"query_id": qid, "pending_flag": True, "limit": 1000, "format": "json"}},
        )
        status = res.get("status")
        if status == "SUCCESS":
            results = res.get("results") or {}
            if results.get("stream_id"):
                stream = core_post(
                    "/public_api/v1/xql/get_query_results_stream",
                    {"request_data": {"stream_id": results["stream_id"], "is_gzip_compressed": False}},
                )
                text = stream if isinstance(stream, str) else json.dumps(stream)
                return [json.loads(line) for line in text.splitlines() if line.strip().startswith("{")]
            return results.get("data") or []
        if status not in ("PENDING", None) or time.time() > deadline:
            raise DemistoException(f"XQL query {status or 'timed out'}: {res}")
        time.sleep(5)


def main():  # pragma: no cover
    try:
        args = demisto.args()
        backfill = argToBoolean(args.get("backfill") or False)
        hours = int(args.get("hours") or 3)
        backfill_days = int(args.get("backfill_days") or 365)
        created = ensure_lookup()
        existing = [] if created else read_lookup()
        window = window_ms(backfill, bool(existing), backfill_days, hours)
        fresh = run_xql(OWNER_QUERY, window)
        rows = merge(existing, fresh)
        for start in range(0, len(rows), BATCH):
            core_post(
                "/public_api/v1/xql/lookups/add_data",
                {"request_data": {"dataset_name": DATASET, "key_fields": KEYS, "data": rows[start : start + BATCH]}},
            )
        summary = {
            "WindowHours": window // HOUR_MS,
            "ObjectsSeen": len(fresh),
            "RowsWritten": len(rows),
            "RowsBefore": len(existing),
            "LookupCreated": created,
        }
        return_results(
            CommandResults(
                readable_output=tableToMarkdown("CTT owner index", summary)
                + (tableToMarkdown("Rows written (first 20)", rows[:20], headers=FIELDS) if rows else ""),
                outputs_prefix="CTT.OwnerIndex",
                outputs=summary,
            )
        )
    except Exception as e:
        return_error(f"CTTOwnerIndex failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
