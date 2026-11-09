import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
from typing import Any
from urllib.parse import quote

JOBS_LIST = "CTT - Jobs"
# "scheduled" is left out: a job switched off on the tenant (Jobs > Disable) stays off.
COMPARED = ("playbookId", "humanCron", "timezone", "recurrent", "details", "tags", "category", "endingType")


def job_changes(wanted: dict, current: dict) -> list[str]:
    """Fields whose value on the tenant differs from the definition. A job only runs when its
    parent is its own id (UUID for jobs made in the UI) and it has an owner."""
    changed = [k for k in COMPARED if wanted.get(k) != current.get(k)]
    if current.get("parent") != current.get("id"):
        changed.append("parent")
    if not current.get("owner"):
        changed.append("owner")
    return changed


def obsolete_jobs(wanted: list[dict], existing: list[dict]) -> list[dict]:
    """CTT jobs on the tenant that the list no longer defines (for example after a rename)."""
    names = {j["name"] for j in wanted}
    return [j for j in existing if str(j.get("name", "")).startswith("CTT - ") and j.get("name") not in names]


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


def job_body(job: dict, current: dict | None, owner: str) -> dict:
    """What CTTEnsureJobs sends: the definition, with the tenant's id, version, start date and on/off
    state for an existing job, parent = that id, and an owner (the job's own, else the given one)."""
    body = dict(job)
    if current:
        body.update(id=current["id"], version=current.get("version"), startDate=current.get("startDate"))
        body.update({k: current[k] for k in ("scheduled", "schedulingStatus") if k in current})
    body["parent"] = body["id"]
    body["owner"] = (current or {}).get("owner") or owner
    return body


def current_user() -> str:
    """The user running the script (its email), for the owner of new jobs."""
    res = demisto.executeCommand("getUsers", {"current": "true"})
    if is_error(res) or not res:
        return ""
    users = res[0].get("Contents") or []
    users = users if isinstance(users, list) else [users]
    for user in users:
        for key in ("email", "username", "id"):
            value = str((user or {}).get(key) or "")
            if "@" in value:
                return value.lower()
    return ""


def core_post(uri: str, body: dict) -> Any:
    res = demisto.executeCommand("core-api-post", {"uri": uri, "body": json.dumps(body)})
    if is_error(res):
        raise DemistoException(get_error(res))
    response = res[0]["Contents"].get("response", {})
    return response.get("reply", response) if isinstance(response, dict) else response


def main():  # pragma: no cover
    try:
        args = demisto.args()
        dry_run = argToBoolean(args.get("dry_run", "false"))
        remove_obsolete = argToBoolean(args.get("remove_obsolete", "false"))
        res = demisto.executeCommand("getList", {"listName": JOBS_LIST})
        if is_error(res):
            raise DemistoException(f"Cannot read '{JOBS_LIST}': {get_error(res)}")
        wanted = json.loads(res[0]["Contents"] or "[]")
        existing = core_post("/jobs/search", {"page": 0, "size": 500}).get("data") or []
        plan = plan_jobs(wanted, existing)
        owner = str(args.get("owner") or "").strip().lower()
        if not owner and any(not (current or {}).get("owner") for action, _, current, _ in plan if action != "ok"):
            owner = current_user()
        rows = []
        for action, job, current, changed in plan:
            body = job_body(job, current, owner)
            if not dry_run and action != "ok":
                if not body["owner"]:
                    raise DemistoException(f"Job {job['name']} needs an owner: run again with owner=<email of a CTT admin>.")
                core_post("/jobs", body)
            state = "" if body.get("scheduled", True) else " (disabled)"
            rows.append({"Job": job["name"], "Action": action + state, "Changed": ", ".join(changed), "Owner": body["owner"]})
        for job in obsolete_jobs(wanted, existing):
            removed = remove_obsolete and not dry_run
            if removed:
                res = demisto.executeCommand("core-api-delete", {"uri": f"/jobs/{quote(str(job['id']), safe='')}"})
                if is_error(res):
                    raise DemistoException(f"Cannot delete job {job['name']}: {get_error(res)}")
            rows.append({"Job": job["name"], "Action": "deleted" if removed else "obsolete", "Changed": "", "Owner": ""})
        title = f"CTT jobs{' (dry run)' if dry_run else ''}"
        return_results(CommandResults(readable_output=tableToMarkdown(title, rows), outputs_prefix="CTT.Jobs", outputs=rows))
    except Exception as e:
        return_error(f"CTTEnsureJobs failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
