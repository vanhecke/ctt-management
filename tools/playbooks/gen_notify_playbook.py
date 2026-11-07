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
ASK_PLAYBOOK = "CTT - Hygiene - Ask Owner"
ASK = "3"  # the question task in ASK_PLAYBOOK; CTTHygieneAskLinks reads its links


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
    t["8"]["nexttasks"] = {"#default#": ["11"], "yes": ["5"]}
    t["5"] = base("5", "aiTask", "Write the Slack message with AI", "CTTHygieneMessagePrompt writes the DM text (only with notify.use_ai).", 1050, x=50,
                  task_extra={"aiTaskId": "CTTHygieneMessagePrompt"})
    t["5"]["scriptarguments"] = {k: arg(k) for k in ("first_name", "owner_tags", "issue_title", "issue_details", "guideline_id", "guideline_title", "guideline_text")}
    t["5"]["continueonerror"] = True
    t["5"]["nexttasks"] = {"#none#": ["11"]}
    # The question loop runs as a sub-playbook: a link back into task 11 would make 11 wait for that
    # link's task too (all incoming tasks must finish first), so the playbook stopped after task 8.
    t["11"] = base("11", "playbook", "Ask the owner until fixed", "Runs CTT - Hygiene - Ask Owner (DM with the Mark as Fixed / Mark as False Positive answers, then the fix check) again until the issue is resolved. Resolving the issue also stops this playbook.", 1220, x=250,
                   task_extra={"playbookName": ASK_PLAYBOOK})
    t["11"]["loop"] = {
        "iscommand": False,
        "exitCondition": "",
        "wait": 1,
        "max": 50,
        "builtincondition": [[{"operator": "isTrue", "left": {"value": {"simple": "CTT.FixCheck.resolved"}, "iscontext": True}}]],
    }
    t["11"]["nexttasks"] = {"#none#": ["7"]}
    t["7"] = base("7", "title", "Done", "", 1390, x=450)
    return {
        "id": NAME,
        "version": -1,
        "name": NAME,
        "description": "Runs on every CTT hygiene health issue: assigns it to the person responsible (from the issue's owner marker and the CTT registry), sends them a Slack DM with the fix and the answer buttons Mark as Fixed / Mark as False Positive, and waits for the answer. Mark as Fixed runs the fix check (resolve with a close note, or ask again with what is still wrong); Mark as False Positive resolves it as False Positive and tells the CTT channel. DMs follow notify in 'CTT - Config'.",
        "fromversion": "8.15.0",
        "marketplaces": ["marketplacev2", "platform"],
        "tags": ["CTT"],
        # Pack-installed playbooks must be adopted before a job, a trigger or the API can attach
        # them to an issue ("playbook is not adopted (69)"); this adopts them on install.
        "adopted": True,
        "starttaskid": "0",
        "tasks": t,
        "view": json.dumps({"linkLabelsPosition": {}, "paper": {"dimensions": {"height": 1405, "width": 780, "x": 50, "y": 50}}}),
        "inputs": [],
        "outputs": [],
        "tests": ["No tests (auto formatted)"],
    }


