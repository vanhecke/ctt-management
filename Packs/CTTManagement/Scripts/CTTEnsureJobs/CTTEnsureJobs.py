import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
from typing import Any

JOBS_LIST = "CTT - Jobs"
COMPARED = ("playbookId", "humanCron", "timezone", "scheduled", "recurrent", "details", "tags")


def job_changes(wanted: dict, current: dict) -> list[str]:
    """Fields whose value on the tenant differs from the definition."""
    return [k for k in COMPARED if wanted.get(k) != current.get(k)]


def plan_jobs(wanted: list[dict], existing: list[dict]) -> list[tuple[str, dict, dict | None, list[str]]]:
    """Returns (action, definition, current job or None, changed fields) per definition."""
    by_name = {j.get("name"): j for j in existing}
    out = []
    for job in wanted:
        current = by_name.get(job["name"])
        if not current:
            out.append(("create", job, None, []))
            continue
        changed = job_changes(job, current)
        out.append(("update" if changed else "ok", job, current, changed))
    return out


def core_post(uri: str, body: dict) -> Any:
    res = demisto.executeCommand("core-api-post", {"uri": uri, "body": json.dumps(body)})
    if is_error(res):
        raise DemistoException(get_error(res))
    response = res[0]["Contents"].get("response", {})
    return response.get("reply", response) if isinstance(response, dict) else response


def main():  # pragma: no cover
    try:
        dry_run = argToBoolean(demisto.args().get("dry_run", "false"))
        res = demisto.executeCommand("getList", {"listName": JOBS_LIST})
        if is_error(res):
            raise DemistoException(f"Cannot read '{JOBS_LIST}': {get_error(res)}")
        wanted = json.loads(res[0]["Contents"] or "[]")
        existing = core_post("/jobs/search", {"page": 0, "size": 500}).get("data") or []
        rows = []
        for action, job, current, changed in plan_jobs(wanted, existing):
            if not dry_run and action != "ok":
                body = dict(job)
                if current:
                    body.update(id=current["id"], version=current.get("version"), startDate=current.get("startDate"))
                core_post("/jobs", body)
            rows.append({"Job": job["name"], "Action": action, "Changed": ", ".join(changed)})
        title = f"CTT jobs{' (dry run)' if dry_run else ''}"
        return_results(CommandResults(readable_output=tableToMarkdown(title, rows), outputs_prefix="CTT.Jobs", outputs=rows))
    except Exception as e:
        return_error(f"CTTEnsureJobs failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
