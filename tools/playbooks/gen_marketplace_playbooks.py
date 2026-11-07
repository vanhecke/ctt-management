"""Generate the CTT Marketplace Updates playbooks (Jev-reviewed Marketplace updates).

Imported from the TypeSafe Jev Marketplace Guard playbooks on cttasean (2026-11-07), renamed
to CTT, with two last steps: a run summary and a post to the CTT Slack channel (CTTSlackPost).
The job is defined in tools/jobs/gen_jobs.py.

Run from content/:  uv run --with pyyaml python3 tools/playbooks/gen_marketplace_playbooks.py
"""

import json
import uuid
from pathlib import Path

import yaml

PACK = Path(__file__).resolve().parent.parent.parent / "Packs" / "CTTManagement"
NS = uuid.UUID("5a0c7d2e-3f41-4b8a-9e6d-1c2b3a4f5e60")
SCRIPT = "CTTMarketplaceUpdates"
CTX = "TypeSafeJevMarketplace"  # context prefix kept from the original script
MAIN = "CTT - Marketplace Updates"
ANALYSIS = "CTT - Marketplace Release Analysis"


def simple(value: str) -> dict:
    return {"simple": value}


def task(pb: str, tid: str, kind: str, name: str, x: int, y: int, nxt: dict | None = None, **extra) -> dict:
    task_uuid = str(uuid.uuid5(NS, f"{pb}-{tid}"))
    body = {"id": task_uuid, "version": -1, "name": name, "description": extra.pop("description", ""), "type": kind}
    body.update({"iscommand": False, "brand": ""})
    body.update(extra.pop("task", {}))
    t = {"id": tid, "taskid": task_uuid, "type": kind, "task": body}
    if nxt:
        t["nexttasks"] = nxt
    t.update(extra)
    t.setdefault("separatecontext", False)
    t.setdefault("continueonerrortype", "")
    t.update(
        {
            "view": json.dumps({"position": {"x": x, "y": y}}),
            "note": False,
            "timertriggers": [],
            "ignoreworker": False,
            "skipunavailable": False,
            "quietmode": 0,
        }
    )
    return t


def step(pb: str, tid: str, name: str, description: str, action: str, args: dict, y: int, nxt: dict, **extra) -> dict:
    return task(
        pb,
        tid,
        "regular",
        name,
        50,
        y,
        nxt,
        description=description,
        task={"scriptName": SCRIPT},
        scriptarguments={"action": simple(action), **{k: simple(v) for k, v in args.items()}},
        **extra,
    )


def go(tid: str) -> dict:
    return {"#none#": [tid]}


def playbook(name: str, description: str, tasks: list[dict], height: int, inputs: list, outputs: list) -> dict:
    return {
        "id": name,
        "version": -1,
        "name": name,
        "description": description,
        "fromversion": "8.9.0",
        "marketplaces": ["marketplacev2", "platform"],
        "tags": ["CTT"],
        # Pack-installed playbooks must be adopted before a job can run them (see gen_jobs.py).
        "adopted": True,
        "starttaskid": "0",
        "tasks": {t["id"]: t for t in tasks},
        "view": json.dumps({"linkLabelsPosition": {}, "paper": {"dimensions": {"height": height, "width": 380, "x": 50, "y": 50}}}),
        "inputs": inputs,
        "outputs": outputs,
        "tests": ["No tests (auto formatted)"],
    }


