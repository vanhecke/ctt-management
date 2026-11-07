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
ROUND1 = {"title": "20", "ask": "21", "wait": "22", "links": "23", "dm": "24", "progress": "25", "check": "26", "resolved": "27", "fp": "28", "close": "29", "fpclose": "40", "gate": "43"}
ROUND2 = {"clear": "30", "title": "31", "ask": "32", "wait": "33", "links": "34", "dm": "35", "check": "36", "resolved": "37", "fp": "38", "last": "39", "close": "41", "fpclose": "42", "gate": "44", "lastgate": "45"}
WATCH = {"watch": "50", "fixed": "51", "close": "52"}


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
    t["2"]["nexttasks"] = {"#default#": [WATCH["watch"]], "yes": ["3"]}
    t["3"] = base("3", "regular", "Assign the issue to its owner", "Sets the issue assignee to the owner's email.", 540, x=250,
                  task_extra={"script": "Cortex Core - Platform|||core-update-issue", "iscommand": True, "brand": "Cortex Core - Platform"})
    t["3"]["scriptarguments"] = {"id": arg("issue_id"), "assigned_user_mail": arg("owner_email")}
    t["3"]["continueonerror"] = True
    t["3"]["nexttasks"] = {"#none#": ["8"]}
    t["8"] = base("8", "condition", "Write the message with AI?", "notify.use_ai in CTT - Config; otherwise the FOUND / RULE / FIX template is used.", 880, x=250)
    t["8"]["conditions"] = [{"label": "yes", "condition": is_true("use_ai")}]
    t["8"]["nexttasks"] = {"#default#": [ROUND1["title"]], "yes": ["5"]}
    t["5"] = base("5", "aiTask", "Write the Slack message with AI", "CTTHygieneMessagePrompt writes the DM text (only with notify.use_ai).", 1050, x=50,
                  task_extra={"aiTaskId": "CTTHygieneMessagePrompt"})
    t["5"]["scriptarguments"] = {k: arg(k) for k in ("first_name", "owner_tags", "issue_title", "issue_details", "guideline_id", "guideline_title", "guideline_text")}
    t["5"]["continueonerror"] = True
    t["5"]["nexttasks"] = {"#none#": [ROUND1["title"]]}
    # Two rounds, inline: a loop back to an earlier task deadlocks (a task waits for all incoming
    # tasks), and a looped sub-playbook shows a confusing Work Plan. A second unconfirmed "Fixed"
    # can only happen on a guideline with an automatic check, which the hourly fix check closes
    # once it's really fixed, so two rounds are enough.
    add_round(t, ROUND1, 1220, second=False)
    add_round(t, ROUND2, 2080, second=True)
    add_watch(t, 1380)
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
        "view": json.dumps({"linkLabelsPosition": {}, "paper": {"dimensions": {"height": 3115, "width": 1080, "x": -150, "y": 50}}}),
        "inputs": [],
        "outputs": [],
        "tests": ["No tests (auto formatted)"],
    }


def dm_args(note: str = "", links: bool = True) -> dict:
    args = {
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
        "buttons": arg("buttons"),
    }
    if links:
        args.update(fixed_url={"simple": "${CTT.Ask.fixed_url}"}, not_violation_url={"simple": "${CTT.Ask.not_violation_url}"})
    if note:
        args["note"] = {"simple": note}
    return args


def add_gate(t: dict, key: str, y: int, yes: list[str], no: list[str]) -> None:
    """"Should the owner get a Slack DM?" in front of a DM: no (DMs off, not on the allowlist, no
    Slack ID or the daily limit reached) skips only the DM."""
    t[key] = base(key, "condition", "Should the owner get a Slack DM?", "notify from triage: DMs follow notify in CTT - Config (mode, allowlist, daily limit). No skips only the DM.", y, x=450)
    t[key]["conditions"] = [{"label": "yes", "condition": is_true("notify")}]
    t[key]["nexttasks"] = {"yes": yes, **({"#default#": no} if no else {})}


def add_close(t: dict, key: str, name: str, ctx: str, y: int, x: int) -> None:
    """The last task of a branch: close the issue with the reason and note the fix check wrote.
    Each branch has its own: a shared one would wait for every branch that leads to it."""
    t[key] = base(key, "regular", name, "Closes the issue with the close note saying why (the playbook ends here).", y, x=x,
                  task_extra={"script": "Builtin|||closeInvestigation", "iscommand": True, "brand": "Builtin"})
    t[key]["scriptarguments"] = {"closeReason": {"simple": f"${{{ctx}.reason}}"}, "closeNotes": {"simple": f"${{{ctx}.note}}"}}


