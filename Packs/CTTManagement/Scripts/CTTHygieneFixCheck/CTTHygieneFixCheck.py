import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import re
import textwrap
import time
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

PREFIX = "CTT - Hygiene - "
NAME_RE = re.compile(r"^CTT - Hygiene - (CTT-[A-Z]+-\d+) - ")
# Same object pattern as CTTHygieneTriage: "<actor> created|saved|ran ... on <kind> '<name>'".
OBJ_RE = re.compile(r"\b(?:created|saved|on) (?P<kind>[A-Za-z][\w ]*?) '(?P<name>[^']+)'")
OWNER_RE = re.compile(r"\[owner: ([^\]]*)\]")
ENDPOINT_RE = re.compile(r"^Endpoint (?P<name>.+?): ")
EMAIL_RE = re.compile(r"^(?P<email>[^\s@]+@[^\s@]+) signed in")
TAG_RE = re.compile(r"^\s*([A-Za-z0-9]{2,16})\s*[-_]")
# Issues of the inventory check resolve themselves through its own plan().
INVENTORY_MARKERS = ("The inventory check found", "The sweep found", "Daily sweep found")
NO_OWNER = {"", "unknown", "null", "none", "unassigned"}
# Kinds with a Tags field: one of the owner's tags there replaces the name prefix (CTT-TAG-01).
TAGGED_KINDS = ("Playbook", "Script", "Job")
# Audit-log object kinds whose objects the API can list by name (audit kind -> listed kind).
LISTED_KINDS = {
    "Playbook": "Playbook",
    "Script": "Script",
    "Automation": "Script",
    "Job": "Job",
    "JobCenter": "Job",
    "Integrations": "Integration instance",
    "Integration": "Integration instance",
    "Integration instance": "Integration instance",
    "Correlation rule": "Correlation rule",
    "Lookup dataset": "Dataset",
    "Dataset": "Dataset",
}
BUILTIN_KINDS = {"Playbook": "Playbook", "Script": "Script", "Automation": "Script"}
NO_CHECK = {
    "CTT-OWN-01": "it records a change to someone else's object, which can't be undone automatically",
    "CTT-CEN-01": "it records a change in a centrally managed area",
    "CTT-OOTB-02": "agent changes can't be compared with the built-in version",
}
CONFIG_LIST = "CTT - Config"
STATE_LIST = "CTT - Fix State"
NOTIFY_STATE = "CTT - Notify State"
PAGE = 100
DAY_MS = 86_400_000
WIDTH = 46
SGT = timezone(timedelta(hours=8))
FIXED_REASON = "Resolved - Fixed"
FALLBACK_REASON = "Resolved - Other"
FALSE_POSITIVE_REASON = "Resolved - False Positive"
# An issue whose Notify Owner playbook is in one of these states is closed by that playbook (its
# last task), never by the job: closing an issue stops its playbook halfway.
ACTIVE_PLAYBOOK = {"running", "waiting", "pending", "inprogress", "in_progress"}
WATCH_SECONDS = 3600
WATCH_TIMEOUT = 90 * 86_400

