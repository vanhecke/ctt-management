"""Generate the CTTManagement correlation rules from the specs below.

Run from content/:  uv run --with pyyaml python3 tools/correlation_rules/gen_correlation_rules.py
Every rule is a health-domain rule; its issue name carries the guideline ID.
"""

import json
import subprocess
import sys
import uuid
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
CONTENT = HERE.parent.parent
OUT = CONTENT / "Packs" / "CTTManagement" / "CorrelationRules"
LINT = CONTENT.parent / "bin" / "xql-lint"
NS = uuid.UUID("6f1c2d8e-2b7a-4c55-9a0e-c77a11e0c7a1")

EXTRACT = (HERE / "10_extract.xql").read_text().strip()
ACTOR = (HERE / "20_actor_join.xql").read_text().strip()
OBJECT = (HERE / "30_object_join.xql").read_text().strip()
AUDIT = f"{EXTRACT}\n{ACTOR}\n{OBJECT}"

MANAGED_BRANDS = [
    "VirusTotal (API v3)", "SlackV3", "Core REST API", "Cortex Core - Platform", "Cortex Core - IR",
    "Cortex Core - IOC", "XQL Query Engine", "GoogleSheets", "GoogleDrive", "GoogleDocs", "GoogleCalendar",
]
AUDIT_FIELDS = "| fields _time, actor, actor_email, actor_registered, object_kind, object_name, obj_tag, obj_owner, action, subtype, finding, guideline_id, title, description"
AUDIT_LINK = 'dataset = management_auditing | filter email = "$actor_email" or lowercase(user_name) = "$actor" | sort desc _time'

LOGIN_BASE = """dataset = management_auditing
| filter management_auditing_type = ENUM.MANAGEMENT_AUDIT_AUTHENTICATION and subtype in ("Login", "SSO") and management_auditing_result = ENUM.MANAGEMENT_AUDIT_SUCCESS
| filter email contains "@" and email !~= "@crtxtool\\.invalid$"
| alter actor_email = lowercase(email), actor_name = lowercase(user_name)
| comp count() as logins, max(_time) as last_login by actor_email, actor_name"""

