import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import hashlib
import json
import re
import time
from typing import Any

CONFIG_LIST = "CTT - Config"
# Kept from the daily sweep this check replaces, so issues it raised are not raised again.
STATE_LIST = "CTT - Sweep State"
OWNERS_DATASET = "ctt_object_owners"
TAG_RE = re.compile(r"^\s*([A-Za-z0-9]{2,16})\s*[-_]")
ISSUE_PREFIX = "CTT - Hygiene"
TITLES = {
    "CTT-TAG-01": "Objects without a registered owner tag",
    "CTT-TAG-02": "Owner tag missing from a tag field or policy scope",
    "CTT-LIFE-02": "Objects owned by an inactive DC",
    "CTT-LAB-02": "Endpoints without an owner tag",
}
# Kinds with a Tags field: a registered tag there replaces the name prefix (CTT-TAG-01).
TAGGED_KINDS = ("Playbook", "Script", "Job")
# Inventory kinds and the object kinds the owner index (audit log) uses for them.
INDEX_KINDS = {
    "Playbook": ("Playbook",),
    "Script": ("Script", "Automation"),
    "Job": ("Job", "JobCenter"),
    "Integration instance": ("Integrations", "Integration"),
    "Correlation rule": ("Correlation rule",),
    "Lookup dataset": ("Lookup dataset", "Dataset"),
    "Data collector": ("Data collector",),
    "Policy profile": ("Policy profile",),
    "Policy rule": ("Policy rule",),
}
# Platform objects that exist on every tenant under a fixed name: other code loads the user hook
# scripts by name, and testmodule is the platform's own instance (no integration behind it).
PLATFORM_SCRIPTS = {"CommonServerUserPython", "CommonServerUserPowerShell", "CommonUserServer"}
PLATFORM_INSTANCE_BRANDS = {"testmodule"}
COLLECTOR_DAYS = 365
ENDPOINT_DAYS = 30

# BEGIN GENERATED INVENTORY_COLLECTOR_QUERY (tools/correlation_rules/gen_correlation_rules.py; do not edit)
INVENTORY_COLLECTOR_QUERY = (
    "dataset = management_auditing\n"
    "| filter management_auditing_result = ENUM.MANAGEMENT_AUDIT_SUCCESS\n"
    '| filter email != null and email != "" and email not in ("Palo Alto Networks", "N/A", "Xpanse Develo'
    'pment", "Cortex Automation")\n'
    '| filter user_name = null or user_name !~= "^(Public API - [0-9]+|APIKeyUser_[0-9]+|XSIAM Automation'
    '|Cortex Automation)$"\n'
    '| filter coalesce(description, "") !~= "(was auto-provisioned \\(JIT\\) via SSO|via SSO group claim)"\n'
    '| alter actor_email = if(email contains "@", replex(lowercase(email), "@asean\\.ctt$", "@paloaltonetw'
    'orks.com"), null), actor_name = lowercase(user_name)\n'
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
    '| filter object_kind = "Data collector" and object_name != null and object_name != ""\n'
    '| alter is_create = if(action = "create", 1, 0)\n'
    "| comp count() as events, max(is_create) as has_create, earliest(actor) as creator by object_name\n"
    "| filter events = 1 and has_create = 1\n"
    "| fields object_name, creator"
)
# END GENERATED INVENTORY_COLLECTOR_QUERY

# BEGIN GENERATED INVENTORY_POLICY_NAMES_QUERY (tools/correlation_rules/gen_correlation_rules.py; do not edit)
INVENTORY_POLICY_NAMES_QUERY = (
    "dataset = endpoints\n"
    "| dedup endpoint_id by desc last_seen\n"
    "| filter endpoint_status != ENUM.UNINSTALLED\n"
    '| alter policy_names = arraycreate(coalesce(assigned_prevention_policy, ""), coalesce(assigned_exten'
    'sions_policy, ""))\n'
    "| arrayexpand policy_names\n"
    '| filter policy_names != "" and policy_names !~= "^[A-Za-z]+ Default$"\n'
    "| comp count() as endpoints by policy_names\n"
    "| fields policy_names, endpoints"
)
# END GENERATED INVENTORY_POLICY_NAMES_QUERY

