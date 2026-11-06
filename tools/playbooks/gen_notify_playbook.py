"""Generate the 'CTT - Hygiene - Notify Owner' playbook and its trigger.

Run from content/:  uv run --with pyyaml python3 tools/playbooks/gen_notify_playbook.py
"""

import json
import uuid
from pathlib import Path

import yaml

PACK = Path(__file__).resolve().parent.parent.parent / "Packs" / "CTTManagement"
NAME = "CTT - Hygiene - Notify Owner"
NS = uuid.UUID("7a1e3c5d-9b2f-4e6a-8c0d-1f2e3d4c5b6a")
CTX = "CTT.Triage"


def tid(key: str) -> str:
    return str(uuid.uuid5(NS, f"{NAME}-{key}"))


def base(key: str, kind: str, name: str, desc: str, y: int, x: int = 450, task_extra: dict | None = None) -> dict:
    task = {"id": tid(key), "version": -1, "name": name, "description": desc, "type": kind}
    if kind != "aiTask":
        task.update(iscommand=False, brand="")
    task.update(task_extra or {})
    return {
        "id": key,
        "taskid": tid(key),
        "type": kind,
        "task": task,
        "separatecontext": False,
        "continueonerrortype": "",
        "view": json.dumps({"position": {"x": x, "y": y}}),
        "note": False,
        "timertriggers": [],
        "ignoreworker": False,
        "skipunavailable": False,
        "quietmode": 0,
    }


def arg(path: str) -> dict:
    return {"simple": f"${{{CTX}.{path}}}"}


def is_true(path: str) -> list:
    return [[{"operator": "isEqualString", "left": {"value": {"simple": f"{CTX}.{path}"}, "iscontext": True}, "right": {"value": {"simple": "true"}}}]]


def playbook() -> dict:
    t = {}
    t["0"] = base("0", "start", "", "", 50)
    t["0"]["nexttasks"] = {"#none#": ["9"]}
    # A re-run on the same issue appended a second triage result to the context, so the send
    # task looped over two Slack IDs and sent the DM twice. Start from a clean context.
    t["9"] = base("9", "regular", "Clear context from an earlier run", "Deletes the issue context so a re-run sends one DM.", 130,
                  task_extra={"scriptName": "DeleteContext"})
    t["9"]["scriptarguments"] = {"all": {"simple": "yes"}}
    t["9"]["nexttasks"] = {"#none#": ["1"]}
    t["1"] = base("1", "regular", "Triage the hygiene issue", "Finds the owner, their Slack ID and the guideline, and decides whether to assign and notify.", 260,
                  task_extra={"scriptName": "CTTHygieneTriage"})
    t["1"]["nexttasks"] = {"#none#": ["2"]}
    t["2"] = base("2", "condition", "Can the issue be assigned to a person?", "", 370)
    t["2"]["conditions"] = [{"label": "yes", "condition": is_true("assign")}]
    t["2"]["nexttasks"] = {"#default#": ["7"], "yes": ["3"]}
    t["3"] = base("3", "regular", "Assign the issue to its owner", "Sets the issue assignee to the owner's email.", 540, x=250,
                  task_extra={"script": "Cortex Core - Platform|||core-update-issue", "iscommand": True, "brand": "Cortex Core - Platform"})
    t["3"]["scriptarguments"] = {"id": arg("issue_id"), "assigned_user_mail": arg("owner_email")}
    t["3"]["continueonerror"] = True
    t["3"]["nexttasks"] = {"#none#": ["4"]}
    t["4"] = base("4", "condition", "Should the owner get a Slack DM?", "", 710, x=250)
    t["4"]["conditions"] = [{"label": "yes", "condition": is_true("notify")}]
    t["4"]["nexttasks"] = {"#default#": ["7"], "yes": ["8"]}
    t["8"] = base("8", "condition", "Write the message with AI?", "notify.use_ai in CTT - Config; otherwise the FOUND / RULE / FIX template is used.", 880, x=250)
    t["8"]["conditions"] = [{"label": "yes", "condition": is_true("use_ai")}]
    t["8"]["nexttasks"] = {"#default#": ["6"], "yes": ["5"]}
    t["5"] = base("5", "aiTask", "Write the Slack message with AI", "CTTHygieneMessagePrompt writes the DM text (only with notify.use_ai).", 1050, x=50,
                  task_extra={"aiTaskId": "CTTHygieneMessagePrompt"})
    t["5"]["scriptarguments"] = {k: arg(k) for k in ("first_name", "owner_tags", "issue_title", "issue_details", "guideline_id", "guideline_title", "guideline_text")}
    t["5"]["continueonerror"] = True
    t["5"]["nexttasks"] = {"#none#": ["6"]}
    t["6"] = base("6", "regular", "Send the Slack DM", "Lays out the DM (FOUND / RULE / FIX, or the AI text) and sends it through the CTT Slack Webhook (msg_person).", 1220, x=250,
                  task_extra={"scriptName": "CTTHygieneSendDM"})
    t["6"]["scriptarguments"] = {
        "slack_user_id": arg("slack_id"),
        "owner_email": arg("owner_email"),
        "first_name": arg("first_name"),
        "found": arg("found"),
        "fix": arg("fix"),
        "guideline_title": arg("guideline_title"),
        "message": {"simple": "${CTT.HygieneMessage}"},
        "issue_url": arg("issue_url"),
        "issue_id": arg("issue_id"),
        "guideline_id": arg("guideline_id"),
    }
    t["6"]["nexttasks"] = {"#none#": ["10"]}
    t["10"] = base("10", "regular", "Set the issue to In Progress", "The owner has been told; the issue now waits for their fix.", 1390, x=250,
                   task_extra={"script": "Cortex Core - Platform|||core-update-issue", "iscommand": True, "brand": "Cortex Core - Platform"})
    t["10"]["scriptarguments"] = {"id": arg("issue_id"), "status": {"simple": "In Progress"}}
    t["10"]["continueonerror"] = True
    t["10"]["nexttasks"] = {"#none#": ["7"]}
    t["7"] = base("7", "title", "Done", "", 1560)
    return {
        "id": NAME,
        "version": -1,
        "name": NAME,
        "description": "Runs on every CTT hygiene health issue: assigns it to the person responsible (from the issue's owner marker and the CTT registry) and sends them a short AI-written Slack DM with the fix and the issue link. DMs follow notify.mode in 'CTT - Config'.",
        "fromversion": "8.15.0",
        "marketplaces": ["marketplacev2", "platform"],
        "tags": ["CTT"],
        # Pack-installed playbooks must be adopted before a job, a trigger or the API can attach
        # them to an issue ("playbook is not adopted (69)"); this adopts them on install.
        "adopted": True,
        "starttaskid": "0",
        "tasks": t,
        "view": json.dumps({"linkLabelsPosition": {}, "paper": {"dimensions": {"height": 1575, "width": 780, "x": 50, "y": 50}}}),
        "inputs": [],
        "outputs": [],
        "tests": ["No tests (auto formatted)"],
    }