def main_playbook() -> dict:
    pb, core = MAIN, "${inputs.CoreInstance}"
    tasks = [
        task(pb, "0", "start", "", 50, 50, go("12")),
        task(
            pb, "12", "condition", "Is TypeSafe Jev configured?", 50, 220,
            {"yes": ["1"], "#default#": ["13"]},
            description="Runs only on tenants with an enabled TypeSafe Jev instance; elsewhere the run closes without changes.",
            task={"scriptName": "IsIntegrationAvailable"},
            scriptarguments={"brandname": simple("TypeSafe Jev")},
        ),
        task(
            pb, "13", "regular", "Close: TypeSafe Jev is not configured", 500, 400,
            description="Closes the run without changes: this tenant has no enabled TypeSafe Jev instance.",
            task={"script": "Builtin|||closeInvestigation", "iscommand": True, "brand": "Builtin"},
            scriptarguments={"closeNotes": simple("Skipped: no enabled TypeSafe Jev instance on this tenant, so no Marketplace updates were reviewed.")},
        ),
        step(
            pb, "1", "Collect installed packs and enabled integrations",
            "Lists installed packs, their newer Marketplace releases and the enabled integration instances.",
            "collect", {"core_instance": core}, 400, go("2"),
        ),
        step(
            pb, "2", "Prepare release evidence for Jev",
            "Batches the newer releases with their notes and the observed integrations for Jev.",
            "prepare_ai", {"core_instance": core, "snapshot": f"${{{CTX}.Snapshot}}"}, 580, go("3"),
        ),
        task(
            pb, "3", "condition", "Are there newer releases to review?", 50, 760,
            {"#default#": ["5"], "yes": ["4"]},
            description="Continue to Jev analysis only when the collected Marketplace inventory contains newer releases requiring review.",
            conditions=[
                {
                    "label": "yes",
                    "condition": [[{"operator": "isTrue", "left": {"value": simple(f"{CTX}.ReviewPlan.Required"), "iscontext": True}}]],
                }
            ],
        ),
        task(
            pb, "4", "playbook", "Review pending releases with Jev", 280, 940, go("5"),
            description="Runs TypeSafe Jev for every evidence batch. Each returned question ID stays tied to its source release.",
            task={"playbookName": ANALYSIS},
            scriptarguments={"BatchJSON": simple(f"${{{CTX}.ReviewPlan.BatchJSON}}")},
            separatecontext=True,
            loop={"iscommand": False, "exitCondition": "", "wait": 1, "max": 100, "forEach": True},
        ),
        step(
            pb, "5", "Validate Jev decisions against supplied evidence",
            "Validates all Jev answers in one run: rejects conflicting answers and keeps missing or uncertain judgments as unresolved.",
            "apply_ai",
            {"analysis_response": f"${{{CTX}.AnalystBatch}}", "core_instance": core, "review_plan": f"${{{CTX}.ReviewPlan}}"},
            1120, go("6"),
        ),
        step(
            pb, "6", "Create validation issues for affected breaking changes",
            "One deduplicated issue per breaking change that affects an enabled integration.",
            "publish", {"assessment": f"${{{CTX}.Assessment}}", "core_instance": core, "dry_run": "${inputs.DryRun}"},
            1300, go("7"),
        ),
        step(
            pb, "7", "Install approved updates and verify versions",
            "Installs approved updates with their missing mandatory dependencies first (cyclic groups together) through the tenant Marketplace, then verifies each exact version. A failed dependency blocks its parents.",
            "install",
            {
                "assessment": f"${{{CTX}.Assessment}}",
                "core_instance": core,
                "dry_run": "${inputs.DryRun}",
                "snapshot": f"${{{CTX}.Snapshot}}",
            },
            1480, {"#none#": ["8"], "#error#": ["8"]},
            continueonerror=True, continueonerrortype="errorPath",
        ),
        step(
            pb, "8", "Create manual review cases for held or unresolved updates",
            "One deduplicated review issue and case per held, unresolved or failed update (pack + target version). Resolves stale review cases once the pack is installed or the target changes. Never installs or approves anything.",
            "review",
            {
                "assessment": f"${{{CTX}.Assessment}}",
                "core_instance": core,
                "dry_run": "${inputs.DryRun}",
                "installation": f"${{{CTX}.Installation}}",
                "snapshot": f"${{{CTX}.Snapshot}}",
            },
            1660, go("9"),
        ),
        step(
            pb, "9", "Summarize the run",
            "Builds a plain-text summary of this run: packs checked, installed, held and failed updates, and review cases.",
            "summary",
            {
                "snapshot": f"${{{CTX}.Snapshot}}",
                "installation": f"${{{CTX}.Installation}}",
                "review": f"${{{CTX}.Review}}",
                "routing": f"${{{CTX}.Routing}}",
            },
            1840, go("10"),
        ),
        task(
            pb, "10", "regular", "Post the summary to the CTT Slack channel", 50, 2020, go("11"),
            description="Posts the run summary with CTTSlackPost. A Slack failure does not stop the run.",
            task={"scriptName": "CTTSlackPost"},
            scriptarguments={"message": simple(f"${{{CTX}.Summary.text}}")},
            continueonerror=True,
        ),
        task(
            pb, "11", "regular", "Close the completed Marketplace run", 50, 2200,
            description="Closes only this run's investigation. Review cases stay open until resolved.",
            task={"script": "Builtin|||closeInvestigation", "iscommand": True, "brand": "Builtin"},
            scriptarguments={
                "closeNotes": simple(
                    f"Marketplace release review, guarded installation and manual-review case routing completed. See {CTX}.Assessment, "
                    "Routing, Installation, Review and Summary. Only this run's investigation is closed; review cases stay open."
                )
            },
        ),
    ]
    inputs = [
        {
            "key": "DryRun",
            "value": simple("false"),
            "required": False,
            "description": "true reviews and reports without installing packs or creating, updating or closing cases.",
            "playbookInputQuery": None,
        },
        {
            "key": "CoreInstance",
            "value": {},
            "required": False,
            "description": "Core REST API instance name. Empty uses the enabled instance.",
            "playbookInputQuery": None,
        },
    ]
    return playbook(
        MAIN,
        "Jev-reviewed Marketplace updates: collects newer pack releases, has TypeSafe Jev review each one against the enabled integrations, installs approved updates with their mandatory dependencies and verifies the versions. Held, unresolved or failed updates get one deduplicated review case each, breaking changes that affect an enabled integration get a validation issue, and a summary goes to the CTT Slack channel. Run by the job of the same name (Monday to Thursday, 05:00 Singapore time). Needs the Core REST API integration and a TypeSafe Jev instance; without Jev the run closes without changes.",
        tasks,
        2225,
        inputs,
        [],
    )