# BEGIN GENERATED FIX_POLICY_QUERY (tools/correlation_rules/gen_correlation_rules.py; do not edit)
FIX_POLICY_QUERY = (
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
    "| join type = left (dataset = ctt_registry | alter obj_tag = ctt_tag, obj_owner = owner_email, obj_o"
    "wner_role = role | fields obj_tag, obj_owner, obj_owner_role) as ro ro.obj_tag = obj_tag\n"
    '| filter object_kind not in ("AITask", "CaseField", "IssueField", "Credentials", "KnowledgeSource", '
    '"Investigation", "Indicator", "Entry", "War Room", "Whitelist", "Content", "Execute")\n'
    '| filter object_kind = "Policy rule" and object_name in ("__NAMES__")\n'
    '| alter scope_target = coalesce(arrayindex(regextract(description, "with target (.+?) created$"), 0)'
    ', arrayindex(regextract(description, "scope updated to include: (.+)$"), 0))\n'
    '| filter action = "delete" or scope_target != null\n'
    '| alter scope_tags = arrayindex(regextract(scope_target, "tags (?:=|in) ([^=]+?)(?: and [a-z ]+ (?:='
    '|in) .*)?$"), 0)\n'
    "| dedup object_name by desc _time\n"
    "| fields _time, object_name, action, actor, scope_target, scope_tags"
)
# END GENERATED FIX_POLICY_QUERY
# BEGIN GENERATED FIX_ENDPOINT_QUERY (tools/correlation_rules/gen_correlation_rules.py; do not edit)
FIX_ENDPOINT_QUERY = (
    "dataset = endpoints\n"
    "| dedup endpoint_id by desc last_seen\n"
    '| alter etags = arrayconcat(json_extract_scalar_array(tags, "$.endpoint_tags"), json_extract_scalar_'
    'array(tags, "$.server_tags"))\n'
    '| alter etags = if(etags = null or array_length(etags) = 0, arraycreate("-"), etags)\n'
    '| alter policy_tag = lowercase(arrayindex(regextract(assigned_prevention_policy, "^\\s*([A-Za-z0-9]{2'
    ',16})\\s*[-_]"), 0)), package_tag = lowercase(arrayindex(regextract(installation_package, "^\\s*([A-Za'
    '-z0-9]{2,16})\\s*[-_]"), 0))\n'
    '| alter lab_ip = coalesce(arrayindex(arrayfilter(ip_address, "@element" ~= "^10\\."), 0), arrayindex('
    'arrayfilter(ip_address, "@element" ~= "^172\\.16\\."), 0))\n'
    '| alter ip_octet = coalesce(arrayindex(regextract(lab_ip, "^10\\.(\\d+)\\."), 0), arrayindex(regextract'
    '(lab_ip, "^172\\.16\\.(\\d+)\\."), 0))\n'
    "| arrayexpand etags\n"
    "| alter etag = lowercase(etags)\n"
    '| join type = left (dataset = ctt_registry | filter role != "central" | alter etag = ctt_tag, etag_o'
    "wner = owner_email | fields etag, etag_owner) as te te.etag = etag\n"
    "| comp max(etag_owner) as tag_owner by endpoint_id, endpoint_name, lab_ip, ip_octet, policy_tag, pac"
    "kage_tag, assigned_prevention_policy, installation_package\n"
    '| join type = left (dataset = ctt_registry | filter role != "central" | alter policy_tag = ctt_tag, '
    "policy_owner = owner_email | fields policy_tag, policy_owner) as tp tp.policy_tag = policy_tag\n"
    '| join type = left (dataset = ctt_registry | filter role != "central" | alter package_tag = ctt_tag,'
    " package_owner = owner_email | fields package_tag, package_owner) as tk tk.package_tag = package_tag"
    "\n"
    '| join type = left (dataset = ctt_registry | filter lab_octet != "" | comp max(owner_email) as range'
    "_owner by lab_octet | alter ip_octet = lab_octet | fields ip_octet, range_owner) as tr tr.ip_octet ="
    " ip_octet\n"
    '| join type = left (dataset = ctt_object_owners | filter object_kind = "Agent installer" and object_'
    'name !~= "^(?i)ctt\\s*[-_]" | alter installation_package = object_name, installer_owner = coalesce(cr'
    "eator, last_editor) | fields installation_package, installer_owner) as io io.installation_package = "
    "installation_package\n"
    '| join type = left (dataset = ctt_object_owners | filter object_kind = "Policy rule" and object_name'
    ' !~= "^(?i)(ctt\\s*[-_]|default)" | alter assigned_prevention_policy = object_name, policy_editor = l'
    "ast_editor | fields assigned_prevention_policy, policy_editor) as po po.assigned_prevention_policy ="
    " assigned_prevention_policy\n"
    '| alter installer_owner = if(installer_owner = "", null, installer_owner), policy_editor = if(policy'
    '_editor = "", null, policy_editor)\n'
    "| alter owner = coalesce(tag_owner, policy_owner, package_owner, installer_owner, policy_editor)\n"
    '| alter owner_source = if(tag_owner != null, "endpoint tag", if(policy_owner != null, "tag in its po'
    'licy name", if(package_owner != null, "tag in its installer name", if(installer_owner != null, conca'
    't("creator of installer ", installation_package), if(policy_editor != null, concat("last editor of p'
    'olicy ", assigned_prevention_policy), null)))))\n'
    '| alter owner_label = coalesce(owner, "unknown"), owner_note = if(owner != null, concat("Owner: ", o'
    'wner, " (", owner_source, ")."), "No owner found: add your tag to the endpoint.")\n'
    '| filter endpoint_name in ("__NAMES__")\n'
    "| alter violating = if(lab_ip != null and (range_owner = null or (owner != null and range_owner != o"
    "wner)), 1, 0)\n"
    "| fields endpoint_name, lab_ip, owner, range_owner, violating"
)
# END GENERATED FIX_ENDPOINT_QUERY


# ---------- parsing ----------


def parse_issue(issue: dict) -> dict | None:
    """The fields a fix check needs, or None for issues it doesn't handle."""
    name, desc = str(issue.get("name") or ""), str(issue.get("description") or "")
    m = NAME_RE.match(name)
    if not m or desc.startswith(INVENTORY_MARKERS):
        return None
    obj, marker = OBJ_RE.search(desc), OWNER_RE.search(desc)
    owner = (marker.group(1) if marker else "").strip().lower()
    if owner in NO_OWNER:
        owner = str(issue.get("assigned_user_mail") or "").lower()
    endpoint, email = ENDPOINT_RE.match(desc), EMAIL_RE.match(desc)
    return {
        "id": str(issue.get("id")),
        "guideline": m.group(1),
        "title": name,
        "kind": obj.group("kind") if obj else "",
        "name": obj.group("name") if obj else "",
        "owner": "" if owner in NO_OWNER else owner,
        "endpoint": endpoint.group("name") if endpoint else "",
        "email": email.group("email").lower() if email else "",
        "created": int(issue.get("_insert_time") or 0),
        "cases": [str(c) for c in issue.get("case_ids") or []],
        "playbook": str(issue.get("playbook_run_status") or "").lower(),
    }


def what(item: dict) -> str:
    """A short label for the object an issue is about."""
    if item["endpoint"]:
        return f"endpoint {item['endpoint']}"
    if item["name"]:
        return f"{item['kind'].lower()} '{item['name']}'"
    if item["email"]:
        return item["email"]
    return item["title"].split(" - ", 3)[-1]