def ask_playbook() -> dict:
    """One round: clear old answer links, ask "Did you fix it?" by Generated link and, in parallel,
    DM the owner the links; then run the fix check on the answer."""
    def at(key, kind, name, desc, y, x=250, extra=None):
        task = base(key, kind, name, desc, y, x, extra)
        task["taskid"] = task["task"]["id"] = str(uuid.uuid5(NS, f"{ASK_PLAYBOOK}-{key}"))
        return task

    t = {}
    t["0"] = at("0", "start", "", "", 50)
    t["0"]["nexttasks"] = {"#none#": ["1"]}
    t["1"] = at("1", "regular", "Clear the previous answer links", "Asking again appends links; start each round without the old ones.", 180, extra={"scriptName": "DeleteContext"})
    t["1"]["scriptarguments"] = {"key": {"simple": "Ask"}}
    t["1"]["nexttasks"] = {"#none#": ["2"]}
    t["2"] = at("2", "title", "Ask and DM", "", 330)
    t["2"]["nexttasks"] = {"#none#": [ASK, "10"]}
    # The links reach the context a few seconds after the question starts; a script started later
    # gets them in its starting context (the only way to read them in a run started by an
    # automation rule, whose context the context API can't see).
    t["10"] = at("10", "regular", "Wait for the question's links", "Gives the question time to write its answer links to the context.", 400, x=450, extra={"scriptName": "Sleep"})
    t["10"]["scriptarguments"] = {"seconds": {"simple": "20"}}
    t["10"]["nexttasks"] = {"#none#": ["4"]}
    t[ASK] = at(ASK, "condition", "Did you fix it?", "Asked by Generated link: one link per answer, opened without a Cortex login, behind the Mark as Fixed and Mark as False Positive buttons of the DM. Waits until answered (no timeout); the daily digest reminds the owner.", 480, x=50)
    t[ASK]["message"] = {
        "to": {"simple": f"${{{CTX}.owner_email}}"},
        "subject": {"simple": f"CTT hygiene issue #${{{CTX}.issue_id}}"},
        "body": {"simple": f"CTT hygiene issue #${{{CTX}.issue_id}}: ${{{CTX}.issue_title}}. Did you fix it?"},
        "methods": ["pushLinkToContext"],
        "format": "",
        "bcc": None,
        "cc": None,
        "timings": {"retriescount": 0, "retriesinterval": 1440, "completeafterreplies": 1, "completeafterv2": True, "completeaftersla": False},
        "replyOptions": ["Fixed", "False positive"],
    }
    t[ASK]["nexttasks"] = {"Fixed": ["5"], "False positive": ["6"]}
    t["4"] = at("4", "regular", "Get the answer links", "Returns the newest link per answer from the context.", 530, x=450, extra={"scriptName": "CTTHygieneAskLinks"})
    t["4"]["scriptarguments"] = {"task_id": {"simple": ASK}}
    # Without links (Generated link unavailable) the DM still goes out, without answer buttons.
    t["4"]["continueonerror"] = True
    t["4"]["nexttasks"] = {"#none#": ["7"]}
    t["7"] = at("7", "regular", "Send the Slack DM", "Lays out the DM (FOUND / RULE / FIX, or the AI text) with the answer links, as Slack buttons when notify.buttons is on, and sends it through the CTT Slack Webhook. After a Mark as Fixed the check couldn't confirm, it starts with what is still wrong.", 650, x=450, extra={"scriptName": "CTTHygieneSendDM"})
    t["7"]["scriptarguments"] = {
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
        "fixed_url": {"simple": "${CTT.Ask.fixed_url}"},
        "not_violation_url": {"simple": "${CTT.Ask.not_violation_url}"},
        "buttons": arg("buttons"),
        "note": {"simple": "${CTT.FixCheck.note}"},
    }
    t["7"]["nexttasks"] = {"#none#": ["8"]}
    t["8"] = at("8", "regular", "Set the issue to In Progress", "The owner has been told; the issue now waits for their fix.", 820, x=450,
                extra={"script": "Cortex Core - Platform|||core-update-issue", "iscommand": True, "brand": "Cortex Core - Platform"})
    t["8"]["scriptarguments"] = {"id": arg("issue_id"), "status": {"simple": "In Progress"}}
    t["8"]["continueonerror"] = True
    t["8"]["nexttasks"] = {"#none#": ["9"]}
    t["5"] = at("5", "regular", "Check the owner's fix", "CTTHygieneFixCheck confirm=true: resolves the issue with a close note when the check verifies the fix or the guideline has no check; otherwise keeps it open and writes what is still wrong to CTT.FixCheck.note for the next round's DM.", 650, x=50,
                extra={"scriptName": "CTTHygieneFixCheck"})
    t["5"]["scriptarguments"] = {"issue_id": arg("issue_id"), "confirm": {"simple": "true"}}
    t["5"]["nexttasks"] = {"#none#": ["9"]}
    t["6"] = at("6", "regular", "Record: false positive", "CTTHygieneFixCheck false_positive=true: tells the CTT channel, then resolves as False Positive with a close note.", 650, x=-150,
                extra={"scriptName": "CTTHygieneFixCheck"})
    t["6"]["scriptarguments"] = {"issue_id": arg("issue_id"), "false_positive": {"simple": "true"}}
    t["6"]["nexttasks"] = {"#none#": ["9"]}
    t["9"] = at("9", "title", "Round done", "", 990)
    return {
        "id": ASK_PLAYBOOK,
        "version": -1,
        "name": ASK_PLAYBOOK,
        "description": "Sub-playbook of CTT - Hygiene - Notify Owner, run in a loop until the issue is resolved: asks the owner \"Did you fix it?\" by Generated link, DMs them the Mark as Fixed / Mark as False Positive answers, and runs CTTHygieneFixCheck on the answer.",
        "fromversion": "8.15.0",
        "marketplaces": ["marketplacev2", "platform"],
        "tags": ["CTT"],
        "adopted": True,
        "starttaskid": "0",
        "tasks": t,
        "view": json.dumps({"linkLabelsPosition": {}, "paper": {"dimensions": {"height": 1005, "width": 780, "x": -150, "y": 50}}}),
        "inputs": [],
        "outputs": [{"contextPath": "CTT.FixCheck", "description": "The fix check result of this round.", "type": "unknown"}],
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
        # Without this the tenant installs the trigger only as a suggested automation rule that
        # an admin has to accept; with it the rule is enabled on install.
        "is_auto_enabled": True,
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
    (PACK / "Playbooks" / "playbook-CTT-Hygiene-Ask-Owner.yml").write_text(yaml.dump(ask_playbook(), sort_keys=False, width=10000))
    (PACK / "Playbooks" / "playbook-CTT-Hygiene-Ask-Owner_README.md").write_text(
        "Sub-playbook of `CTT - Hygiene - Notify Owner`, looped until the issue is resolved.\n\n"
        "1. Clears the previous answer links (`Ask`).\n"
        "2. Asks **Did you fix it?** by Generated link; in parallel `CTTHygieneAskLinks` waits for the links, `CTTHygieneSendDM` sends the DM with them (Slack buttons with `notify.buttons`) and the issue is set to In Progress.\n"
        "3. **Fixed** runs `CTTHygieneFixCheck confirm=true`; **Mark as False Positive** runs `CTTHygieneFixCheck false_positive=true`.\n\n"
        "An unconfirmed fix leaves `CTT.FixCheck.resolved` false, so the parent loop runs another round whose DM starts with what is still wrong.\n"
    )
    (PACK / "Playbooks" / "playbook-CTT-Hygiene-Notify-Owner_README.md").write_text(
        "Runs on every CTT hygiene health issue (trigger `CTT - Hygiene - Notify Owner`).\n\n"
        "1. `CTTHygieneTriage` finds the owner from the issue's `[owner: ...]` marker, their name, role and Slack ID in the CTT registry, and the guideline.\n"
        "2. `core-update-issue` assigns the issue to the owner's email.\n"
        "3. With `notify.use_ai`, the `CTTHygieneMessagePrompt` AI task writes the DM text; otherwise the FOUND / RULE / FIX template from triage is used.\n"
        "4. The `CTT - Hygiene - Ask Owner` sub-playbook runs in a loop until the issue is resolved: **Did you fix it?** is asked by Generated link (no timeout), and `CTTHygieneSendDM` sends the DM with the answers as Slack buttons **Mark as Fixed**, **Mark as False Positive** and **View Issue** (`notify.buttons`), otherwise with the links in the text. The issue is set to In Progress.\n"
        "5. **Mark as Fixed** runs `CTTHygieneFixCheck confirm=true`: a verified fix (or a guideline without a check) is resolved with a close note; otherwise the question is asked again and the next DM says what is still wrong.\n"
        "6. **Mark as False Positive** runs `CTTHygieneFixCheck false_positive=true`: a post in the CTT channel, then Resolved - False Positive with a close note.\n\n"
        "The hourly `CTT - Hygiene - Fix Check` job also resolves issues it finds fixed; resolving the issue stops this playbook. "
        "Assigning and the AI step continue on error. DMs follow `notify.mode` (`off`, `admins_only`, `all`) and the daily limit in `CTT - Config`.\n"
    )
    (PACK / "Triggers").mkdir(exist_ok=True)
    (PACK / "Triggers" / "Trigger-CTT-Hygiene-Notify-Owner.json").write_text(json.dumps(trigger(), indent=4) + "\n")
    print("wrote playbook and trigger")


if __name__ == "__main__":
    main()