def add_watch(t: dict, y: int) -> None:
    """Runs next to the question rounds, or alone when no DM goes out (no owner, DMs off, daily
    limit): checks the fix every hour (polling) and closes the issue when the check sees it fixed.
    Guidelines without a check end this branch at once."""
    t[WATCH["watch"]] = base(WATCH["watch"], "regular", "Watch for the fix", "CTTHygieneFixCheck watch=true: checks every hour until the check sees the issue fixed. Ends at once for guidelines without an automatic check.", y, x=650,
                             task_extra={"scriptName": "CTTHygieneFixCheck"})
    t[WATCH["watch"]]["scriptarguments"] = {"issue_id": arg("issue_id"), "watch": {"simple": "true"}}
    t[WATCH["watch"]]["nexttasks"] = {"#none#": [WATCH["fixed"]]}
    t[WATCH["fixed"]] = base(WATCH["fixed"], "condition", "Fixed?", "", y + 160, x=650)
    t[WATCH["fixed"]]["conditions"] = [{"label": "yes", "condition": [[{"operator": "isTrue", "left": {"value": {"simple": "CTT.FixWatch.close"}, "iscontext": True}}]]}]
    t[WATCH["fixed"]]["nexttasks"] = {"yes": [WATCH["close"]]}
    add_close(t, WATCH["close"], "Close the issue: fixed (checked)", "CTT.FixWatch", y + 320, x=650)