def analysis_playbook() -> dict:
    pb = ANALYSIS
    tasks = [
        task(pb, "0", "start", "", 50, 50, go("1")),
        step(
            pb, "1", "Prepare batch evidence",
            "Unpacks the release evidence batch and exposes its state and questions for Jev.",
            "unpack_ai", {"batch_json": "${inputs.BatchJSON}"}, 230, go("2"),
        ),
        task(
            pb, "2", "regular", "Review release batch with Jev", 50, 410, go("3"),
            description="Has the TypeSafe Jev integration (pinned model) evaluate each release and name the affected observed components. Source text is untrusted data; missing configuration or usage evidence stays unknown.",
            task={"script": "TypeSafe Jev|||jev-evaluate", "iscommand": True, "brand": "TypeSafe Jev"},
            scriptarguments={
                "extend-context": simple(f"{CTX}.AnalystResult="),
                "ignore-outputs": simple("true"),
                "model": simple("jev-1.13.0"),
                "questions": simple(f"${{{CTX}.Batch.QuestionsJSON}}"),
                "state": simple(f"${{{CTX}.Batch.StateJSON}}"),
            },
        ),
        step(
            pb, "3", "Return Jev batch results",
            "Returns the complete Jev response without dropping release or component judgments.",
            "wrap_ai", {"analysis_response": f"${{{CTX}.AnalystResult}}"}, 590, go("4"),
        ),
        task(pb, "4", "title", "Analysis batch complete", 50, 770),
    ]
    inputs = [
        {
            "key": "BatchJSON",
            "value": {},
            "required": True,
            "description": "One serialized review batch: items, StateJSON and QuestionsJSON.",
            "playbookInputQuery": None,
        }
    ]
    outputs = [{"contextPath": f"{CTX}.AnalystBatch", "description": "Wrapped Jev batch answers returned to the parent playbook.", "type": "unknown"}]
    return playbook(
        ANALYSIS,
        "Sub-playbook of CTT - Marketplace Updates: reviews one batch of Marketplace releases with TypeSafe Jev, using the release notes, installed versions and enabled integrations, and returns every Jev answer for validation by the parent playbook.",
        tasks,
        795,
        inputs,
        outputs,
    )


READMES = {
    MAIN: "Runs `CTTMarketplaceUpdates` (collect, prepare_ai, apply_ai, publish, install, review, summary), the "
    f"`{ANALYSIS}` sub-playbook for each batch of releases, then `CTTSlackPost` with the run summary.\n\n"
    "Needs the `TypeSafe Jev` integration (command `jev-evaluate`) and the `Core REST API` integration. Set the "
    "`DryRun` input to `true` to review and report without installing or changing cases.\n",
    ANALYSIS: "Runs `CTTMarketplaceUpdates` (unpack_ai, wrap_ai) around the `jev-evaluate` command of the "
    "`TypeSafe Jev` integration.\n",
}


def main() -> None:
    for pb in (main_playbook(), analysis_playbook()):
        stem = pb["name"].replace(" ", "-").replace("---", "-")
        path = PACK / "Playbooks" / f"playbook-{stem}.yml"
        path.write_text(yaml.dump(pb, sort_keys=False, width=10000, allow_unicode=True))
        (PACK / "Playbooks" / f"playbook-{stem}_README.md").write_text(f"{pb['description']}\n\n{READMES[pb['name']]}")
        print(f"wrote {path.name}")


if __name__ == "__main__":
    main()
