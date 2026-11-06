"""Generate the CTTManagement job playbooks and jobs (one script per playbook).

Run from content/:  uv run --with pyyaml python3 tools/jobs/gen_jobs.py
"""

import json
import re
import uuid
from pathlib import Path

import yaml

PACK = Path(__file__).resolve().parent.parent.parent / "Packs" / "CTTManagement"
NS = uuid.UUID("0b8f5c3e-6a1d-4f2e-9b7c-5d4e3f2a1b0c")
ALL_DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]

JOBS = [
    {
        "name": "CTT - Registry Sync",
        "script": "CTTRegistrySync",
        "description": "Syncs the CTT registry (tags, lab octets, Slack IDs, admins) from the Google Sheet into the ctt_registry lookup dataset and the 'CTT - Registry' list. Run by the job of the same name every hour.",
        "task": "Sync the CTT registry",
        "inputs": {"source": ("", "auto, sheet or list. Empty uses registry.source in 'CTT - Config'.")},
        "cron": {"timePeriodType": "hours", "timePeriod": 1},
    },
    {
        "name": "CTT - Hygiene - Daily Sweep",
        "script": "CTTHygieneSweep",
        "description": "Daily CTT hygiene sweep: checks custom objects and open Security cases against the CTT guidelines and raises one health issue per guideline and owner. Run by the job of the same name every day at 08:30 Singapore time.",
        "task": "Run the CTT hygiene sweep",
        "inputs": {
            "dry_run": ("false", "true reports findings without raising or resolving issues."),
            "stale_case_days": ("", "Days without change before an open Security case is stale. Empty uses 'CTT - Config'."),
        },
        "cron": {"days": ALL_DAYS, "atTimeHour": "08", "atTimeMinute": "30", "timePeriodType": "weeks", "timePeriod": 1},
    },
    {
        "name": "CTT - Hygiene - Notify Dispatcher",
        "script": "CTTHygieneDispatch",
        "description": "Starts the CTT - Hygiene - Notify Owner playbook on new, unassigned CTT hygiene issues. Run by the job of the same name every 15 minutes, because pack uploads to XSIAM 8.15 do not install automation rules.",
        "task": "Dispatch new CTT hygiene issues",
        "inputs": {
            "lookback_hours": ("48", "How far back to look for new hygiene issues."),
            "max_per_run": ("20", "The most issues to dispatch in one run."),
        },
        "cron": {"timePeriodType": "minutes", "timePeriod": 15},
    },
    {
        "name": "CTT - Tenant Status",
        "script": "CTTTenantStatus",
        "description": "Publishes tenant statistics and hygiene to the CTT Slack channel: replaces the Tenant Status canvas and sets the channel topic. Run by the job of the same name every day at 09:00 Singapore time.",
        "task": "Publish the tenant status to Slack",
        "inputs": {
            "period_days": ("7", "Days of activity to report."),
            "send": ("true", "false only shows the canvas and topic in the War Room."),
        },
        "cron": {"days": ALL_DAYS, "atTimeHour": "09", "atTimeMinute": "00", "timePeriodType": "weeks", "timePeriod": 1},
    },
]


def task(tid: str, kind: str, name: str, nxt: str | None, y: int, extra: dict | None = None) -> dict:
    task_uuid = str(uuid.uuid5(NS, f"{name}-{tid}"))
    t = {
        "id": tid,
        "taskid": task_uuid,
        "type": kind,
        "task": {"id": task_uuid, "version": -1, "name": name, "description": "", "type": kind, "iscommand": False, "brand": ""},
        "separatecontext": False,
        "continueonerrortype": "",
        "view": json.dumps({"position": {"x": 50, "y": y}}),
        "note": False,
        "timertriggers": [],
        "ignoreworker": False,
        "skipunavailable": False,
        "quietmode": 0,
    }
    if nxt:
        t["nexttasks"] = {"#none#": [nxt]}
    if extra:
        t["task"].update(extra.get("task", {}))
        t.update({k: v for k, v in extra.items() if k != "task"})
    return t