def trigger() -> dict:
    return {
        "trigger_id": uuid.uuid5(NS, "trigger").hex,
        "playbook_id": NAME,
        "suggestion_reason": "Assign CTT hygiene issues to their owner and notify them on Slack",
        "description": "Runs the CTT - Hygiene - Notify Owner playbook on every CTT hygiene health issue.",
        "trigger_name": NAME,
        "fromVersion": "8.15.0",
        "alerts_filter": {
            "filter": {
                "AND": [
                    {"SEARCH_FIELD": "alert_name", "SEARCH_TYPE": "CONTAINS", "SEARCH_VALUE": "CTT - Hygiene - "},
                    {"SEARCH_FIELD": "alert_domain", "SEARCH_TYPE": "EQ", "SEARCH_VALUE": "DOMAIN_HEALTH"},
                ]
            }
        },
    }


def main() -> None:
    (PACK / "Playbooks" / "playbook-CTT-Hygiene-Notify-Owner.yml").write_text(yaml.dump(playbook(), sort_keys=False, width=10000))
    (PACK / "Playbooks" / "playbook-CTT-Hygiene-Notify-Owner_README.md").write_text(
        "Runs on every CTT hygiene health issue (trigger `CTT - Hygiene - Notify Owner`).\n\n"
        "1. `CTTHygieneTriage` finds the owner from the issue's `[owner: ...]` marker, their name, role and Slack ID in the CTT registry, and the guideline.\n"
        "2. `core-update-issue` assigns the issue to the owner's email.\n"
        "3. With `notify.use_ai`, the `CTTHygieneMessagePrompt` AI task writes the DM text; otherwise the FOUND / RULE / FIX template from triage is used.\n"
        "4. `CTTHygieneSendDM` lays it out for the workflow's code block and sends it through the CTT Slack Webhook integration.\n"
        "5. The issue is set to In Progress once the owner has been told.\n\n"
        "Assigning and the AI step continue on error. DMs follow `notify.mode` (`off`, `admins_only`, `all`) and the daily limit in `CTT - Config`.\n"
    )
    (PACK / "Triggers").mkdir(exist_ok=True)
    (PACK / "Triggers" / "Trigger-CTT-Hygiene-Notify-Owner.json").write_text(json.dumps(trigger(), indent=4) + "\n")
    print("wrote playbook and trigger")


if __name__ == "__main__":
    main()