# ---------- checks: each returns (verdict, text), verdict fixed | open | unchecked ----------


def registry_people(rows: list[dict]) -> dict[str, dict]:
    people: dict[str, dict] = {}
    for r in rows:
        email = str(r.get("owner_email") or "").lower()
        if email and r.get("active") != "false" and (email not in people or r.get("tag_kind") == "primary"):
            people[email] = r
    return people


def owner_tags(rows: list[dict], owner: str) -> set[str]:
    tags = {str(r.get("tag") or "").lower() for r in rows if str(r.get("owner_email") or "").lower() == owner}
    tags.discard("")
    if any(str(r.get("owner_email") or "").lower() == owner and r.get("role") in ("admin", "central") for r in rows):
        tags.add("ctt")
    return tags


def check_registry(item: dict, people: dict[str, dict]) -> tuple[str, str]:
    email = item["email"] or item["owner"]
    entry = people.get(email)
    if entry:
        tag = entry.get("tag")
        return "fixed", f"{email} is now in the CTT registry" + (f" (tag {tag})" if tag else "")
    return "open", f"{email} is still not in the CTT registry"


def check_listed(
    item: dict,
    names: dict[str, set[str]],
    field_tags: dict[tuple[str, str], set[str]] | None = None,
    tags: set[str] | None = None,
) -> tuple[str, str]:
    """TAG-01/TAG-04: the object no longer exists under that name. For CTT-TAG-01 a playbook, script
    or job also passes when its Tags field carries one of the owner's tags: then the name needs no
    prefix. field_tags: (kind, name) -> Tags field."""
    kind = LISTED_KINDS[item["kind"]]
    if item["name"] not in names.get(kind, set()):
        return "fixed", f"{what(item)} no longer exists under that name (renamed or deleted)"
    if item["guideline"] == "CTT-TAG-01" and kind in TAGGED_KINDS and field_tags is not None:
        mine = (field_tags.get((kind, item["name"])) or set()) & (tags or set())
        if mine:
            return "fixed", f"{what(item)} carries your tag {', '.join(sorted(mine))} in its Tags field"
        return "open", f"{what(item)} still exists under that name, without one of your tags in its Tags field"
    return "open", f"{what(item)} still exists under that name"


def check_builtin(item: dict, found: dict | None, tags: set[str]) -> tuple[str, str]:
    """OOTB-01: a built-in playbook or script is re-attached to its pack, or a custom object now
    carries one of the owner's tags, or the object is gone."""
    if not found:
        return "fixed", f"{what(item)} no longer exists"
    pack = found.get("packID") or ""
    if pack or found.get("system"):
        if found.get("detached"):
            return "open", f"{what(item)} is still detached from its pack {pack}".rstrip()
        return "fixed", f"{what(item)} is attached to its pack {pack} again".replace("  ", " ")
    tag = TAG_RE.match(item["name"])
    if tag and tag.group(1).lower() in tags:
        return "fixed", f"{what(item)} now carries your tag"
    return "open", f"{what(item)} is still untagged custom content"


def check_policy(item: dict, row: dict | None, tags: set[str]) -> tuple[str, str]:
    """TAG-02: the latest scope of the policy rule targets one of the owner's tags, or it was deleted."""
    if not row:
        return "open", f"{what(item)} has no scope change since the issue"
    if row.get("action") == "delete":
        return "fixed", f"{what(item)} was deleted"
    scoped = {t.strip().lower() for t in str(row.get("scope_tags") or "").split(",") if t.strip()}
    if scoped & tags:
        return "fixed", f"{what(item)} now targets tag {', '.join(sorted(scoped & tags))}"
    return "open", f"{what(item)} still targets {row.get('scope_target') or 'no tag'}"


def check_endpoint(item: dict, rows: list[dict]) -> tuple[str, str]:
    """LAB-01, with the rule's own condition: fixed once no current row for the endpoint violates it."""
    if not rows:
        return "fixed", f"{what(item)} no longer reports to the tenant"
    bad = [r for r in rows if str(r.get("violating")) == "1"]
    if not bad:
        ip = next((r.get("lab_ip") for r in rows if r.get("lab_ip")), None)
        return "fixed", f"{what(item)} now has " + (
            f"{ip}, in its owner's lab range" if ip else "no lab address (10.x or 172.16.x)"
        )
    r = bad[0]
    if r.get("range_owner"):
        return "open", f"{what(item)} still has {r.get('lab_ip')}, in the lab range of {r.get('range_owner')}"
    return "open", f"{what(item)} still has {r.get('lab_ip')}, in an unassigned lab range"