def playbook(job: dict) -> dict:
    script_task = task(
        "1",
        "regular",
        job["task"],
        "2",
        230,
        {
            "task": {"scriptName": job["script"], "description": f"Runs {job['script']}."},
            "scriptarguments": {k: {"simple": f"${{inputs.{k}}}"} for k in job["inputs"]},
        },
    )
    return {
        "id": job["name"],
        "version": -1,
        "name": job["name"],
        "description": job["description"],
        "fromversion": "8.9.0",
        "marketplaces": ["marketplacev2", "platform"],
        "tags": ["CTT"],
        # Pack-installed playbooks must be adopted before a job, a trigger or the API can attach
        # them to an issue ("playbook is not adopted (69)"); this adopts them on install.
        "adopted": True,
        "starttaskid": "0",
        "tasks": {
            "0": task("0", "start", "", "1", 50),
            "1": script_task,
            "2": task("2", "title", "Done", None, 410),
        },
        "view": json.dumps({"linkLabelsPosition": {}, "paper": {"dimensions": {"height": 425, "width": 380, "x": 50, "y": 50}}}),
        "inputs": [
            {"key": k, "value": {"simple": v}, "required": False, "description": d, "playbookInputQuery": None}
            for k, (v, d) in job["inputs"].items()
        ],
        "outputs": [],
        "tests": ["No tests (auto formatted)"],
    }


def job_json(job: dict) -> dict:
    return {
        "id": job["name"],
        "name": job["name"],
        "details": job["description"],
        "playbookId": job["name"],
        "scheduled": True,
        "recurrent": True,
        "cronView": False,
        "humanCron": job["cron"],
        # The scheduler refuses a job without a start date (error 151), and a pack install then
        # drops the job silently.
        "startDate": "2026-11-06T00:00:00Z",
        # Likewise required: the job's incident type (error 100008 without it).
        "type": "##default##",
        "timezone": "Asia/Singapore",
        "timezoneOffset": -480,
        "shouldTriggerNew": True,
        "closePrevRun": True,
        "tags": ["CTT"],
        "isFeed": False,
        "selectedFeeds": [],
        "isAllFeeds": False,
        "fromVersion": "8.9.0",
        "supportedModules": ["xsiam", "agentix"],
    }


def jobs_list(jobs: list[dict]) -> dict:
    """The same job definitions as a list item: pack uploads to XSIAM 8.15 skip Jobs/, so
    CTTEnsureJobs creates the jobs from this list instead."""
    return {
        "id": "CTT - Jobs",
        "name": "CTT - Jobs",
        "type": "json",
        "description": "Job definitions for CTTEnsureJobs, which creates or updates the CTT jobs. Generated from tools/jobs/gen_jobs.py in git.",
        "data": json.dumps(jobs, indent=2),
        "version": -1,
        "fromVersion": "8.9.0",
        "itemVersion": "",
        "locked": False,
        "nameLocked": False,
        "packID": "CTTManagement",
        "system": False,
        "allRead": True,
        "allReadWrite": False,
        "marketplaces": ["marketplacev2", "platform"],
    }


def main() -> None:
    (PACK / "Playbooks").mkdir(exist_ok=True)
    (PACK / "Jobs").mkdir(exist_ok=True)
    (PACK / "Lists" / "list-CTT_-_Jobs.json").write_text(json.dumps(jobs_list([job_json(j) for j in JOBS]), indent=4) + "\n")
    for job in JOBS:
        stem = re.sub(r"[^A-Za-z0-9]+", "-", job["name"])
        pb = PACK / "Playbooks" / f"playbook-{stem}.yml"
        pb.write_text(yaml.dump(playbook(job), sort_keys=False, width=10000))
        (PACK / "Playbooks" / f"playbook-{stem}_README.md").write_text(f"{job['description']}\n\nRuns the `{job['script']}` script.\n")
        jb = PACK / "Jobs" / f"job-{stem}.json"
        jb.write_text(json.dumps(job_json(job), indent=4) + "\n")
        print(f"wrote {pb.name}, {jb.name}")


if __name__ == "__main__":
    main()
