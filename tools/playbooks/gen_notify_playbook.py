"""Generate the 'CTT - Hygiene - Notify Owner' playbook, its 'CTT - Hygiene - Ask Owner'
sub-playbook and the trigger.

Run from content/:  uv run --with pyyaml python3 tools/playbooks/gen_notify_playbook.py

Notify Owner (started by the automation rule on every CTT hygiene issue):
  duplicate? -> close | already fixed? -> close | triage -> assign -> In Progress ->
  [Ask Owner sub-playbook, looped until the answer closes it -> close] in parallel with
  [hourly watch -> close]. A link back to an earlier task deadlocks (a task waits for all its
  incoming links), so the re-ask is the sub-playbook task's own loop ("repeat until").
Every branch ends in its own close task, so the issue is closed by the playbook's last task.
"""

import json
import uuid
from pathlib import Path

import yaml

PACK = Path(__file__).resolve().parent.parent.parent / "Packs" / "CTTManagement"
NAME = "CTT - Hygiene - Notify Owner"
ASK = "CTT - Hygiene - Ask Owner"
NS = uuid.UUID("7a1e3c5d-9b2f-4e6a-8c0d-1f2e3d4c5b6a")
CTX = "CTT.Triage"
ROUND = {"clear": "1", "title": "2", "ask": "21", "wait": "22", "links": "23", "gate": "43", "dm": "24", "nodm": "44", "check": "26", "resolved": "27", "done": "29", "remember": "30", "fp": "28", "fpdone": "40"}
MAX_ROUNDS = 10  # the parent's loop over Ask Owner; the hourly watch keeps going after that
WATCH = {"watch": "50", "fixed": "51", "close": "52", "ended": "57"}
# Every condition task needs a #default# branch: a condition none of whose branches match fails the
# task ("The output [] didn't satisfy any of the conditions", playbook state error).
OPEN_AFTER_ROUNDS = "20"
THANKS = {"answer": ("53", "54"), "watch": ("55", "56")}  # (gate, DM) in front of close 19 / 52
_PB = NAME  # the playbook whose task IDs tid() derives; set per playbook in build()


def tid(key: str) -> str:
    return str(uuid.uuid5(NS, f"{_PB}-{key}"))


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


def is_set(path: str) -> list:
    return [[{"operator": "isNotEmpty", "left": {"value": {"simple": path}, "iscontext": True}}]]


def is_on(path: str) -> list:
    return [[{"operator": "isTrue", "left": {"value": {"simple": path}, "iscontext": True}}]]


def wrap(name: str, description: str, tasks: dict, height: int) -> dict:
    return {
        "id": name,
        "version": -1,
        "name": name,
        "description": description,
        "fromversion": "8.15.0",
        "marketplaces": ["marketplacev2", "platform"],
        "tags": ["CTT"],
        # Pack-installed playbooks must be adopted before a job, a trigger or the API can attach
        # them to an issue ("playbook is not adopted (69)"); this adopts them on install.
        "adopted": True,
        "starttaskid": "0",
        "tasks": tasks,
        "view": json.dumps({"linkLabelsPosition": {}, "paper": {"dimensions": {"height": height, "width": 1300, "x": -250, "y": 50}}}),
        "inputs": [],
        "outputs": [],
        "tests": ["No tests (auto formatted)"],
    }