ENDPOINT_BASE = """dataset = endpoints
| dedup endpoint_id by desc last_seen
| alter etags = arrayconcat(json_extract_scalar_array(tags, "$.endpoint_tags"), json_extract_scalar_array(tags, "$.server_tags"))
| alter etags = if(etags = null or array_length(etags) = 0, arraycreate("-"), etags)
| alter policy_tag = lowercase(arrayindex(regextract(assigned_prevention_policy, "^\\s*([A-Za-z0-9]{2,16})\\s*[-_]"), 0)), package_tag = lowercase(arrayindex(regextract(installation_package, "^\\s*([A-Za-z0-9]{2,16})\\s*[-_]"), 0))
| alter lab_ip = coalesce(arrayindex(arrayfilter(ip_address, "@element" ~= "^10\\."), 0), arrayindex(arrayfilter(ip_address, "@element" ~= "^172\\.16\\."), 0))
| alter ip_octet = coalesce(arrayindex(regextract(lab_ip, "^10\\.(\\d+)\\."), 0), arrayindex(regextract(lab_ip, "^172\\.16\\.(\\d+)\\."), 0))
| arrayexpand etags
| alter etag = lowercase(etags)
| join type = left (dataset = ctt_registry | filter role != "central" | alter etag = ctt_tag, etag_owner = owner_email | fields etag, etag_owner) as te te.etag = etag
| comp max(etag_owner) as tag_owner by endpoint_id, endpoint_name, lab_ip, ip_octet, policy_tag, package_tag, assigned_prevention_policy, installation_package
| join type = left (dataset = ctt_registry | filter role != "central" | alter policy_tag = ctt_tag, policy_owner = owner_email | fields policy_tag, policy_owner) as tp tp.policy_tag = policy_tag
| join type = left (dataset = ctt_registry | filter role != "central" | alter package_tag = ctt_tag, package_owner = owner_email | fields package_tag, package_owner) as tk tk.package_tag = package_tag
| join type = left (dataset = ctt_registry | filter lab_octet != "" | comp max(owner_email) as range_owner by lab_octet | alter ip_octet = lab_octet | fields ip_octet, range_owner) as tr tr.ip_octet = ip_octet
| join type = left (dataset = ctt_object_owners | filter object_kind = "Agent installer" and object_name !~= "^(?i)ctt\\s*[-_]" | alter installation_package = object_name, installer_owner = coalesce(creator, last_editor) | fields installation_package, installer_owner) as io io.installation_package = installation_package
| join type = left (dataset = ctt_object_owners | filter object_kind = "Policy rule" and object_name !~= "^(?i)(ctt\\s*[-_]|default)" | alter assigned_prevention_policy = object_name, policy_editor = last_editor | fields assigned_prevention_policy, policy_editor) as po po.assigned_prevention_policy = assigned_prevention_policy
| alter installer_owner = if(installer_owner = "", null, installer_owner), policy_editor = if(policy_editor = "", null, policy_editor)
| alter owner = coalesce(tag_owner, policy_owner, package_owner, installer_owner, policy_editor)
| alter owner_source = if(tag_owner != null, "endpoint tag", if(policy_owner != null, "tag in its policy name", if(package_owner != null, "tag in its installer name", if(installer_owner != null, concat("creator of installer ", installation_package), if(policy_editor != null, concat("last editor of policy ", assigned_prevention_policy), null)))))
| alter owner_label = coalesce(owner, "unknown"), owner_note = if(owner != null, concat("Owner: ", owner, " (", owner_source, ")."), "No owner found: add your tag to the endpoint.")"""
ENDPOINT_FIELDS = "| fields endpoint_id, endpoint_name, lab_ip, owner, owner_label, owner_source, owner_note, tag_owner, range_owner, assigned_prevention_policy, installation_package, finding, guideline_id, title"
ENDPOINT_LINK = 'dataset = endpoints | filter endpoint_name = "$endpoint_name" | dedup endpoint_id by desc last_seen'