# BEGIN GENERATED INVENTORY_POLICY_SCOPE_QUERY (tools/correlation_rules/gen_correlation_rules.py; do not edit)
INVENTORY_POLICY_SCOPE_QUERY = (
    "dataset = management_auditing\n"
    "| filter management_auditing_result = ENUM.MANAGEMENT_AUDIT_SUCCESS\n"
    '| filter email != null and email != "" and email not in ("Palo Alto Networks", "N/A", "Xpanse Develo'
    'pment", "Cortex Automation")\n'
    '| filter user_name = null or user_name !~= "^(Public API - [0-9]+|APIKeyUser_[0-9]+|XSIAM Automation'
    '|Cortex Automation)$"\n'
    '| filter coalesce(description, "") !~= "(was auto-provisioned \\(JIT\\) via SSO|via SSO group claim)"\n'
    '| alter actor_email = if(email contains "@", replex(lowercase(email), "@asean\\.ctt$", "@paloaltonetw'
    'orks.com"), null), actor_name = lowercase(user_name)\n'
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
# END GENERATED INVENTORY_POLICY_SCOPE_QUERY

# BEGIN GENERATED INVENTORY_ENDPOINT_QUERY (tools/correlation_rules/gen_correlation_rules.py; do not edit)
INVENTORY_ENDPOINT_QUERY = (
    "dataset = endpoints\n"
    "| dedup endpoint_id by desc last_seen\n"
    "| filter endpoint_status != ENUM.UNINSTALLED\n"
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
    "| filter tag_owner = null\n"
    "| fields endpoint_name, owner, owner_source"
)
# END GENERATED INVENTORY_ENDPOINT_QUERY
QUOTED_RE = re.compile(r"'([^']+)'")
DAY_MS = 86_400_000
PAGE = 100  # the public API refuses search sizes above 100


# ---------- pure helpers (unit tested) ----------


# CTT SSO accounts (<user>@asean.ctt) are the same people as <user>@paloaltonetworks.com, the email in
# the CTT registry. Every email from the tenant goes through canonical_email before a registry lookup.
SSO_DOMAIN, HOME_DOMAIN = "@asean.ctt", "@paloaltonetworks.com"


def canonical_email(email) -> str:
    """The registry email for a sign-in email: <user>@asean.ctt (CTT SSO) is <user>@paloaltonetworks.com."""
    e = str(email or "").strip().lower()
    return e[: -len(SSO_DOMAIN)] + HOME_DOMAIN if e.endswith(SSO_DOMAIN) else e


def parse_tag(name: str) -> str | None:
    m = TAG_RE.match(name or "")
    return m.group(1).lower() if m else None


SYSTEM_CREATORS = {"dbot@demisto.com", "dbot", "palo alto networks", "n/a"}


def normalize_creator(creator: str | None) -> str:
    c = canonical_email(creator)
    return "unknown" if not c or c in SYSTEM_CREATORS else c


def registry_index(rows: list[dict]) -> dict[str, dict]:
    return {str(r.get("tag", "")).lower(): r for r in rows if r.get("tag")}


def owner_index(rows: list[dict]) -> dict[tuple[str, str], str]:
    """(object kind, lower-case name) -> the person who last changed it, else who created it."""
    out: dict[tuple[str, str], str] = {}
    for r in rows:
        person = normalize_creator(r.get("last_editor") or r.get("creator"))
        if person != "unknown" and r.get("object_name"):
            out[(str(r.get("object_kind")), str(r["object_name"]).lower())] = person
    return out


def find_owner(obj: dict, owners: dict[tuple[str, str], str]) -> str:
    """Who to hold responsible for an untagged object: its creator from the API when that is a
    person, else whoever last changed it according to the audit log ("Updated By")."""
    creator = normalize_creator(obj.get("creator"))
    if creator != "unknown":
        return creator
    name = str(obj.get("name") or "").lower()
    for kind in INDEX_KINDS.get(obj.get("kind", ""), (obj.get("kind", ""),)):
        if (kind, name) in owners:
            return owners[(kind, name)]
    return "unknown"


def reported_names(issues: list[dict]) -> set[str]:
    """Object names already quoted in an open hygiene issue raised by a correlation rule, so the
    inventory check does not raise a second issue for the same object."""
    names: set[str] = set()
    for issue in issues:
        if not str(issue.get("name", "")).startswith(ISSUE_PREFIX + " - "):
            continue
        desc = str(issue.get("description") or "")
        if desc.startswith(("Daily sweep found", "The inventory check found")):
            continue
        names.update(n.lower() for n in QUOTED_RE.findall(desc))
    return names


def object_tag(obj: dict, registry: dict[str, dict]) -> tuple[str | None, dict | None]:
    """The registered tag an object carries: its name prefix, or for a playbook, script or job a
    registered tag in its Tags field (CTT-TAG-01: an object tagged there needs no name prefix)."""
    tag = parse_tag(obj.get("name") or "")
    if tag in registry:
        return tag, registry[tag]
    if obj.get("kind") in TAGGED_KINDS:
        field = sorted(str(t).strip().lower() for t in obj.get("tags") or [])
        found = next((t for t in field if t in registry), None)
        if found:
            return found, registry[found]
    return tag, None


def check_object(obj: dict, registry: dict[str, dict], owners: dict | None = None) -> list[dict]:
    """obj: kind, name, creator (email or ''), tags (Tags field of playbooks, scripts, jobs); a policy
    rule also carries its latest scope (scope_target, scope_tags), an endpoint its owner and
    owner_source (endpoints only come here without a registered tag). Returns findings."""
    name = obj.get("name") or ""
    base = {"kind": obj["kind"], "name": name}
    if obj["kind"] == "Endpoint":
        owner = normalize_creator(obj.get("creator")) or "unknown"
        detail = "no registered endpoint or server tag"
        if owner != "unknown" and obj.get("owner_source"):
            detail += f"; owner: {obj['owner_source']}"
        return [{**base, "guideline": "CTT-LAB-02", "owner": owner, "detail": detail}]
    tag, entry = object_tag(obj, registry)
    if not entry:
        detail = "no tag prefix" if not tag else f"prefix '{tag}' is not a registered tag"
        owner = find_owner(obj, owners or {})
        return [{**base, "guideline": "CTT-TAG-01", "owner": owner, "detail": detail}] + scope_findings(obj, registry, owner)
    findings = []
    owner = entry.get("owner_email") or "central"
    findings.extend(scope_findings(obj, registry, owner))
    if entry.get("active") == "false":
        findings.append({**base, "guideline": "CTT-LIFE-02", "owner": owner, "detail": f"tag '{tag}' belongs to an inactive DC"})
    if obj["kind"] == "Playbook" and entry.get("role") != "central":
        owner_tags = {t for t, r in registry.items() if r.get("owner_email") == entry.get("owner_email")}
        if not {str(t).lower() for t in (obj.get("tags") or [])} & owner_tags:
            findings.append(
                {**base, "guideline": "CTT-TAG-02", "owner": owner, "detail": f"Tags field lacks the owner's tag ({tag})"}
            )
    return findings


def scope_findings(obj: dict, registry: dict[str, dict], owner: str) -> list[dict]:
    """CTT-TAG-02 for a policy rule: its latest scope must target one of its owner's tags, not
    endpoint names, Any or someone else's tags. No finding without a known scope, or for central ones."""
    target = str(obj.get("scope_target") or "").strip()
    if obj.get("kind") != "Policy rule" or not target or owner == "central":
        return []
    mine = {t for t, r in registry.items() if r.get("owner_email") == owner}
    scoped = {t.strip().lower() for t in str(obj.get("scope_tags") or "").split(",") if t.strip()}
    if scoped & mine:
        return []
    if scoped:
        detail = f"its scope targets tag {', '.join(sorted(scoped))}, not one of the owner's tags"
    else:
        detail = f"its scope targets {target}, not one of the owner's tags"
    return [{"kind": obj["kind"], "name": obj.get("name") or "", "guideline": "CTT-TAG-02", "owner": owner, "detail": detail}]


def inventory_entry(obj: dict, registry: dict[str, dict], owners: dict | None = None) -> dict:
    tag, entry = object_tag(obj, registry)
    owner = (entry.get("owner_email") or "central") if entry else find_owner(obj, owners or {})
    return {"kind": obj["kind"], "name": obj.get("name") or "", "tag": tag if entry else None, "owner": owner}


def item_key(f: dict) -> str:
    """Stable identity of a finding (kind and name only), so details that change daily (a case's
    idle days) don't count as a change. Short, to keep the state list small."""
    return hashlib.sha256(f"{f['kind']}|{f['name']}".encode()).hexdigest()[:8]


def group_findings(findings: list[dict]) -> dict[str, dict]:
    groups: dict[str, dict] = {}
    for f in findings:
        key = f"{f['guideline']}|{f['owner']}"
        g = groups.setdefault(key, {"guideline": f["guideline"], "owner": f["owner"], "items": [], "keys": set()})
        g["items"].append(f"{f['kind']} '{f['name']}': {f['detail']}")
        g["keys"].add(item_key(f))
    for g in groups.values():
        g["items"] = sorted(set(g["items"]))
        g["keys"] = sorted(g["keys"])
        g["fingerprint"] = hashlib.sha256("".join(g["keys"]).encode()).hexdigest()[:16]
    return groups


def plan(groups: dict[str, dict], state: dict[str, dict]) -> tuple[list[str], list[str], list[str]]:
    """Returns (keys to raise, keys whose open issue to resolve, keys to update quietly).

    A group raises once and keeps its issue while it only shrinks (things got fixed). It raises a
    replacement only when new items appear, and its issue is resolved once the group is empty.
    That keeps a busy tenant from opening a new Health case every day."""
    raise_keys, resolve_keys, update_keys = [], [], []
    for key, group in groups.items():
        prev = state.get(key)
        if not prev:
            raise_keys.append(key)
        elif prev.get("fingerprint") != group["fingerprint"]:
            if set(group["keys"]) - set(prev.get("keys") or []):
                raise_keys.append(key)
                resolve_keys.append(key)
            else:
                update_keys.append(key)
    resolve_keys += [k for k in state if k not in groups]
    return sorted(raise_keys), sorted(resolve_keys), sorted(update_keys)


def issue_body(group: dict, now_ms: int, max_items: int = 60) -> dict:
    gid = group["guideline"]
    items = group["items"]
    lines = "\n".join(f"- {i}" for i in items[:max_items])
    more = f"\n- ... and {len(items) - max_items} more" if len(items) > max_items else ""
    return {
        "request_data": {
            "issue": {
                "name": f"{ISSUE_PREFIX} - {gid} - {TITLES[gid]} ({group['owner']})",
                "description": f"The inventory check found {len(items)} item(s) for owner {group['owner']} "
                f"that break guideline {gid}. See CTT-Guidelines.\n{lines}{more}\n[owner: {group['owner']}]",
                "observation_time": now_ms,
                "issue_domain": "Health",
                "category": "CTT Hygiene",
                "type": "Unclassified",
                "severity": "MEDIUM",
                "remediation": f"Fix the items listed, following guideline {gid} in CTT-Guidelines.",
            }
        }
    }


# ---------- tenant I/O ----------


def _contents(res: list) -> Any:
    if is_error(res):
        raise DemistoException(get_error(res))
    response = res[0]["Contents"].get("response", {})
    return response.get("reply", response) if isinstance(response, dict) else response


def core_post(uri: str, body: dict) -> Any:
    return _contents(demisto.executeCommand("core-api-post", {"uri": uri, "body": json.dumps(body)}))


def core_get(uri: str) -> Any:
    return _contents(demisto.executeCommand("core-api-get", {"uri": uri}))


def get_list_json(name: str, default: Any) -> Any:
    res = demisto.executeCommand("getList", {"listName": name})
    if is_error(res) or not res[0].get("Contents") or "Item not found" in str(res[0].get("Contents")):
        return default
    try:
        return json.loads(res[0]["Contents"])
    except ValueError:
        return default


def save_list_json(name: str, data: Any) -> None:
    payload = json.dumps(data, indent=1)
    res = demisto.executeCommand("setList", {"listName": name, "listData": payload})
    if is_error(res):
        demisto.executeCommand("createList", {"listName": name, "listData": payload})


def collect_objects(errors: list[str]) -> list[dict]:
    objects: list[dict] = []

    def attempt(label: str, fn):
        try:
            objects.extend(fn())
        except Exception as e:
            errors.append(f"{label}: {e}")

    def playbooks():
        res = core_post("/playbook/search", {"query": "system:F", "size": 2000})
        return [
            {
                "kind": "Playbook",
                "name": p.get("name"),
                "creator": (p.get("OWNER") or {}).get("id", ""),
                "tags": p.get("tags") or [],
            }
            for p in res.get("playbooks") or []
            if not p.get("packID") and not p.get("system")
        ]

    def scripts():
        res = core_post("/automation/search", {"query": "system:F", "size": 2000})
        return [
            {"kind": "Script", "name": s.get("name"), "creator": s.get("user", ""), "tags": s.get("tags") or []}
            for s in res.get("scripts") or []
            if not s.get("packID") and not s.get("system") and s.get("name") not in PLATFORM_SCRIPTS
        ]

    def jobs():
        res = core_post("/jobs/search", {"page": 0, "size": 500})
        return [
            {"kind": "Job", "name": j.get("name"), "creator": j.get("owner", ""), "tags": j.get("tags") or []}
            for j in res.get("data") or []
        ]

    def instances():
        res = core_post("/settings/integration/search", {"size": 1000})
        return [
            {"kind": "Integration instance", "name": i.get("name"), "creator": ""}
            for i in res.get("instances") or []
            if not i.get("isBuiltin") and not i.get("packID") and i.get("brand") not in PLATFORM_INSTANCE_BRANDS
        ]

    def collectors():
        rows = run_xql(INVENTORY_COLLECTOR_QUERY, COLLECTOR_DAYS)
        return [{"kind": "Data collector", "name": r.get("object_name"), "creator": r.get("creator") or ""} for r in rows]

    def profiles():
        seen: dict[str, dict] = {}
        for ptype in ("prevention", "extension"):
            for p in core_post("/public_api/v1/endpoints/get_profiles", {"request_data": {"type": ptype}}) or []:
                name = p.get("PROFILE_NAME") if isinstance(p, dict) else None
                if not name or p.get("PROFILE_IS_DEFAULT") or "@" not in str(p.get("PROFILE_CREATED_BY") or ""):
                    continue
                seen.setdefault(name, {"kind": "Policy profile", "name": name, "creator": p.get("PROFILE_CREATED_BY")})
        return list(seen.values())

    def policy_rules():
        """Policies in use (no API lists policy rules) with their latest scope from the audit log."""
        names = sorted(
            {str(r.get("policy_names")) for r in run_xql(INVENTORY_POLICY_NAMES_QUERY, ENDPOINT_DAYS) if r.get("policy_names")}
        )
        if not names:
            return []
        query = INVENTORY_POLICY_SCOPE_QUERY.replace('"__NAMES__"', ", ".join(json.dumps(n) for n in names))
        scopes = {r.get("object_name"): r for r in run_xql(query, COLLECTOR_DAYS)}
        objs = []
        for name in names:
            row = scopes.get(name) or {}
            live = row.get("action") != "delete"
            objs.append(
                {
                    "kind": "Policy rule",
                    "name": name,
                    "creator": "",
                    "scope_target": row.get("scope_target") if live else None,
                    "scope_tags": row.get("scope_tags") if live else None,
                }
            )
        return objs

    def endpoints():
        rows = run_xql(INVENTORY_ENDPOINT_QUERY, ENDPOINT_DAYS)
        return [
            {
                "kind": "Endpoint",
                "name": r.get("endpoint_name"),
                "creator": r.get("owner") or "",
                "owner_source": r.get("owner_source"),
            }
            for r in rows
            if r.get("endpoint_name")
        ]

    def correlation_rules():
        rows: list[dict] = []
        for start in range(0, 2000, PAGE):
            res = core_post(
                "/public_api/v1/correlations/get", {"request_data": {"search_from": start, "search_to": start + PAGE}}
            )
            page = res.get("objects", []) if isinstance(res, dict) else []
            rows.extend(page)
            if len(page) < PAGE:
                break
        return [
            {
                "kind": "Correlation rule",
                "name": r.get("name"),
                "creator": r.get("created_by") if "@" in str(r.get("created_by")) else "",
            }
            for r in rows
        ]

    def lookups():
        res = core_post("/public_api/v1/xql/get_datasets", {"request_data": {}})
        return [
            {"kind": "Lookup dataset", "name": d.get("Dataset Name"), "creator": ""}
            for d in res or []
            if isinstance(d, dict) and str(d.get("Type", "")).upper() == "LOOKUP"
        ]

    for label, fn in [
        ("playbooks", playbooks),
        ("scripts", scripts),
        ("jobs", jobs),
        ("integration instances", instances),
        ("correlation rules", correlation_rules),
        ("lookups", lookups),
        ("data collectors", collectors),
        ("policy profiles", profiles),
        ("policy rules", policy_rules),
        ("endpoints", endpoints),
    ]:
        attempt(label, fn)
    return objects


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


def read_owner_index() -> dict[tuple[str, str], str]:
    res = core_post("/public_api/v1/xql/lookups/get_data", {"request_data": {"dataset_name": OWNERS_DATASET, "limit": 10000}})
    rows = res.get("data", []) if isinstance(res, dict) else (res or [])
    return owner_index([r for r in rows if isinstance(r, dict)])


def open_hygiene_issues() -> list[dict]:
    filters = [
        {"field": "issue_domain", "operator": "in", "value": ["Health"]},
        {"field": "status.progress", "operator": "in", "value": ["New", "In Progress"]},
    ]
    issues: list[dict] = []
    for start in range(0, 2000, PAGE):
        body = {"request_data": {"filters": filters, "search_from": start, "search_to": start + PAGE}}
        page = core_post("/public_api/v1/issue/search", body).get("DATA") or []
        issues.extend(page)
        if len(page) < PAGE:
            break
    return issues


def create_issue(group: dict, now_ms: int) -> str:
    reply = core_post("/public_api/v1/issue", issue_body(group, now_ms))
    return str((reply or {}).get("external_id") or "")


def resolve_issue(external_id: str, comment: str) -> None:
    if not external_id:
        return
    found = core_post(
        "/public_api/v1/issue/search",
        {"request_data": {"filters": [{"field": "external_id", "operator": "in", "value": [external_id]}]}},
    )
    for issue in (found or {}).get("DATA") or []:
        core_post(
            f"/public_api/v1/issue/{issue.get('id')}",
            {
                "request_data": {
                    "update_data": {
                        "status": "Resolved",
                        "status_resolution_reason": "Resolved - Other",
                        "status_resolution_comment": comment,
                    }
                }
            },
        )


def main():  # pragma: no cover
    try:
        args = demisto.args()
        dry_run = argToBoolean(args.get("dry_run", "false"))
        include_inventory = argToBoolean(args.get("include_inventory", "false"))
        cfg = get_list_json(CONFIG_LIST, {})
        check_cfg = cfg.get("inventory") or cfg.get("sweep", {})
        max_new = int(check_cfg.get("max_new_issues_per_run", 50))
        registry_rows = get_list_json(cfg.get("registry", {}).get("output_list", "CTT - Registry"), [])
        if not registry_rows:
            raise DemistoException("The 'CTT - Registry' list is empty. Run the CTT - Registry Sync job first.")
        registry = registry_index(registry_rows)
        now_ms = int(time.time() * 1000)

        errors: list[str] = []
        owners: dict = {}
        try:
            owners = read_owner_index()
        except Exception as e:
            errors.append(f"owner index ({OWNERS_DATASET}): {e}")
        skip: set[str] = set()
        try:
            skip = reported_names(open_hygiene_issues())
        except Exception as e:
            errors.append(f"open issues: {e}")
        findings: list[dict] = []
        objects = collect_objects(errors)
        for obj in objects:
            if str(obj.get("name") or "").lower() in skip:
                continue
            findings.extend(check_object(obj, registry, owners))
        inventory = [inventory_entry(o, registry, owners) for o in objects] if include_inventory else []

        groups = group_findings(findings)
        state = get_list_json(STATE_LIST, {})
        raise_keys, resolve_keys, update_keys = plan(groups, state)
        raised, resolved = [], []
        if not dry_run:
            for key in resolve_keys:
                try:
                    resolve_issue(state[key].get("external_id", ""), "Superseded or fixed; found by the CTT inventory check.")
                    resolved.append(key)
                except Exception as e:
                    errors.append(f"resolve {key}: {e}")
                state.pop(key, None)
            for key in raise_keys[:max_new]:
                try:
                    ext = create_issue(groups[key], now_ms)
                    state[key] = {
                        "fingerprint": groups[key]["fingerprint"],
                        "external_id": ext,
                        "keys": groups[key]["keys"],
                    }
                    raised.append(key)
                except Exception as e:
                    errors.append(f"raise {key}: {e}")
            for key in update_keys:
                state[key].update(fingerprint=groups[key]["fingerprint"], keys=groups[key]["keys"])
            save_list_json(STATE_LIST, state)

        rows = [
            {"Guideline": g["guideline"], "Owner": g["owner"], "Items": len(g["items"]), "New issue": k in raise_keys}
            for k, g in sorted(groups.items())
        ]
        md = tableToMarkdown(
            f"CTT inventory check{' (dry run)' if dry_run else ''}", rows, headers=["Guideline", "Owner", "Items", "New issue"]
        )
        md += (
            f"\nRaised {len(raised)} issue(s), resolved {len(resolved)}. "
            f"Skipped {len(skip)} object name(s) already in open rule issues."
        )
        if errors:
            md += tableToMarkdown("Collection errors", [{"Error": e} for e in errors])
        return_results(
            CommandResults(
                readable_output=md,
                outputs_prefix="CTT.InventoryCheck",
                outputs={"Findings": findings, "Inventory": inventory, "Raised": raised, "Resolved": resolved, "Errors": errors},
            )
        )
    except Exception as e:
        return_error(f"CTTInventoryCheck failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
