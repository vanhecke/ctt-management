"""Generate the 'CTT - Hygiene' XSIAM dashboard.

Run from content/:  uv run --with pyyaml python3 tools/dashboards/gen_dashboard.py
"""

import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

CONTENT = Path(__file__).resolve().parent.parent.parent
OUT = CONTENT / "Packs" / "CTTManagement" / "XSIAMDashboards" / "CTTManagement_CTT_Hygiene.json"
LINT = CONTENT.parent / "bin" / "xql-lint"
EXTRACT = (CONTENT / "tools" / "correlation_rules" / "10_extract.xql").read_text().strip()
NS = uuid.UUID("2c4e6a8b-1d3f-4b5a-8c7d-9e0f1a2b3c4d")
DAY = 86_400_000

HYGIENE = (
    'dataset = issues\n| filter xdm.issue.name ~= "^CTT - Hygiene - "\n| dedup xdm.issue.id by desc _insert_time\n'
    '| alter guideline = arrayindex(regextract(xdm.issue.name, "(CTT-[A-Z]+-[0-9]+)"), 0)'
)
# CTT SSO accounts (<user>@asean.ctt) are <user>@paloaltonetworks.com in the registry.
CANON_EMAIL = 'replex(lowercase(email), "@asean\\.ctt$", "@paloaltonetworks.com")'
REGISTRY_BY_EMAIL = (
    '| join type = left (dataset = ctt_registry | filter owner_email != "" | comp count() as tags by owner_email '
    "| alter reg_email = owner_email | fields reg_email, tags) as r r.reg_email = actor_email"
)

# (title, description, chart type, phrase, days, width)
ROWS = [
    [
        ("Hygiene issues by guideline", "CTT hygiene issues raised, by guideline ID.", "column",
         f'{HYGIENE}\n| comp count() as issues by guideline\n| sort desc issues\n'
         '| view graph type = column subtype = grouped header = "Hygiene issues by guideline" xaxis = guideline yaxis = issues', 30, 40),
        ("Open hygiene issues", "CTT hygiene issues that are not resolved yet.", "table",
         f'{HYGIENE}\n| filter xdm.issue.status.progress != "RESOLVED"\n'
         "| fields _time, guideline, xdm.issue.name, xdm.issue.description, xdm.issue.status.progress, xdm.issue.id\n| sort desc _time", 30, 60),
    ],
    [
        ("Hygiene issues per day", "New CTT hygiene issues per day and guideline.", "line",
         f'{HYGIENE}\n| bin _time span = 1d\n| comp count() as issues by _time, guideline\n'
         '| view graph type = line header = "Hygiene issues per day" xaxis = _time yaxis = issues series = guideline', 30, 50),
        ("Changes by person", "Successful create, edit, delete and install actions per person in the management audit log.", "column",
         "dataset = management_auditing\n| filter management_auditing_result = ENUM.MANAGEMENT_AUDIT_SUCCESS and email contains \"@\"\n"
         '| filter subtype ~= "^(Add|Upload|Copy|Create|New|Edit|Delete|Change|Update|Install)"\n'
         # One bar per person: the email username is the same for the CTT SSO and the PANW account.
         '| alter person = arrayindex(regextract(lowercase(email), "^([^@]+)@"), 0)\n'
         "| comp count() as changes by person\n| sort desc changes\n| limit 15\n"
         '| view graph type = column subtype = grouped header = "Changes by person" xaxis = person yaxis = changes', 7, 50),
    ],
    [
        ("Objects created without a tag prefix", "Objects created in the last 7 days whose name does not start with a tag.", "table",
         f'{EXTRACT}\n| filter action = "create" and object_name != null and obj_tag = null\n'
         '| filter object_kind not in ("AITask", "CaseField", "IssueField", "Credentials", "KnowledgeSource", "Investigation", "Indicator", "Entry")\n'
         "| fields _time, user_name, object_kind, object_name, subtype\n| sort desc _time", 7, 55),
        ("Open Security cases by age", "Open Security-domain cases, oldest first.", "table",
         "dataset = cases\n| dedup xdm.case.id by desc _insert_time\n"
         '| filter xdm.case.domain = "SECURITY" and xdm.case.status_progress != "RESOLVED"\n'
         '| alter age_days = timestamp_diff(current_time(), _time, "DAY")\n'
         "| fields xdm.case.id, xdm.case.name, xdm.case.assigned_to, xdm.case.severity, age_days\n| sort desc age_days", 90, 45),
    ],
    [
        ("Endpoint ownership", "Endpoints with their tags, prevention policy and the owner found through the policy's tag.", "table",
         "dataset = endpoints\n| dedup endpoint_id by desc last_seen\n"
         '| alter endpoint_tags = json_extract_scalar_array(tags, "$.endpoint_tags")\n'
         '| alter policy_tag = lowercase(arrayindex(regextract(assigned_prevention_policy, "^\\s*([A-Za-z0-9]{2,16})\\s*[-_]"), 0))\n'
         "| join type = left (dataset = ctt_registry | alter policy_tag = ctt_tag, policy_owner = owner_name | fields policy_tag, policy_owner) as p p.policy_tag = policy_tag\n"
         "| fields endpoint_name, endpoint_status, ip_address, endpoint_tags, assigned_prevention_policy, policy_owner, installation_package\n| sort asc endpoint_name", 7, 50),
        ("Active users not in the registry", "People who signed in during the last 30 days but have no registry row.", "table",
         "dataset = management_auditing\n"
         '| filter management_auditing_type = ENUM.MANAGEMENT_AUDIT_AUTHENTICATION and subtype in ("Login", "SSO") and email contains "@"\n'
         f"| alter actor_email = {CANON_EMAIL}\n"
         "| comp count() as logins, max(_time) as last_login, values(user_name) as user_names by actor_email\n"
         f"{REGISTRY_BY_EMAIL}\n| filter reg_email = null\n| fields actor_email, user_names, logins, last_login\n| sort desc logins", 30, 50),
    ],
    [
        ("CTT registry", "The registry synced from the Google Sheet: one row per tag.", "table",
         "dataset = ctt_registry\n| fields ctt_tag, primary_tag, owner_name, owner_email, role, lab_octet, tag_kind, active\n| sort asc primary_tag, asc tag_kind", 1, 100),
    ],
]