RULES = [
    {
        "file": "Active_user_not_in_registry",
        "name": "CTT - Hygiene - Active user not in registry",
        "guideline": "CTT-GEN-01",
        "description": "A user signed in to the tenant but has no row in the CTT registry, so nothing they create can be traced to a tag (CTT-GEN-01).",
        "xql": f"""{LOGIN_BASE}
{ACTOR}
| filter actor_registered = "no"
| alter guideline_id = "CTT-GEN-01", title = "Active user not in registry", finding = concat(to_string(logins), " sign-in(s) by a user without a registry row")
| fields actor, actor_email, actor_name, logins, last_login, finding, guideline_id, title""",
        "alert_description": "$actor_email signed in $logins time(s) but is not in the CTT registry. Add them to the registry sheet with a tag and lab octet (guideline $guideline_id).",
        "crontab": "0 1 * * *",
        "window": "24 hours",
        "suppress": ["actor_email"],
        "owner_field": "actor_email",
        "link": 'dataset = management_auditing | filter email = "$actor_email" | sort desc _time',
        "fields": {"actor_effective_username": "actor_email"},
    },
    {
        "file": "Object_created_without_owner_tag",
        "name": "CTT - Hygiene - Object created without owner tag",
        "guideline": "CTT-TAG-01",
        "description": "Someone created an object whose name does not start with a tag registered to them: no tag prefix (CTT-TAG-01), a prefix that is not a registered tag (CTT-TAG-01), or another DC's tag (CTT-TAG-04).",
        "xql": f"""{AUDIT}
| filter action = "create" and object_name != null
| alter finding = if(obj_tag = null, "no tag prefix", if(obj_owner_role = null, concat("prefix '", obj_tag, "' is not a registered tag"), if(obj_owner_role != "central" and obj_owner != actor, concat("tag '", obj_tag, "' belongs to ", obj_owner), "ok")))
| filter finding != "ok"
| alter guideline_id = if(finding contains "belongs to", "CTT-TAG-04", "CTT-TAG-01")
| alter title = if(guideline_id = "CTT-TAG-04", "Object created with someone else's tag", "Object created without owner tag")
{AUDIT_FIELDS}""",
        "alert_description": "$actor created $object_kind '$object_name': $finding. Rename it to start with your own tag (guideline $guideline_id).",
        "crontab": "*/30 * * * *",
        "window": "35 minutes",
        "suppress": ["actor", "object_name"],
        "link": AUDIT_LINK,
        "fields": {"actor_effective_username": "actor"},
    },
    {
        "file": "Another_owners_object_changed",
        "name": "CTT - Hygiene - Another owner's object changed",
        "guideline": "CTT-OWN-01",
        "description": "Someone who is not a CTT admin edited or deleted an object whose tag belongs to another DC (CTT-OWN-01).",
        "xql": f"""{AUDIT}
| filter action in ("modify", "delete") and object_name != null
| filter obj_owner_role in ("dc", "admin") and obj_owner != actor and actor_is_admin != 1
| alter guideline_id = "CTT-OWN-01", title = "Another owner's object changed", finding = concat(subtype, " on an object owned by ", obj_owner)
{AUDIT_FIELDS}""",
        "alert_description": "$actor ran '$subtype' on $object_kind '$object_name', which belongs to $obj_owner (guideline $guideline_id). Ask the owner, or duplicate the object under your own tag.",
        "crontab": "*/30 * * * *",
        "window": "35 minutes",
        "suppress": ["actor", "object_name"],
        "link": AUDIT_LINK,
        "fields": {"actor_effective_username": "actor"},
    },
    {
        "file": "Builtin_or_untagged_content_changed",
        "name": "CTT - Hygiene - Built-in or untagged content changed",
        "guideline": "CTT-OOTB-01",
        "description": "Someone, CTT admins included, edited, deleted, adopted or detached content without a registered owner tag: built-in or marketplace content, or an untagged custom object (CTT-OOTB-01, CTT-OOTB-02 for AI agents).",
        "xql": f"""{AUDIT}
| filter (action in ("modify", "delete") and object_name != null and obj_owner_role = null) or subtype ~= "^(Adopt|Detach)"
| alter guideline_id = if(object_kind in ("Agent", "Action"), "CTT-OOTB-02", "CTT-OOTB-01"), title = "Built-in or untagged content changed"
| alter finding = if(subtype ~= "^(Adopt|Detach)", "marketplace content adopted or detached", if(obj_tag = null, "object has no owner tag", concat("prefix '", obj_tag, "' is not a registered tag")))
{AUDIT_FIELDS}""",
        "alert_description": "$actor ran '$subtype' on $object_kind '$object_name' ($finding). Duplicate built-in content and change the copy under your own tag (guideline $guideline_id).",
        "crontab": "*/30 * * * *",
        "window": "35 minutes",
        "suppress": ["actor", "object_name"],
        "link": AUDIT_LINK,
        "fields": {"actor_effective_username": "actor"},
    },
    {
        "file": "Policy_rule_not_scoped_by_owner_tag",
        "name": "CTT - Hygiene - Policy rule not scoped by your tag",
        "guideline": "CTT-TAG-02",
        "description": "Someone created a policy rule, or changed its scope, without targeting one of their own endpoint tags: it targets endpoint names or other conditions, or only tags that belong to someone else (CTT-TAG-02). Collector policies are skipped.",
        "xql": f"""{AUDIT}
| filter object_kind = "Policy rule" and object_name != null and action in ("create", "modify")
| alter scope_target = coalesce(arrayindex(regextract(description, "with target (.+?) created$"), 0), arrayindex(regextract(description, "scope updated to include: (.+)$"), 0))
| filter scope_target != null and scope_target !~= "^collector"
| alter scope_tags = arrayindex(regextract(scope_target, "tags (?:=|in) ([^=]+?)(?: and [a-z ]+ (?:=|in) .*)?$"), 0)
| alter ttags = if(scope_tags = null, arraycreate("-"), split(scope_tags, ","))
| arrayexpand ttags
| alter ttag = lowercase(trim(ttags))
| join type = left (dataset = ctt_registry | alter ttag = ctt_tag, ttag_owner = owner_email, ttag_role = role | fields ttag, ttag_owner, ttag_role) as tt tt.ttag = ttag
| alter mine = if(ttag_owner = actor or (ttag_role = "central" and actor_is_admin = 1), 1, 0)
| comp max(mine) as has_own_tag by _time, actor, actor_email, actor_registered, object_kind, object_name, obj_tag, obj_owner, action, subtype, description, scope_target, scope_tags
| filter has_own_tag = 0
| alter guideline_id = "CTT-TAG-02", title = "Policy rule not scoped by your tag"
| alter finding = if(scope_tags = null, concat("it targets ", scope_target, " instead of your endpoint tag"), concat("it targets tag ", scope_tags, ", which is not one of your tags"))
{AUDIT_FIELDS}""",
        "alert_description": "$actor saved $object_kind '$object_name': $finding. Scope policies to endpoints that carry your own tag (guideline $guideline_id).",
        "crontab": "*/30 * * * *",
        "window": "35 minutes",
        "suppress": ["actor", "object_name"],
        "link": AUDIT_LINK,
        "fields": {"actor_effective_username": "actor"},
    },
    {
        "file": "Centrally_managed_setting_changed",
        "name": "CTT - Hygiene - Centrally managed setting changed",
        "guideline": "CTT-CEN-01",
        "severity": "SEV_040_HIGH",
        "description": "Someone who is not a CTT admin changed a centrally managed area: tenant settings, permissions, SSO, content packs, a managed integration instance, or central CTT content (CTT-CEN-01).",
        "xql": f"""{AUDIT}
| alter brand = arrayindex(regextract(description, "BrandName: ([^,]+)"), 0)
| filter actor_is_admin != 1
| filter (management_auditing_type in (ENUM.MANAGEMENT_AUDIT_SERVER_SETTINGS, ENUM.MANAGEMENT_AUDIT_PERMISSIONS, ENUM.MANAGEMENT_AUDIT_AUTHENTICATION_SETTINGS) and subtype != "Read") or object_kind = "ContentPack" or brand in ({", ".join('"' + b + '"' for b in MANAGED_BRANDS)}) or (obj_owner_role = "central" and action != "other")
| alter object_name = coalesce(object_name, description)
| alter guideline_id = "CTT-CEN-01", title = "Centrally managed setting changed"
| alter finding = if(object_kind = "ContentPack", concat(subtype, ": ", description), if(obj_owner_role = "central", concat(subtype, " on central CTT content"), if(brand != null, concat(subtype, " on managed integration ", brand), subtype)))
{AUDIT_FIELDS}""",
        "alert_description": "$actor, who is not a CTT admin, made a change in a centrally managed area: $finding (guideline $guideline_id). Ask the CTT admins in the team channel instead.",
        "crontab": "*/30 * * * *",
        "window": "35 minutes",
        "suppress": ["actor", "subtype"],
        "link": AUDIT_LINK,
        "fields": {"actor_effective_username": "actor"},
    },
    {
        "file": "Endpoint_outside_owners_lab_range",
        "name": "CTT - Hygiene - Endpoint outside owner's lab range",
        "guideline": "CTT-LAB-01",
        "description": "An endpoint has a lab address (10.<octet>.y.z or 172.16.<octet>.z) in a lab range that is unassigned or belongs to someone other than the endpoint's owner. The owner is found through its endpoint tag, the tag in its policy or installer name, the creator of its installer, or the last editor of its policy rule (CTT-LAB-01).",
        "xql": f"""{ENDPOINT_BASE}
| filter lab_ip != null and (range_owner = null or (owner != null and range_owner != owner))
| alter guideline_id = "CTT-LAB-01", title = "Endpoint outside owner's lab range"
| alter finding = if(range_owner = null, concat("IP ", lab_ip, " is in an unassigned lab range"), concat("IP ", lab_ip, " is in the lab range of ", range_owner, " but the endpoint belongs to ", owner))
{ENDPOINT_FIELDS}""",
        "alert_description": "Endpoint $endpoint_name: $finding. $owner_note Move it into your own lab range, 10.<octet>.0.0/16 or 172.16.<octet>.0/24 (guideline $guideline_id).",
        "crontab": "0 2 * * *",
        "window": "7 days",
        "suppress": ["endpoint_id"],
        "owner_field": "owner_label",
        "link": ENDPOINT_LINK,
        "fields": {"agent_hostname": "endpoint_name", "actor_effective_username": "owner_label"},
    },
    {
        "file": "Endpoint_without_owner_tag",
        "name": "CTT - Hygiene - Endpoint without owner tag",
        "guideline": "CTT-LAB-02",
        "enabled": False,
        "description": "An endpoint carries no registered tag as an endpoint or server tag (CTT-LAB-02, proposed guideline; ships disabled).",
        "xql": f"""{ENDPOINT_BASE}
| filter tag_owner = null
| alter guideline_id = "CTT-LAB-02", title = "Endpoint without owner tag", finding = if(owner != null, concat("no endpoint tag; likely owner ", owner), "no endpoint tag and no owner found")
{ENDPOINT_FIELDS}""",
        "alert_description": "Endpoint $endpoint_name has no registered owner tag ($finding). $owner_note Add your tag as an endpoint tag (guideline $guideline_id).",
        "crontab": "0 2 * * *",
        "window": "7 days",
        "suppress": ["endpoint_id"],
        "owner_field": "owner_label",
        "link": ENDPOINT_LINK,
        "fields": {"agent_hostname": "endpoint_name", "actor_effective_username": "owner_label"},
    },
    {
        "file": "API_key_created_without_expiry",
        "name": "CTT - Hygiene - API key created without expiry",
        "guideline": "CTT-CEN-02",
        "enabled": False,
        "description": "Someone created an API key with no expiration date (CTT-CEN-02, proposed guideline; ships disabled).",
        "xql": """dataset = management_auditing
| filter management_auditing_type = ENUM.MANAGEMENT_AUDIT_API_KEY and subtype = "Add New Key" and description contains "Expiration UTC Time: Not specified"
| filter management_auditing_result = ENUM.MANAGEMENT_AUDIT_SUCCESS and email contains "@"
| alter actor_email = if(email contains "@", lowercase(email), null), actor_name = lowercase(user_name)
"""
        + ACTOR
        + """
| alter guideline_id = "CTT-CEN-02", title = "API key created without expiry", finding = description
| fields _time, actor, actor_email, finding, guideline_id, title, description""",
        "alert_description": "$actor created an API key without an expiration date: $finding (guideline $guideline_id).",
        "crontab": "*/30 * * * *",
        "window": "35 minutes",
        "suppress": ["actor", "description"],
        "link": AUDIT_LINK,
        "fields": {"actor_effective_username": "actor"},
    },
]