def check_item(item: dict, ctx: dict) -> tuple[str, str]:
    gid, kind = item["guideline"], item["kind"]
    if gid == "CTT-GEN-01":
        return check_registry(item, ctx["people"])
    if gid in ("CTT-TAG-01", "CTT-TAG-04") and kind in LISTED_KINDS and item["name"]:
        return check_listed(item, ctx["names"], ctx.get("field_tags"), ctx["tags"](item["owner"]))
    if gid == "CTT-OOTB-01" and kind in BUILTIN_KINDS and item["name"]:
        return check_builtin(item, ctx["builtin"].get((BUILTIN_KINDS[kind], item["name"])), ctx["tags"](item["owner"]))
    if gid == "CTT-TAG-02" and item["name"]:
        return check_policy(item, ctx["policies"].get(item["name"]), ctx["tags"](item["owner"]))
    if gid == "CTT-LAB-01" and item["endpoint"]:
        return check_endpoint(item, ctx["endpoints"].get(item["endpoint"], []))
    if gid in NO_CHECK:
        return "unchecked", f"there is no automatic check for {gid}: {NO_CHECK[gid]}"
    if kind:
        return "unchecked", f"there is no automatic check for {gid} on this object type ({kind})"
    return "unchecked", f"there is no automatic check for this {gid} issue"


# ---------- decisions ----------


def sgt(now_ms: int) -> str:
    return datetime.fromtimestamp(now_ms / 1000, SGT).strftime("%d %b %H:%M SGT")


def decide(item: dict, verdict: str, text: str, mode: str, now_ms: int) -> dict:
    """What to do with one issue. mode: check (job), confirm (owner pressed Mark as Fixed) or
    false_positive (owner pressed Mark as False Positive). Every close carries a note saying why."""
    owner = item["owner"] or "the owner"
    if mode == "false_positive":
        return {
            "action": "resolve",
            "reason": FALSE_POSITIVE_REASON,
            "note": f"Marked as false positive by {owner} on {sgt(now_ms)}.",
        }
    if mode == "confirm":
        if verdict == "fixed":
            return {
                "action": "resolve",
                "reason": FIXED_REASON,
                "note": f"Confirmed fixed by {owner} and verified: {text} ({sgt(now_ms)}).",
            }
        if verdict == "unchecked":
            return {"action": "resolve", "reason": FIXED_REASON, "note": f"Confirmed fixed by {owner} on {sgt(now_ms)} ({text})."}
        return {
            "action": "keep",
            "note": (
                f"You said this is fixed, but the check still sees it: {text}. Fix it, then press Mark as Fixed again; "
                "it also closes by itself within an hour once it is fixed."
            ),
        }
    if verdict == "fixed":
        return {
            "action": "resolve",
            "reason": FIXED_REASON,
            "note": f"Auto-closed by the CTT fix check: {text} (checked {sgt(now_ms)}).",
        }
    return {"action": "none", "note": ""}


def resolution_kind(comment: str) -> str:
    """How a resolved hygiene issue was closed, from the note the fix check or inventory check wrote."""
    c = comment or ""
    if c.startswith("Auto-closed by the CTT fix check"):
        return "auto check"
    if c.startswith("Confirmed fixed by"):
        return "owner confirmed"
    if c.startswith(("Marked as false positive", "Marked not a violation")):
        return "false positive"
    if "inventory check" in c.lower() or "sweep" in c.lower():
        return "inventory check"
    return "manual"


def case_close_note(issues: list[dict]) -> str | None:
    """The close note for a hygiene case once all its issues are resolved (None while one is open).
    It quotes the issues' own close notes, so the case says why too."""
    if not issues or any(str(i.get("status.progress") or "").lower() != "resolved" for i in issues):
        return None
    notes = [f"#{i.get('id')}: {i.get('status.resolution_comment') or 'resolved'}" for i in issues]
    return "All its CTT hygiene issues are resolved. " + " ".join(notes)


def playbook_close(plan: dict) -> dict:
    """What the playbook's closing task needs: closeInvestigation takes any allowed reason, but it
    can't fall back when 'Resolved - Fixed' isn't licensed, so fixes close as 'Resolved - Other'."""
    reason = plan.get("reason") or FALLBACK_REASON
    return {"close": True, "reason": FALLBACK_REASON if reason == FIXED_REASON else reason, "note": plan["note"]}


# ---------- digest ----------


def decide_dm(owner: str, entry: dict, notify: dict, sent_today: int) -> tuple[bool, str]:
    """Whether to DM an owner, following notify.mode, the allowlist and the daily limit (as in
    CTTCaseHousekeeping)."""
    mode = notify.get("mode", "off")
    if not entry or not entry.get("slack_id"):
        return False, "no Slack ID in the registry"
    if mode == "off":
        return False, "DMs are off (notify.mode)"
    if mode == "allowlist" and owner not in {a.lower() for a in notify.get("allowlist") or []}:
        return False, "not on notify.allowlist"
    if mode == "admins_only" and entry.get("role") != "admin":
        return False, "DMs go to CTT admins only"
    if sent_today >= int(notify.get("max_dms_per_owner_per_day", 3)):
        return False, "daily DM limit reached"
    return True, "sent"


def _header(left: str, right: str) -> list[str]:
    inner = WIDTH - 2
    text = f"  {left}"
    text = text + " " * max(1, inner - len(text) - len(right) - 2) + right + "  "
    return ["╭" + "─" * inner + "╮", "│" + text[:inner].ljust(inner) + "│", "╰" + "─" * inner + "╯"]