def view_options(kind: str, phrase: str) -> dict:
    if kind == "table":
        return {"type": "table", "commands": []}
    m = re.search(r"\| view graph (.+)$", phrase)
    cmds = []
    for name, value in re.findall(r'(\w+) = ("[^"]*"|\S+)', m.group(1)):
        if name != "type":
            cmds.append({"command": {"op": "=", "name": name, "value": value}})
    return {"type": kind, "commands": cmds}


def lint(title: str, phrase: str) -> None:
    res = subprocess.run([str(LINT), "-"], input=phrase, text=True, capture_output=True)
    errors = [l for l in res.stdout.splitlines() if "  error  " in l and "does not exist" not in l]
    if errors:
        sys.exit(f"xql-lint errors in widget '{title}':\n" + "\n".join(errors))


def main() -> None:
    widgets, layout = [], []
    created = 1793900000000
    for r, row in enumerate(ROWS):
        cells = []
        for c, (title, desc, kind, phrase, days, width) in enumerate(row):
            lint(title, phrase)
            key = f"xql_{created + r * 10 + c}"
            data = {"phrase": phrase, "time_frame": {"relativeTime": days * DAY}, "viewOptions": view_options(kind, phrase)}
            widgets.append({"widget_key": key, "title": title, "creation_time": created + r * 10 + c, "description": desc,
                            "data": data, "support_time_range": True,
                            "additional_info": {"query_tables": [], "query_uses_library": False}})
            cells.append({"key": key, "data": {"type": "Custom XQL", "width": width, "height": 400, **data}})
        layout.append({"id": f"row-{r + 1}", "data": cells})
    dash_id = uuid.uuid5(NS, "CTT - Hygiene").hex
    doc = {
        "dashboards_data": [{
            "id": dash_id, "global_id": dash_id, "name": "CTT - Hygiene",
            "description": "CTT tenant hygiene: guideline issues, who changes what, untagged objects, stale cases, endpoint ownership and the registry.",
            "status": "ENABLED", "default_dashboard_id": 1, "layout": layout, "metadata": {"params": []},
        }],
        "widgets_data": widgets,
        "fromVersion": "8.9.0",
        "supportedModules": ["xsiam"],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=4) + "\n")
    print(f"wrote {OUT.relative_to(CONTENT)} with {len(widgets)} widgets")


if __name__ == "__main__":
    main()