class Literal(str):
    pass


yaml.add_representer(Literal, lambda d, s: d.represent_scalar("tag:yaml.org,2002:str", s, style="|"))


def lint(name: str, query: str) -> None:
    """Fail on syntax errors. Unknown datasets and fields are only hints: the bundled schema lacks
    the ctt_registry lookup and some newer fields (endpoints.endpoint_id), and there is no tenant
    schema while crtxtool cannot sign in to cttasean."""
    res = subprocess.run([str(LINT), "-"], input=query, text=True, capture_output=True)
    findings = [line for line in res.stdout.splitlines() if "  error  " in line or "  warning  " in line]
    errors = [f for f in findings if "  error  " in f and "does not exist" not in f]
    if errors:
        sys.exit(f"xql-lint errors in {name}:\n" + "\n".join(errors))
    for f in findings:
        if "dataset name is invalid" not in f:
            print(f"  {name}: {f.strip()}")


def build(spec: dict) -> dict:
    xql = spec["xql"].strip() + "\n"
    lint(spec["name"], xql)
    alert_name = "CTT - Hygiene - $guideline_id - $title"
    return {
        "global_rule_id": str(uuid.uuid5(NS, spec["name"])),
        "name": spec["name"],
        "description": spec["description"],
        "fromversion": "8.9.0",
        "is_enabled": spec.get("enabled", True),
        "dataset": "alerts",
        "execution_mode": "SCHEDULED",
        "crontab": spec["crontab"],
        "search_window": spec["window"],
        "timezone": "UTC",
        "xql_query": Literal(xql),
        "action": "ALERTS",
        "alert_domain": "DOMAIN_HEALTH",
        "alert_type": "Unclassified",
        "alert_category": "OTHER",
        "alert_name": alert_name,
        # The marker tells the Notify Owner playbook whom to assign and DM (CTTHygieneTriage).
        "alert_description": f"{spec['alert_description']} [owner: ${spec.get('owner_field', 'actor')}]",
        "alert_fields": spec["fields"],
        "severity": spec.get("severity", "SEV_030_MEDIUM"),
        "user_defined_severity": None,
        "user_defined_category": None,
        "mapping_strategy": "CUSTOM",
        "mitre_defs": {},
        "suppression_enabled": True,
        "suppression_duration": "1 days",
        "suppression_fields": spec["suppress"],
        "investigation_query_link": spec["link"],
        "drilldown_query_timeframe": "ALERT",
        "lookup_mapping": [],
    }