def notify_playbook() -> dict:
    global _PB
    _PB = NAME
    t = {}
    t["0"] = base("0", "start", "", "", 50)
    t["0"]["nexttasks"] = {"#none#": ["9"]}
    # A re-run on the same issue appended a second triage result to the context, so the send
    # task looped over two Slack IDs and sent the DM twice. Start from a clean context.
    t["9"] = base("9", "regular", "Clear context from an earlier run", "Deletes the issue context so a re-run sends one DM.", 180,
                  task_extra={"scriptName": "DeleteContext"})
    t["9"]["scriptarguments"] = {"all": {"simple": "yes"}}
    t["9"]["nexttasks"] = {"#none#": ["10"]}
    # 1. Known already? The daily rules raise the same finding again once their one-day suppression
    # ends, and a false positive would come back the next day.
    t["10"] = base("10", "regular", "Look for the same problem in other issues", "CTTHygieneDuplicateCheck: another open issue about the same endpoint, user or object, or one marked a false positive in the last notify.false_positive_days days.", 310,
                   task_extra={"scriptName": "CTTHygieneDuplicateCheck"})
    t["10"]["nexttasks"] = {"#none#": ["11"]}
    t["11"] = base("11", "condition", "Is the same problem already open, or marked a false positive?", "", 440)
    t["11"]["conditions"] = [{"label": "yes", "condition": is_set("CTT.Duplicate.duplicate_of")}]
    t["11"]["nexttasks"] = {"yes": ["12"], "#default#": ["13"]}
    add_close(t, "12", "Close the issue: duplicate", "CTT.Duplicate", 440, x=900)
    # 2. Fixed already? A playbook created with the owner's tag in its Tags field, an endpoint
    # moved before the playbook ran: close without assigning or notifying anyone.
    t["13"] = base("13", "regular", "Check whether it is already fixed", "CTTHygieneFixCheck resolve=false: the guideline's automatic check, if it has one. Writes the close reason and note to CTT.FixCheck.", 600,
                   task_extra={"scriptName": "CTTHygieneFixCheck"})
    t["13"]["scriptarguments"] = {"issue_id": {"simple": "${CTT.Duplicate.issue_id}"}, "resolve": {"simple": "false"}}
    t["13"]["continueonerror"] = True
    t["13"]["nexttasks"] = {"#none#": ["14"]}
    t["14"] = base("14", "condition", "Already fixed?", "", 760)
    t["14"]["conditions"] = [{"label": "yes", "condition": is_on("CTT.FixCheck.close")}]
    t["14"]["nexttasks"] = {"yes": ["15"], "#default#": ["1"]}
    add_close(t, "15", "Close the issue: already fixed", "CTT.FixCheck", 760, x=900)
    # 3. Assign, then ask the owner (sub-playbook) and watch for the fix in parallel.
    t["1"] = base("1", "regular", "Triage the hygiene issue", "Finds the owner, their Slack ID and the guideline, and decides whether to assign and notify.", 920,
                  task_extra={"scriptName": "CTTHygieneTriage"})
    t["1"]["nexttasks"] = {"#none#": ["2"]}
    t["2"] = base("2", "condition", "Can the issue be assigned to a person?", "", 1080)
    t["2"]["conditions"] = [{"label": "yes", "condition": is_true("assign")}]
    t["2"]["nexttasks"] = {"#default#": [WATCH["watch"]], "yes": ["3"]}
    t["3"] = base("3", "regular", "Assign the issue to its owner", "Sets the issue assignee to the owner: their @paloaltonetworks.com account when it exists, else their CTT SSO account (@asean.ctt).", 1240, x=250,
                  task_extra={"script": "Cortex Core - Platform|||core-update-issue", "iscommand": True, "brand": "Cortex Core - Platform"})
    t["3"]["scriptarguments"] = {"id": arg("issue_id"), "assigned_user_mail": arg("assignee_email")}
    t["3"]["continueonerror"] = True
    t["3"]["nexttasks"] = {"#none#": ["4"]}
    t["4"] = base("4", "regular", "Set the issue to In Progress", "The issue now waits for the owner's fix.", 1400, x=250,
                  task_extra={"script": "Cortex Core - Platform|||core-update-issue", "iscommand": True, "brand": "Cortex Core - Platform"})
    t["4"]["scriptarguments"] = {"id": arg("issue_id"), "status": {"simple": "In Progress"}}
    t["4"]["continueonerror"] = True
    t["4"]["nexttasks"] = {"#none#": ["8"]}
    t["8"] = base("8", "condition", "Write the message with AI?", "notify.use_ai in CTT - Config; otherwise the FOUND / RULE / FIX template is used.", 1560, x=250)
    t["8"]["conditions"] = [{"label": "yes", "condition": is_true("use_ai")}]
    t["8"]["nexttasks"] = {"#default#": ["16"], "yes": ["5"]}
    t["5"] = base("5", "aiTask", "Write the Slack message with AI", "CTTHygieneMessagePrompt writes the DM text (only with notify.use_ai).", 1560, x=650,
                  task_extra={"aiTaskId": "CTTHygieneMessagePrompt"})
    t["5"]["scriptarguments"] = {k: arg(k) for k in ("first_name", "owner_tags", "issue_title", "issue_details", "guideline_id", "guideline_title", "guideline_text")}
    t["5"]["continueonerror"] = True
    t["5"]["nexttasks"] = {"#none#": ["16"]}
    t["16"] = base("16", "title", "Ask the owner and watch for the fix", "", 1720, x=250)
    t["16"]["nexttasks"] = {"#none#": ["17", WATCH["watch"]]}
    t["17"] = base("17", "playbook", "Ask the owner", f"Runs {ASK} (one round: DM with Mark as Fixed / Mark as False Positive, the answer, the fix check on it) again until the answer closes the issue, at most {MAX_ROUNDS} rounds. Its result is in CTT.FixCheck.", 1880, x=50,
                   task_extra={"playbookName": ASK})
    t["17"]["separatecontext"] = False
    t["17"]["loop"] = {"iscommand": False, "exitCondition": "", "wait": 1, "max": MAX_ROUNDS, "builtincondition": is_on("CTT.FixCheck.close")}
    t["17"]["nexttasks"] = {"#none#": ["18"]}
    t["18"] = base("18", "condition", "Did the owner's answer close it?", "Yes for a verified fix, a guideline without a check, or a false positive.", 2040, x=50)
    t["18"]["conditions"] = [{"label": "yes", "condition": is_on("CTT.FixCheck.close")}]
    t["18"]["nexttasks"] = {"yes": [THANKS["answer"][0]], "#default#": [OPEN_AFTER_ROUNDS]}
    t[OPEN_AFTER_ROUNDS] = base(OPEN_AFTER_ROUNDS, "title", "Still open after the last question round", "The issue stays open; the hourly check and the daily digest carry on.", 2200, x=-250)
    add_thanks(t, THANKS["answer"], "19", "CTT.FixCheck", 2200, x=50)
    add_close(t, "19", "Close the issue: the owner's answer", "CTT.FixCheck", 2520, x=50)
    add_watch(t, 1880)
    return wrap(
        NAME,
        "Runs on every CTT hygiene health issue. Closes it at once when the same problem is already open (or was marked a false positive recently) or the guideline's check sees it fixed. Otherwise assigns it to the person responsible (from the issue's owner marker and the CTT registry), sets it In Progress, and runs CTT - Hygiene - Ask Owner (Slack DM with Mark as Fixed / Mark as False Positive) next to an hourly fix check (scheduled command). Every branch ends in its own close task with a close note saying why.",
        t,
        2700,
    )