def add_round(t: dict, r: dict, y: int, second: bool) -> None:
    """One question round: ask by Generated link and, in parallel, DM the answer links; then the fix
    check on the answer. The second round starts by clearing the first round's links and its DM
    says what the check still sees; after it, a last DM and the playbook ends."""
    n = 2 if second else 1
    if second:
        t[r["clear"]] = base(r["clear"], "regular", "Clear the first round's answer links", "Asking again appends links; the second DM needs the new ones.", y, x=250,
                             task_extra={"scriptName": "DeleteContext"})
        t[r["clear"]]["scriptarguments"] = {"key": {"simple": "Ask"}}
        t[r["clear"]]["nexttasks"] = {"#none#": [r["title"]]}
        y += 140
    t[r["title"]] = base(r["title"], "title", f"Round {n}: ask the owner", "", y, x=250)
    t[r["title"]]["nexttasks"] = {"#none#": [r["ask"], r["wait"]] + ([] if second else [WATCH["watch"]])}
    t[r["ask"]] = base(r["ask"], "condition", "Did you fix it?" if not second else "Did you fix it? (second time)",
                       "Asked by Generated link: one link per answer, opened without a Cortex login, behind the Mark as Fixed and Mark as False Positive buttons of the DM. Waits until answered (no timeout); the daily digest reminds the owner.", y + 160, x=50)
    t[r["ask"]]["message"] = {
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
    t[r["ask"]]["nexttasks"] = {"Fixed": [r["check"]], "False positive": [r["fp"]]}
    t[r["wait"]] = base(r["wait"], "regular", "Wait for the question's links", "Gives the question time to write its answer links; a script started later gets them in its context.", y + 160, x=450,
                        task_extra={"scriptName": "Sleep"})
    t[r["wait"]]["scriptarguments"] = {"seconds": {"simple": "20"}}
    t[r["wait"]]["nexttasks"] = {"#none#": [r["links"]]}
    t[r["links"]] = base(r["links"], "regular", "Get the answer links", "Returns the newest link per answer.", y + 320, x=450,
                         task_extra={"scriptName": "CTTHygieneAskLinks"})
    t[r["links"]]["scriptarguments"] = {"task_id": {"simple": r["ask"]}}
    # Without links (Generated link unavailable) the DM still goes out, without answer buttons.
    t[r["links"]]["continueonerror"] = True
    t[r["links"]]["nexttasks"] = {"#none#": [r["gate"]]}
    # Only the DM depends on notify (mode, allowlist, Slack ID, daily limit); the rest of the round
    # runs either way.
    add_gate(t, r["gate"], y + 400, [r["dm"]], [] if second else [r["progress"]])
    t[r["dm"]] = base(r["dm"], "regular", "Send the Slack DM" if not second else "Send the second DM",
                      "Lays out the DM (FOUND / RULE / FIX, or the AI text) with the answer links, as Slack buttons when notify.buttons is on, and sends it through the CTT Slack Webhook."
                      + (" Starts with what the check still sees." if second else ""), y + 560, x=450, task_extra={"scriptName": "CTTHygieneSendDM"})
    t[r["dm"]]["scriptarguments"] = dm_args("${CTT.FixCheck.note}" if second else "")
    if not second:
        t[r["dm"]]["nexttasks"] = {"#none#": [r["progress"]]}
        t[r["progress"]] = base(r["progress"], "regular", "Set the issue to In Progress", "The issue now waits for the owner's fix.", y + 720, x=450,
                                task_extra={"script": "Cortex Core - Platform|||core-update-issue", "iscommand": True, "brand": "Cortex Core - Platform"})
        t[r["progress"]]["scriptarguments"] = {"id": arg("issue_id"), "status": {"simple": "In Progress"}}
        t[r["progress"]]["continueonerror"] = True
    t[r["check"]] = base(r["check"], "regular", "Check the owner's fix", "CTTHygieneFixCheck confirm=true: resolves the issue with a close note when the check verifies the fix or the guideline has no check; otherwise keeps it open and writes what is still wrong to CTT.FixCheck.", y + 320, x=50,
                         task_extra={"scriptName": "CTTHygieneFixCheck"})
    t[r["check"]]["scriptarguments"] = {"issue_id": arg("issue_id"), "confirm": {"simple": "true"}, "resolve": {"simple": "false"}}
    t[r["check"]]["nexttasks"] = {"#none#": [r["resolved"]]}
    t[r["resolved"]] = base(r["resolved"], "condition", "Close the issue?", "Yes when the check verified the fix or the guideline has no check.", y + 480, x=50)
    t[r["resolved"]]["conditions"] = [{"label": "yes", "condition": [[{"operator": "isTrue", "left": {"value": {"simple": "CTT.FixCheck.close"}, "iscontext": True}}]]}]
    t[r["resolved"]]["nexttasks"] = {"yes": [r["close"]], "#default#": [r["lastgate"] if second else ROUND2["clear"]]}
    add_close(t, r["close"], "Close the issue: fixed", "CTT.FixCheck", y + 640, x=-50)
    t[r["fp"]] = base(r["fp"], "regular", "Record: false positive", "CTTHygieneFixCheck false_positive=true: tells the CTT channel and writes the False Positive close note.", y + 320, x=-250,
                      task_extra={"scriptName": "CTTHygieneFixCheck"})
    t[r["fp"]]["scriptarguments"] = {"issue_id": arg("issue_id"), "false_positive": {"simple": "true"}, "resolve": {"simple": "false"}}
    t[r["fp"]]["nexttasks"] = {"#none#": [r["fpclose"]]}
    add_close(t, r["fpclose"], "Close the issue: false positive", "CTT.FixCheck", y + 480, x=-250)
    if second:
        add_gate(t, r["lastgate"], y + 640, [r["last"]], [])
        t[r["last"]] = base(r["last"], "regular", "Tell the owner it closes by itself", "Last DM: what the check still sees, and that the hourly fix check closes the issue once it's fixed. No more questions.", y + 800, x=50,
                            task_extra={"scriptName": "CTTHygieneSendDM"})
        t[r["last"]]["scriptarguments"] = dm_args(
            "You said this is fixed, but the check still sees it: ${CTT.FixCheck.evidence}. The issue closes by itself within an hour once it is fixed.",
            links=False,
        )
        # No next task: the watch branch closes the issue once the check sees it fixed.


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
    (PACK / "Playbooks" / "playbook-CTT-Hygiene-Notify-Owner_README.md").write_text(
        "Runs on every CTT hygiene health issue (trigger `CTT - Hygiene - Notify Owner`).\n\n"
        "1. `CTTHygieneTriage` finds the owner from the issue's `[owner: ...]` marker, their name, role and Slack ID in the CTT registry, and the guideline.\n"
        "2. `core-update-issue` assigns the issue to the owner's email.\n"
        "3. With `notify.use_ai`, the `CTTHygieneMessagePrompt` AI task writes the DM text; otherwise the FOUND / RULE / FIX template from triage is used.\n"
        "4. **Round 1**: **Did you fix it?** is asked by Generated link (no timeout); in parallel `CTTHygieneAskLinks` gets its links and `CTTHygieneSendDM` sends the DM with the buttons **Mark as Fixed**, **Mark as False Positive** and **View Issue** (`notify.buttons`; otherwise links in the text). The issue is set to In Progress.\n"
        "5. **Watch** (parallel): `CTTHygieneFixCheck watch=true` checks every hour and closes the issue once the check sees it fixed (guidelines with an automatic check).\n"
        "6. **Mark as Fixed** runs `CTTHygieneFixCheck confirm=true resolve=false`: a verified fix (or a guideline without a check) closes the issue; otherwise **round 2** asks once more with a DM that says what is still wrong, and after a second unconfirmed answer a last DM says the issue closes by itself once fixed.\n"
        "7. **Mark as False Positive** runs `CTTHygieneFixCheck false_positive=true resolve=false` (a post in the CTT channel) and closes the issue as False Positive.\n\n"
        "Without a DM (DMs off, not on the allowlist, no Slack ID or the daily limit) the rounds run without the DM; an issue without an owner only gets the watch. The issue is always closed by the last task of a branch (`closeInvestigation` with the close note), never halfway. "
        "Assigning and the AI step continue on error. DMs follow `notify.mode` (`off`, `admins_only`, `all`) and the daily limit in `CTT - Config`.\n"
    )
    (PACK / "Triggers").mkdir(exist_ok=True)
    (PACK / "Triggers" / "Trigger-CTT-Hygiene-Notify-Owner.json").write_text(json.dumps(trigger(), indent=4) + "\n")
    print("wrote playbook and trigger")


if __name__ == "__main__":
    main()