SCRIPTS = CONTENT / "Packs" / "CTTManagement" / "Scripts"
OWNER_INDEX_QUERY = f"""{EXTRACT}
{ACTOR}
{OBJECT.splitlines()[-1]}
| filter object_name != null and object_name != "" and action in ("create", "modify")
| alter is_create = if(action = "create", 1, 0)
| comp earliest(actor) as first_actor, latest(actor) as last_editor, max(is_create) as has_create, max(_time) as last_ts by object_kind, object_name
| alter creator = if(has_create = 1, first_actor, ""), last_change = format_timestamp("%Y-%m-%dT%H:%M:%SZ", last_ts)
| fields object_kind, object_name, creator, last_editor, last_change"""
# Data collectors (HTTP collectors and other data collection) that no API lists: those created in the
# window and neither edited nor deleted since. The audit log records a rename as an edit of the old
# name, so an edited collector may carry another name now and is left out.
INVENTORY_COLLECTOR_QUERY = f"""{EXTRACT}
{ACTOR}
| filter object_kind = "Data collector" and object_name != null and object_name != ""
| alter is_create = if(action = "create", 1, 0)
| comp count() as events, max(is_create) as has_create, earliest(actor) as creator by object_name
| filter events = 1 and has_create = 1
| fields object_name, creator"""
ENDPOINT_OWNER_QUERY = f"""{ENDPOINT_BASE}
| fields endpoint_id, endpoint_name, lab_ip, owner, owner_source"""
# Rule stages the fix check reuses, so it judges an issue fixed by the rule's own logic.
SCOPE_STAGES = '| alter scope_target = coalesce(arrayindex(regextract(description, "with target (.+?) created$"), 0), arrayindex(regextract(description, "scope updated to include: (.+)$"), 0))' + "\n" + '| alter scope_tags = arrayindex(regextract(scope_target, "tags (?:=|in) ([^=]+?)(?: and [a-z ]+ (?:=|in) .*)?$"), 0)'
# "__NAMES__" is replaced at run time by the quoted names of the open issues.
FIX_POLICY_QUERY = f"""{AUDIT}
| filter object_kind = "Policy rule" and object_name in ("__NAMES__")
{SCOPE_STAGES.splitlines()[0]}
| filter action = "delete" or scope_target != null
{SCOPE_STAGES.splitlines()[1]}
| dedup object_name by desc _time
| fields _time, object_name, action, actor, scope_target, scope_tags"""
FIX_ENDPOINT_QUERY = f"""{ENDPOINT_BASE}
| filter endpoint_name in ("__NAMES__")
| alter violating = if(lab_ip != null and (range_owner = null or (owner != null and range_owner != owner)), 1, 0)
| fields endpoint_name, lab_ip, owner, range_owner, violating"""
# Queries that scripts run with the same stages as the rules, so a rule, the owner index and the
# case housekeeping always agree on object names and endpoint owners.
GENERATED = [
    (SCRIPTS / "CTTOwnerIndex" / "CTTOwnerIndex.py", "OWNER_QUERY", OWNER_INDEX_QUERY),
    (SCRIPTS / "CTTInventoryCheck" / "CTTInventoryCheck.py", "INVENTORY_COLLECTOR_QUERY", INVENTORY_COLLECTOR_QUERY),
    (SCRIPTS / "CTTCaseHousekeeping" / "CTTCaseHousekeeping.py", "ENDPOINT_OWNER_QUERY", ENDPOINT_OWNER_QUERY),
    (SCRIPTS / "CTTHygieneFixCheck" / "CTTHygieneFixCheck.py", "FIX_POLICY_QUERY", FIX_POLICY_QUERY),
    (SCRIPTS / "CTTHygieneFixCheck" / "CTTHygieneFixCheck.py", "FIX_ENDPOINT_QUERY", FIX_ENDPOINT_QUERY),
]