def ask_playbook() -> dict:
    global _PB
    _PB = ASK
    t = {}
    t["0"] = base("0", "start", "", "", 50)
    t["0"]["nexttasks"] = {"#none#": [ROUND["clear"]]}
    add_round(t, ROUND, 180)
    return wrap(
        ASK,
        "Sub-playbook of CTT - Hygiene - Notify Owner, one round per run (the parent repeats it until the answer closes the issue): asks the owner \"Did you fix it?\" by Generated link and sends the Slack DM with the answers as buttons (Mark as Fixed / Mark as False Positive / View Issue). From the second round on, the DM starts with what the check still saw (CTT.Reask.note). Mark as Fixed runs the fix check; Mark as False Positive records it and tells the CTT channel. Writes the result to CTT.FixCheck (close, reason, note); the parent closes the issue. Runs in the parent's context.",
        t,
        1400,
    )


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


def add_thanks(t: dict, keys: tuple[str, str], close: str, ctx: str, y: int, x: int) -> None:
    """Thank the owner before the close task (closing the issue stops the playbook, so nothing runs
    after it). Same gate as the question's DM; a failed DM never blocks the close."""
    gate, dm = keys
    t[gate] = base(gate, "condition", "Should the owner get a Slack DM?", "notify from triage (mode, allowlist, Slack ID). No closes the issue without a thank-you.", y, x=x)
    t[gate]["conditions"] = [{"label": "yes", "condition": is_true("notify")}]
    t[gate]["nexttasks"] = {"yes": [dm], "#default#": [close]}
    t[dm] = base(dm, "regular", "Thank the owner", "CTTHygieneSendDM closed=true: thanks the owner and quotes the close note. Doesn't count toward the daily DM limit.", y + 160, x=x,
                 task_extra={"scriptName": "CTTHygieneSendDM"})
    t[dm]["scriptarguments"] = {
        "slack_user_id": arg("slack_id"),
        "owner_email": arg("owner_email"),
        "first_name": arg("first_name"),
        "issue_id": arg("issue_id"),
        "issue_url": arg("issue_url"),
        "guideline_id": arg("guideline_id"),
        "closed": {"simple": "true"},
        "close_reason": {"simple": f"${{{ctx}.reason}}"},
        "close_note": {"simple": f"${{{ctx}.note}}"},
    }
    t[dm]["continueonerror"] = True
    t[dm]["nexttasks"] = {"#none#": [close]}


