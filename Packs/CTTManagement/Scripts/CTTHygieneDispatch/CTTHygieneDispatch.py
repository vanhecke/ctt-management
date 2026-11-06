import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import time
from urllib.parse import quote

PLAYBOOK = "CTT - Hygiene - Notify Owner"
STATE_LIST = "CTT - Dispatch State"
PREFIX = "CTT - Hygiene - "
PAGE = 100
KEEP = 1000


def pick(issues: list[dict], done: set[str], limit: int) -> list[str]:
    """New CTT hygiene issues that nobody owns yet and were not dispatched before."""
    out = []
    for issue in issues:
        iid = str(issue.get("id", ""))
        if not iid or iid in done or issue.get("assigned_to"):
            continue
        if not str(issue.get("name", "")).startswith(PREFIX):
            continue
        out.append(iid)
    return out[:limit]


def remember(done: list[str], new: list[str]) -> list[str]:
    merged = [d for d in done if d not in set(new)] + new
    return merged[-KEEP:]


def core(command: str, args: dict):
    res = demisto.executeCommand(command, args)
    if is_error(res):
        raise DemistoException(get_error(res))
    response = res[0]["Contents"].get("response", {})
    return response.get("reply", response) if isinstance(response, dict) else response


def search_new_health_issues(hours: int) -> list[dict]:
    since = int(time.time() * 1000) - hours * 3_600_000
    filters = [
        {"field": "issue_domain", "operator": "in", "value": ["Health"]},
        {"field": "status.progress", "operator": "in", "value": ["New"]},
        {"field": "_insert_time", "operator": "gte", "value": since},
    ]
    issues: list[dict] = []
    for start in range(0, 1000, PAGE):
        body = {"request_data": {"filters": filters, "search_from": start, "search_to": start + PAGE}}
        page = core("core-api-post", {"uri": "/public_api/v1/issue/search", "body": json.dumps(body)}).get("DATA") or []
        issues.extend(page)
        if len(page) < PAGE:
            break
    return issues


def main():  # pragma: no cover
    try:
        args = demisto.args()
        hours = int(args.get("lookback_hours") or 48)
        limit = int(args.get("max_per_run") or 20)
        res = demisto.executeCommand("getList", {"listName": STATE_LIST})
        try:
            done = json.loads(res[0]["Contents"]).get("done", []) if not is_error(res) else []
        except (ValueError, KeyError, TypeError, AttributeError):
            done = []
        rows, handled = [], []
        for iid in pick(search_new_health_issues(hours), set(done), limit):
            # A new issue has no investigation (War Room) until something opens it, and a playbook
            # cannot be attached before that: "couldn't find investigation with id ...".
            core("core-api-post", {"uri": f"/investigation/{iid}", "body": json.dumps({"pageSize": 1})})
            current = core("core-api-get", {"uri": f"/inv-playbook/{iid}"}) or {}
            if isinstance(current, dict) and current.get("playbookId"):
                rows.append({"Issue": iid, "Action": f"skipped, already runs {current.get('playbookId')}"})
            else:
                core("core-api-post", {"uri": f"/inv-playbook/new/{quote(PLAYBOOK, safe='')}/{iid}", "body": "{}"})
                rows.append({"Issue": iid, "Action": f"started {PLAYBOOK}"})
            handled.append(iid)
        if handled:
            payload = json.dumps({"done": remember(done, handled)})
            if is_error(demisto.executeCommand("setList", {"listName": STATE_LIST, "listData": payload})):
                demisto.executeCommand("createList", {"listName": STATE_LIST, "listData": payload})
        md = tableToMarkdown("CTT hygiene dispatch", rows) if rows else "No new CTT hygiene issues to dispatch."
        return_results(CommandResults(readable_output=md, outputs_prefix="CTT.Dispatch", outputs=rows))
    except Exception as e:
        return_error(f"CTTHygieneDispatch failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