def py_chunks(query: str, width: int = 100) -> str:
    """The query as adjacent string literals, so no line passes the content pipeline's 130
    character limit."""
    pieces = []
    for line in query.splitlines(keepends=True):
        pieces += [line[i : i + width] for i in range(0, len(line), width)]
    return "\n".join(f"    {json.dumps(p)}" for p in pieces)


def write_script_queries() -> None:
    for script, var, query in GENERATED:
        lint(var, query + "\n")
        begin, end = f"# BEGIN GENERATED {var}", f"# END GENERATED {var}"
        text = script.read_text()
        head, rest = text.split(begin, 1)
        _, tail = rest.split(end, 1)
        block = f"{begin} (tools/correlation_rules/gen_correlation_rules.py; do not edit)\n{var} = (\n{py_chunks(query)}\n)\n{end}"
        script.write_text(head + block + tail)
        print(f"wrote {var} into {script.relative_to(CONTENT)}")


def main() -> None:
    write_script_queries()
    OUT.mkdir(parents=True, exist_ok=True)
    expected = set()
    for spec in RULES:
        if spec.get("enabled", True) is False:
            # A pack install ignores is_enabled: false and installs the rule enabled (seen on
            # joris, 2026-11-06). Rules for proposed guidelines stay out of the pack until the
            # guideline is accepted; set "enabled": True on the spec to ship one.
            print(f"skipped {spec['name']} (proposed guideline, not shipped)")
            continue
        path = OUT / f"CTTManagement_{spec['file']}.yml"
        expected.add(path.name)
        path.write_text(yaml.dump(build(spec), sort_keys=False, allow_unicode=True, width=10000))
        print(f"wrote {path.relative_to(CONTENT)} ({'enabled' if spec.get('enabled', True) else 'disabled'})")
    for stale in OUT.glob("CTTManagement_*.yml"):
        if stale.name not in expected:
            stale.unlink()
            print(f"removed {stale.relative_to(CONTENT)}")


if __name__ == "__main__":
    main()