def add_watch(t: dict, y: int) -> None:
    """Runs next to the Ask Owner sub-playbook, or alone for an issue without an owner: a scheduled
    command (polling: true, ScheduledCommand every hour, see xsoar.pan.dev scheduled-commands)
    that checks the fix and closes the issue when the check sees it fixed. Guidelines without a
    check end this branch at once."""
    t[WATCH["watch"]] = base(WATCH["watch"], "regular", "Watch for the fix", "CTTHygieneFixCheck watch=true: checks every hour until the check sees the issue fixed. Ends at once for guidelines without an automatic check.", y, x=650,
                             task_extra={"scriptName": "CTTHygieneFixCheck"})
    t[WATCH["watch"]]["scriptarguments"] = {"issue_id": arg("issue_id"), "watch": {"simple": "true"}}
    t[WATCH["watch"]]["nexttasks"] = {"#none#": [WATCH["fixed"]]}
    t[WATCH["fixed"]] = base(WATCH["fixed"], "condition", "Fixed?", "", y + 160, x=650)
    t[WATCH["fixed"]]["conditions"] = [{"label": "yes", "condition": [[{"operator": "isTrue", "left": {"value": {"simple": "CTT.FixWatch.close"}, "iscontext": True}}]]}]
    t[WATCH["fixed"]]["nexttasks"] = {"yes": [THANKS["watch"][0]], "#default#": [WATCH["ended"]]}
    t[WATCH["ended"]] = base(WATCH["ended"], "title", "Watch ended: no automatic check for this issue", "Guidelines and object types without a check, and the daily inventory issues (they close at the next inventory run).", y + 320, x=1000)
    add_thanks(t, THANKS["watch"], WATCH["close"], "CTT.FixWatch", y + 320, x=650)
    add_close(t, WATCH["close"], "Close the issue: fixed (checked)", "CTT.FixWatch", y + 640, x=650)


def add_end(t: dict, key: str, name: str, y: int, x: int) -> None:
    """End of a sub-playbook branch: the parent reads CTT.FixCheck and closes the issue."""
    t[key] = base(key, "title", name, "", y, x=x)