def _line(item: dict, now_ms: int, server: str, suffix: str = "") -> list[str]:
    days = max(0, (now_ms - item["created"]) // DAY_MS) if item.get("created") else 0
    text = f"• #{item['id']} {item['guideline']} {what(item)}" + (f" ({days}d)" if item.get("created") else "") + suffix
    lines = textwrap.wrap(text, WIDTH, subsequent_indent="  ") or [text]
    return [*lines[:3], *([f"  {server}/issue-view/{item['id']}"] if server else [])]


def build_digest(first_name: str, still_open: list[dict], fixed: list[dict], now_ms: int, server: str, max_items: int = 8) -> str:
    out = [*_header("CTT HYGIENE", "DAILY"), "", f"Hi {first_name or 'there'},"]
    if still_open:
        out += ["", f"STILL OPEN ({len(still_open)})"]
        out += textwrap.wrap(
            "Fix them, then press Mark as Fixed in the issue's DM. Wrong or intended? Press Mark as False Positive.", WIDTH
        )
        for item in still_open[:max_items]:
            out += _line(item, now_ms, server)
        if len(still_open) > max_items:
            out.append(f"• … and {len(still_open) - max_items} more")
    if fixed:
        out += ["", f"CLOSED SINCE YESTERDAY ({len(fixed)})"]
        for item in fixed[:max_items]:
            out += _line({**item, "created": 0}, now_ms, "", f" ({item.get('how', 'closed')})")
    out += ["", "─" * WIDTH, "Checked guidelines close by themselves.", "Questions? Ask in the CTT channel."]
    return "\n".join(out)


# ---------- tenant I/O ----------


def core_post(uri: str, body: dict) -> Any:
    res = demisto.executeCommand("core-api-post", {"uri": uri, "body": json.dumps(body)})
    if is_error(res):
        raise DemistoException(f"core-api-post {uri} failed: {get_error(res)}")
    response = res[0]["Contents"].get("response", {})
    return response.get("reply", response) if isinstance(response, dict) else response


def get_list_json(name: str, default: Any) -> Any:
    res = demisto.executeCommand("getList", {"listName": name})
    if is_error(res) or not res[0].get("Contents") or "Item not found" in str(res[0].get("Contents")):
        return default
    try:
        return json.loads(res[0]["Contents"])
    except ValueError:
        return default


def save_list_json(name: str, data: Any) -> None:
    payload = json.dumps(data)
    if is_error(demisto.executeCommand("setList", {"listName": name, "listData": payload})):
        demisto.executeCommand("createList", {"listName": name, "listData": payload})


def search_issues(filters: list[dict]) -> list[dict]:
    issues: list[dict] = []
    for start in range(0, 3000, PAGE):
        body = {"request_data": {"filters": filters, "search_from": start, "search_to": start + PAGE}}
        page = core_post("/public_api/v1/issue/search", body).get("DATA") or []
        issues.extend(i for i in page if str(i.get("name", "")).startswith(PREFIX))
        if len(page) < PAGE:
            break
    return issues


def open_issues(ids: list[str]) -> list[dict]:
    filters = [
        {"field": "issue_domain", "operator": "in", "value": ["Health"]},
        {"field": "status.progress", "operator": "in", "value": ["New", "In Progress"]},
    ]
    if ids:
        filters.append({"field": "id", "operator": "in", "value": [int(i) for i in ids]})
    return search_issues(filters)


def recently_resolved(since_ms: int) -> list[dict]:
    filters = [
        {"field": "issue_domain", "operator": "in", "value": ["Health"]},
        {"field": "status.progress", "operator": "in", "value": ["Resolved"]},
        {"field": "_insert_time", "operator": "gte", "value": since_ms - 30 * DAY_MS},
    ]
    return [i for i in search_issues(filters) if int(i.get("resolution_status_modified_ts") or 0) >= since_ms]


def listed_names(
    kinds: set[str], errors: list[str], field_tags: dict[tuple[str, str], set[str]] | None = None
) -> dict[str, set[str]]:
    """Names of the custom objects of each kind the open issues need (same sources as the
    inventory check's collect_objects); field_tags gets the Tags field of each playbook, script and
    job, by (kind, name)."""
    names: dict[str, set[str]] = {}

    def tagged(kind: str, rows: list[dict]) -> list[str]:
        if field_tags is not None:
            for r in rows:
                if r.get("name"):
                    field_tags[(kind, r["name"])] = {str(t).strip().lower() for t in r.get("tags") or [] if str(t).strip()}
        return [r.get("name") for r in rows]

    fetch = {
        "Playbook": lambda: tagged(
            "Playbook", core_post("/playbook/search", {"query": "system:F", "size": 5000}).get("playbooks") or []
        ),
        "Script": lambda: tagged(
            "Script", core_post("/automation/search", {"query": "system:F", "size": 5000}).get("scripts") or []
        ),
        "Job": lambda: tagged("Job", core_post("/jobs/search", {"page": 0, "size": 1000}).get("data") or []),
        "Integration instance": lambda: [
            i.get("name") for i in core_post("/settings/integration/search", {"size": 2000}).get("instances") or []
        ],
        "Correlation rule": lambda: [
            r.get("name")
            for r in core_post("/public_api/v1/correlations/get", {"request_data": {"search_from": 0, "search_to": 5000}}).get(
                "objects"
            )
            or []
        ],
        "Dataset": lambda: [
            d.get("Dataset Name")
            for d in core_post("/public_api/v1/xql/get_datasets", {"request_data": {}}) or []
            if isinstance(d, dict)
        ],
    }
    for kind in kinds:
        try:
            names[kind] = {n for n in fetch[kind]() if n}
        except Exception as e:
            errors.append(f"listing {kind}s: {e}")
    return names


def builtin_object(kind: str, name: str) -> dict | None:
    if kind == "Playbook":
        rows = core_post("/playbook/search", {"query": name, "size": 200}).get("playbooks") or []
    else:
        rows = core_post("/automation/search", {"query": name, "size": 200}).get("scripts") or []
    return next((r for r in rows if r.get("name") == name), None)


def quoted(values: list[str]) -> str:
    return ", ".join(json.dumps(v) for v in sorted(set(values)))


def run_xql(query: str, days: int, timeout: int = 300) -> list[dict]:
    qid = core_post(
        "/public_api/v1/xql/start_xql_query",
        {"request_data": {"query": query, "timeframe": {"relativeTime": days * DAY_MS}}},
    )
    deadline = time.time() + timeout
    while True:
        res = core_post(
            "/public_api/v1/xql/get_query_results",
            {"request_data": {"query_id": qid, "pending_flag": True, "limit": 1000, "format": "json"}},
        )
        if res.get("status") == "SUCCESS":
            return (res.get("results") or {}).get("data") or []
        if res.get("status") not in ("PENDING", None) or time.time() > deadline:
            raise DemistoException(f"XQL query {res.get('status') or 'timed out'}")
        time.sleep(5)


def resolve(issue_id: str, reason: str, note: str, state: dict) -> str:
    """Resolve with a close note. 'Resolved - Fixed' depends on the tenant's license (joris 8.15
    rejects it); then 'Resolved - Other' is used, remembered for the rest of the run."""
    if reason == FIXED_REASON and state.get("no_fixed_reason"):
        reason = FALLBACK_REASON
    body = {"status": "Resolved", "status_resolution_reason": reason, "status_resolution_comment": note[:900]}
    try:
        core_post(f"/public_api/v1/issue/{issue_id}", {"request_data": {"update_data": body}})
    except DemistoException as e:
        if reason != FIXED_REASON or "allowed statuses" not in str(e):
            raise
        state["no_fixed_reason"] = True
        body["status_resolution_reason"] = FALLBACK_REASON
        core_post(f"/public_api/v1/issue/{issue_id}", {"request_data": {"update_data": body}})
        reason = FALLBACK_REASON
    return reason


def close_case(case_id: str, note: str, reason: str, state: dict) -> None:
    """Resolve a case with a note. An issue's case stays open when the issue is resolved, so the
    fix check closes it once all its issues are resolved."""
    if reason == FIXED_REASON and state.get("no_fixed_reason"):
        reason = FALLBACK_REASON
    body = {"status_progress": "Resolved", "resolve_reason": reason, "resolve_comment": note[:900]}
    try:
        core_post(f"/public_api/v1/case/update/{case_id}", {"request_data": {"update_data": body}})
    except DemistoException:
        if reason == FALLBACK_REASON:
            raise
        body["resolve_reason"] = FALLBACK_REASON
        core_post(f"/public_api/v1/case/update/{case_id}", {"request_data": {"update_data": body}})


def issues_by_ids(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    body = {"request_data": {"filters": [{"field": "id", "operator": "in", "value": [int(i) for i in ids]}], "search_to": 100}}
    return core_post("/public_api/v1/issue/search", body).get("DATA") or []


def close_finished_cases(case_ids: list[str], reason: str, state: dict, errors: list[str]) -> list[str]:
    """Close the given cases whose issues are all resolved; returns the closed case IDs."""
    closed = []
    if not case_ids:
        return closed
    try:
        body = {
            "request_data": {
                "filters": [{"field": "case_id", "operator": "in", "value": [int(c) for c in case_ids]}],
                "search_to": 100,
            }
        }
        cases = core_post("/public_api/v1/case/search", body).get("DATA") or []
    except Exception as e:
        errors.append(f"reading cases {case_ids}: {e}")
        return closed
    for case in cases:
        if str(case.get("status_progress") or "").lower() == "resolved":
            continue
        try:
            note = case_close_note(issues_by_ids([str(i) for i in case.get("issue_ids") or []]))
            if note:
                close_case(str(case.get("case_id")), note, reason, state)
                closed.append(str(case.get("case_id")))
        except Exception as e:
            errors.append(f"closing case {case.get('case_id')}: {e}")
    return closed


def open_hygiene_case_ids() -> list[str]:
    filters = [
        {"field": "status_progress", "operator": "nin", "value": ["Resolved"]},
        {"field": "case_domain", "operator": "in", "value": ["Health"]},
    ]
    ids: list[str] = []
    for start in range(0, 2000, PAGE):
        body = {"request_data": {"filters": filters, "search_from": start, "search_to": start + PAGE}}
        page = core_post("/public_api/v1/case/search", body).get("DATA") or []
        ids += [str(c.get("case_id")) for c in page if str(c.get("case_name") or "").startswith(PREFIX)]
        if len(page) < PAGE:
            break
    return ids


def post_channel(text: str, errors: list[str]) -> None:
    res = demisto.executeCommand("CTTSlackPost", {"message": text})
    if is_error(res):
        errors.append(f"CTTSlackPost: {get_error(res)}")


def send_digest(owner: str, entry: dict, content: str) -> None:
    res = demisto.executeCommand(
        "CTTHygieneSendDM", {"slack_user_id": entry["slack_id"], "owner_email": owner, "content": content}
    )
    if is_error(res):
        raise DemistoException(get_error(res))


# ---------- main ----------


def build_context(items: list[dict], registry: list[dict], errors: list[str]) -> dict:
    ctx: dict[str, Any] = {
        "people": registry_people(registry),
        "names": {},
        "field_tags": {},
        "builtin": {},
        "policies": {},
        "endpoints": {},
    }
    tag_cache: dict[str, set[str]] = {}
    ctx["tags"] = lambda owner: tag_cache.setdefault(owner, owner_tags(registry, owner))
    listed = {
        LISTED_KINDS[i["kind"]] for i in items if i["guideline"] in ("CTT-TAG-01", "CTT-TAG-04") and i["kind"] in LISTED_KINDS
    }
    if listed:
        ctx["names"] = listed_names(listed, errors, ctx["field_tags"])
    for i in items:
        if i["guideline"] == "CTT-OOTB-01" and i["kind"] in BUILTIN_KINDS and i["name"]:
            key = (BUILTIN_KINDS[i["kind"]], i["name"])
            try:
                ctx["builtin"][key] = builtin_object(*key)
            except Exception as e:
                errors.append(f"looking up {i['name']}: {e}")
    policies = [i["name"] for i in items if i["guideline"] == "CTT-TAG-02" and i["name"]]
    if policies:
        try:
            rows = run_xql(FIX_POLICY_QUERY.replace('"__NAMES__"', quoted(policies)), days=90)
            ctx["policies"] = {r.get("object_name"): r for r in rows}
        except Exception as e:
            errors.append(f"policy scope query: {e}")
    endpoints = [i["endpoint"] for i in items if i["guideline"] == "CTT-LAB-01" and i["endpoint"]]
    if endpoints:
        try:
            for r in run_xql(FIX_ENDPOINT_QUERY.replace('"__NAMES__"', quoted(endpoints)), days=30):
                ctx["endpoints"].setdefault(r.get("endpoint_name"), []).append(r)
        except Exception as e:
            errors.append(f"endpoint query: {e}")
    return ctx


def main():  # pragma: no cover
    args = demisto.args()
    try:
        now_ms = int(time.time() * 1000)
        dry_run = argToBoolean(args.get("dry_run") or "false")
        watch = argToBoolean(args.get("watch") or "false")
        # In the Notify Owner playbook the script only decides; the playbook closes the issue in its
        # last task. The job (resolve=true) closes issues that have no running playbook.
        resolve_now = argToBoolean(args.get("resolve") or "true") and not watch
        mode = (
            "false_positive"
            if argToBoolean(args.get("false_positive") or "false")
            else ("confirm" if argToBoolean(args.get("confirm") or "false") else "check")
        )
        ids = [i.strip() for i in str(args.get("issue_id") or "").split(",") if i.strip()]
        owner_filter = str(args.get("owner") or "").strip().lower()
        if (mode != "check" or watch) and not ids and not owner_filter:
            raise DemistoException("confirm, false_positive and watch need issue_id (or owner).")
        cfg = get_list_json(CONFIG_LIST, {})
        registry = get_list_json(cfg.get("registry", {}).get("output_list", "CTT - Registry"), [])
        errors: list[str] = []
        items = [i for i in (parse_issue(x) for x in open_issues(ids)) if i]
        if owner_filter:
            items = [i for i in items if i["owner"] == owner_filter]
        if args.get("guideline"):
            items = [i for i in items if i["guideline"] == str(args["guideline"]).upper()]
        ctx = build_context(items, registry, errors) if mode != "false_positive" else {}
        run_state: dict[str, Any] = {}
        results = []
        for item in items:
            verdict, text = check_item(item, ctx) if mode != "false_positive" else ("unchecked", "")
            plan = decide(item, verdict, text, mode, now_ms)
            row = {
                "issue_id": item["id"],
                "guideline": item["guideline"],
                "owner": item["owner"],
                "object": what(item),
                "verdict": verdict,
                "evidence": text,
                "action": plan["action"],
                "note": plan["note"],
                "resolved": False,
                "close": False,
            }
            if plan["action"] == "resolve" and mode == "false_positive" and not dry_run:
                post_channel(
                    f"CTT hygiene: {item['owner'] or 'the owner'} marked issue #{item['id']} ({item['guideline']}, "
                    f"{what(item)}) as a false positive. CTT admins: check whether the rule needs tuning.",
                    errors,
                )
            if plan["action"] == "resolve" and not resolve_now:
                row.update(playbook_close(plan))
            elif plan["action"] == "resolve" and mode == "check" and item["playbook"] in ACTIVE_PLAYBOOK:
                row["action"] = "left to its playbook"
            elif plan["action"] == "resolve" and not dry_run:
                try:
                    row["reason"] = resolve(item["id"], plan["reason"], plan["note"], run_state)
                    row["resolved"] = True
                    row["cases_closed"] = close_finished_cases(item["cases"], row["reason"], run_state, errors)
                except Exception as e:
                    errors.append(f"resolving #{item['id']}: {e}")
            results.append(row)

        swept: list[str] = []
        if mode == "check" and resolve_now and not ids and not owner_filter and not dry_run:
            # Hygiene cases stay open when their issue is resolved (by a playbook, this check, the
            # inventory check or a person); close the ones whose issues are all resolved.
            try:
                swept = close_finished_cases(open_hygiene_case_ids(), FALLBACK_REASON, run_state, errors)
            except Exception as e:
                errors.append(f"open hygiene cases: {e}")

        digests = []
        if argToBoolean(args.get("remind") or "false"):
            digests = remind(items, results, registry, cfg, now_ms, dry_run, errors)

        resolved = [r for r in results if r["resolved"] or (dry_run and r["action"] == "resolve")]
        md = tableToMarkdown(
            f"CTT fix check ({'watch' if watch else mode}{', dry run' if dry_run else ''}): {len(items)} issue(s), "
            f"{len(resolved)} {'would be ' if dry_run else ''}resolved",
            results,
            headers=["issue_id", "guideline", "owner", "object", "verdict", "action", "evidence"],
        )
        closed_cases = sorted({c for r in results for c in r.get("cases_closed") or []} | set(swept))
        if closed_cases:
            md += f"\nClosed cases whose hygiene issues are all resolved: {', '.join(closed_cases)}\n"
        if digests:
            md += "\n" + tableToMarkdown("Daily digests", digests, headers=["owner", "open", "closed", "sent"])
        if errors:
            md += "\n**Errors**\n" + "\n".join(f"- {e}" for e in errors)
        scheduled = None
        if watch and results and results[0]["verdict"] == "open":
            # Polling: run again in an hour until the check sees it fixed (or the issue closes).
            md += f"\nStill open; checking again in {WATCH_SECONDS // 60} minutes."
            scheduled = ScheduledCommand(
                command="CTTHygieneFixCheck",
                next_run_in_seconds=WATCH_SECONDS,
                args={"issue_id": ids[0] if ids else results[0]["issue_id"], "watch": "true"},
                timeout_in_seconds=WATCH_TIMEOUT,
            )
        return_results(
            CommandResults(
                readable_output=md,
                # The watch branch runs next to the question rounds; its own key keeps their
                # results apart.
                outputs_prefix="CTT.FixWatch" if watch else "CTT.FixCheck",
                outputs_key_field="issue_id",
                # One object for one issue, so the playbook's conditions read booleans rather than
                # one-item lists.
                outputs=None if scheduled else (results[0] if len(results) == 1 else results),
                scheduled_command=scheduled,
            )
        )
    except Exception as e:
        return_error(f"CTTHygieneFixCheck: {e}")


def remind(  # pragma: no cover
    items: list[dict], results: list[dict], registry: list[dict], cfg: dict, now_ms: int, dry_run: bool, errors: list[str]
) -> list[dict]:
    """One digest DM per owner with their open issues older than a day and what closed since
    yesterday; at most once per owner per day."""
    closed_now = {r["issue_id"] for r in results if r["resolved"]}
    still = [i for i in items if i["id"] not in closed_now and i["owner"] and now_ms - i["created"] >= DAY_MS]
    fixed: list[dict] = []
    try:
        for issue in recently_resolved(now_ms - DAY_MS):
            item = parse_issue(issue)
            if item and item["owner"]:
                fixed.append({**item, "how": resolution_kind(str(issue.get("status.resolution_comment") or ""))})
    except Exception as e:
        errors.append(f"recently resolved issues: {e}")
    people = registry_people(registry)
    notify = cfg.get("notify", {})
    state = get_list_json(STATE_LIST, {})
    sent_state = get_list_json(NOTIFY_STATE, {})
    day = datetime.fromtimestamp(now_ms / 1000, UTC).strftime("%Y-%m-%d")
    reminded = state.get("reminded", {}) if isinstance(state, dict) else {}
    server = ((demisto.demistoUrls() or {}).get("server") or "").rstrip("/")
    rows = []
    for owner in sorted({i["owner"] for i in still}):
        mine = sorted((i for i in still if i["owner"] == owner), key=lambda i: i["created"])
        done = [f for f in fixed if f["owner"] == owner]
        entry = people.get(owner, {})
        if reminded.get(owner) == day:
            rows.append({"owner": owner, "open": len(mine), "closed": len(done), "sent": "already today"})
            continue
        ok, why = decide_dm(owner, entry, notify, int((sent_state.get(day) or {}).get(owner, 0)))
        first = (entry.get("owner_name") or owner.split("@")[0]).split()[0]
        content = build_digest(first, mine, done, now_ms, server)
        if ok and not dry_run:
            try:
                send_digest(owner, entry, content)
                reminded[owner] = day
            except Exception as e:
                why = f"failed: {e}"
        rows.append(
            {"owner": owner, "open": len(mine), "closed": len(done), "sent": why if not dry_run or not ok else "would send"}
        )
    if not dry_run:
        save_list_json(STATE_LIST, {"reminded": {k: v for k, v in reminded.items() if v == day}})
    return rows


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