def add_round(t: dict, r: dict, y: int) -> None:
    """One question round: ask by Generated link and, in parallel, DM the answer links; then the fix
    check on the answer. A fix the check can't confirm writes CTT.Reask.note, so the next round's
    DM (the parent loops) starts with what is still wrong."""
    t[r["clear"]] = base(r["clear"], "regular", "Clear the last round's answer links", "Asking again appends links; the DM needs the new ones.", y, x=250,
                         task_extra={"scriptName": "DeleteContext"})
    t[r["clear"]]["scriptarguments"] = {"key": {"simple": "Ask"}}
    t[r["clear"]]["nexttasks"] = {"#none#": [r["title"]]}
    y += 140
    t[r["title"]] = base(r["title"], "title", "Ask the owner", "", y, x=250)
    t[r["title"]]["nexttasks"] = {"#none#": [r["ask"], r["wait"]]}
    t[r["ask"]] = base(r["ask"], "condition", "Did you fix it?",
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
    # Only the DM depends on notify (mode, allowlist, Slack ID, daily limit); the question waits
    # either way.
    add_gate(t, r["gate"], y + 480, [r["dm"]], [r["nodm"]])
    t[r["nodm"]] = base(r["nodm"], "title", "No DM (see the triage reason)", "", y + 640, x=700)
    t[r["dm"]] = base(r["dm"], "regular", "Send the Slack DM",
                      "Lays out the DM (FOUND / RULE / FIX, or the AI text) with the answer links, as Slack buttons when notify.buttons is on, and sends it through the CTT Slack Webhook. From the second round on it starts with what the check still saw (CTT.Reask.note).",
                      y + 640, x=450, task_extra={"scriptName": "CTTHygieneSendDM"})
    t[r["dm"]]["scriptarguments"] = dm_args("${CTT.Reask.note}")
    t[r["check"]] = base(r["check"], "regular", "Check the owner's fix", "CTTHygieneFixCheck confirm=true resolve=false: close (with a note) when the check verifies the fix or the guideline has no check; otherwise writes what is still wrong to CTT.FixCheck.", y + 320, x=50,
                         task_extra={"scriptName": "CTTHygieneFixCheck"})
    t[r["check"]]["scriptarguments"] = {"issue_id": arg("issue_id"), "confirm": {"simple": "true"}, "resolve": {"simple": "false"}}
    t[r["check"]]["nexttasks"] = {"#none#": [r["resolved"]]}
    t[r["resolved"]] = base(r["resolved"], "condition", "Fixed?", "Yes when the check verified the fix or the guideline has no check.", y + 480, x=50)
    t[r["resolved"]]["conditions"] = [{"label": "yes", "condition": is_on("CTT.FixCheck.close")}]
    t[r["resolved"]]["nexttasks"] = {"yes": [r["done"]], "#default#": [r["remember"]]}
    add_end(t, r["done"], "Fixed: the parent closes the issue", y + 640, x=-150)
    # Not the first time we ask: the next round's DM says what the check still sees.
    t[r["remember"]] = base(r["remember"], "regular", "Note what is still wrong for the next round", "Sets CTT.Reask.note to the fix check's note; the parent runs the next round, whose DM starts with it.", y + 640, x=50,
                            task_extra={"scriptName": "Set"})
    t[r["remember"]]["scriptarguments"] = {"key": {"simple": "CTT.Reask.note"}, "value": {"simple": "${CTT.FixCheck.note}"}}
    t[r["fp"]] = base(r["fp"], "regular", "Record: false positive", "CTTHygieneFixCheck false_positive=true resolve=false: tells the CTT channel and writes the False Positive close note.", y + 320, x=-350,
                      task_extra={"scriptName": "CTTHygieneFixCheck"})
    t[r["fp"]]["scriptarguments"] = {"issue_id": arg("issue_id"), "false_positive": {"simple": "true"}, "resolve": {"simple": "false"}}
    t[r["fp"]]["nexttasks"] = {"#none#": [r["fpdone"]]}
    add_end(t, r["fpdone"], "False positive: the parent closes the issue", y + 480, x=-350)


def trigger() -> dict:
    return {
        "trigger_id": uuid.uuid5(NS, "trigger").hex,
        "playbook_id": NAME,
        "suggestion_reason": "Assign CTT hygiene issues to their owner and notify them on Slack",
        "description": "Runs the CTT - Hygiene - Notify Owner playbook on every CTT hygiene health issue.",
        "trigger_name": NAME,
        "fromVersion": "8.15.0",
        # The tenant installs this as a suggested automation rule; an admin enables it once in the UI.
        # Never set is_auto_enabled: it is a system flag for autonomous SOC rules. In 1.2.0-1.4.0 it
        # turned this rule into a system rule (not editable, its playbook runs affected), per
        # support 2026-11-26.
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
    books = PACK / "Playbooks"
    (books / "playbook-CTT-Hygiene-Notify-Owner.yml").write_text(yaml.dump(notify_playbook(), sort_keys=False, width=10000))
    (books / "playbook-CTT-Hygiene-Ask-Owner.yml").write_text(yaml.dump(ask_playbook(), sort_keys=False, width=10000))
    (books / "playbook-CTT-Hygiene-Notify-Owner_README.md").write_text(
        "Runs on every CTT hygiene health issue (trigger `CTT - Hygiene - Notify Owner`).\n\n"
        "1. **Same problem already known?** `CTTHygieneDuplicateCheck` looks for another open issue about the same endpoint, user or object, or one marked a false positive in the last `notify.false_positive_days` days. If so, the issue is closed as Duplicate Issue.\n"
        "2. **Already fixed?** `CTTHygieneFixCheck resolve=false` runs the guideline's automatic check. If it sees the fix (for example a playbook with the owner's tag in its Tags field), the issue is closed with a note saying why, before anyone is assigned or notified.\n"
        "3. `CTTHygieneTriage` finds the owner from the issue's `[owner: ...]` marker, their name, role and Slack ID in the CTT registry, and the guideline; `core-update-issue` assigns the issue and sets it In Progress.\n"
        "4. With `notify.use_ai`, the `CTTHygieneMessagePrompt` AI task writes the DM text; otherwise the FOUND / RULE / FIX template from triage is used.\n"
        f"5. In parallel:\n   - **Ask the owner:** the `{ASK}` sub-playbook, one round per run (DM with Mark as Fixed / Mark as False Positive, the answer, the fix check on it), repeated by the task's loop until the answer closes the issue (at most {MAX_ROUNDS} rounds). A link back to an earlier task would deadlock, so the re-ask is the loop.\n"
        "   - **Watch:** `CTTHygieneFixCheck watch=true`, a scheduled command (polling) that checks every hour and closes the issue once the check sees it fixed.\n"
        "6. Before either of those closes, `CTTHygieneSendDM closed=true` thanks the owner and quotes the close note (same DM gate; it doesn't count toward the daily limit). Duplicates and issues that were already fixed close without a DM: the owner was never asked.\n\n"
        "An issue without an owner only gets the watch. The issue is always closed by the last task of a branch (`closeInvestigation` with the close note), never halfway; closing it stops the other branch. "
        "Assigning continues on error. DMs follow `notify.mode` (`off`, `allowlist`, `admins_only`, `all`) and the daily limit in `CTT - Config`.\n"
    )
    (books / "playbook-CTT-Hygiene-Ask-Owner_README.md").write_text(
        f"Sub-playbook of `{NAME}`, one question round per run; the parent's task loops it until the answer closes the issue (at most {MAX_ROUNDS} rounds). It runs in the parent's context (CTT.Triage) and writes its result to CTT.FixCheck (`close`, `reason`, `note`). The parent closes the issue.\n\n"
        "1. **Did you fix it?** is asked by Generated link (no timeout); in parallel `CTTHygieneAskLinks` gets its links and `CTTHygieneSendDM` sends the DM with the buttons **Mark as Fixed**, **Mark as False Positive** and **View Issue** (`notify.buttons`; otherwise links in the text). Without a DM (DMs off, not on the allowlist, no Slack ID, daily limit) only the DM is skipped.\n"
        "2. **Mark as Fixed** runs `CTTHygieneFixCheck confirm=true resolve=false`: a verified fix (or a guideline without a check) ends the round with `close`. Otherwise the round writes the check's note to `CTT.Reask.note` and ends; the next round's DM starts with it (\"You said this is fixed, but the check still sees it: …\").\n"
        "3. **Mark as False Positive** runs `CTTHygieneFixCheck false_positive=true resolve=false` (a post in the CTT channel) and ends with `close` (False Positive).\n"
    )
    (PACK / "Triggers").mkdir(exist_ok=True)
    (PACK / "Triggers" / "Trigger-CTT-Hygiene-Notify-Owner.json").write_text(json.dumps(trigger(), indent=4) + "\n")
    print("wrote playbooks and trigger")


if __name__ == "__main__":
    main()
