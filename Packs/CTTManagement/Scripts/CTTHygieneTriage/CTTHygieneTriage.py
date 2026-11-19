import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import re
from datetime import UTC, datetime

OWNER_RE = re.compile(r"\[owner: ([^\]]+)\]")
GUIDELINE_RE = re.compile(r"(CTT-[A-Z]+-\d+)")
NO_OWNER = {"", "unknown", "unassigned", "central", "null", "empty", "none"}
NOTIFY_STATE = "CTT - Notify State"


# CTT SSO accounts (<user>@asean.ctt) are the same people as <user>@paloaltonetworks.com, the email in
# the CTT registry. Every email from the tenant goes through canonical_email before a registry lookup.
SSO_DOMAIN, HOME_DOMAIN = "@asean.ctt", "@paloaltonetworks.com"


def canonical_email(email) -> str:
    """The registry email for a sign-in email: <user>@asean.ctt (CTT SSO) is <user>@paloaltonetworks.com."""
    e = str(email or "").strip().lower()
    return e[: -len(SSO_DOMAIN)] + HOME_DOMAIN if e.endswith(SSO_DOMAIN) else e


def sso_account(email) -> str:
    """The CTT SSO account (<user>@asean.ctt) of a registry email, or '' for other domains."""
    e = canonical_email(email)
    return e[: -len(HOME_DOMAIN)] + SSO_DOMAIN if e.endswith(HOME_DOMAIN) else ""


def pick_assignee(owner: str, users: list[dict]) -> str:
    """The owner's tenant account to assign to: the registry email (<user>@paloaltonetworks.com) when that
    user exists on the tenant, else their CTT SSO account (<user>@asean.ctt) when that one exists, else the
    registry email. users: rbac/get_users rows."""
    emails = {str(u.get("user_email") or "").strip().lower() for u in users or []}
    sso = sso_account(owner)
    if owner not in emails and sso and sso in emails:
        return sso
    return owner


def find_owner(issue: dict) -> str:
    """The owner marker the CTT rules and sweep put in every issue description, else a mapped field."""
    custom = issue.get("CustomFields") or {}
    for text in (issue.get("details"), issue.get("description"), custom.get("description")):
        m = OWNER_RE.search(text or "")
        if m:
            return canonical_email(m.group(1))
    for field in ("actor_effective_username", "actoreffectiveusername"):
        value = issue.get(field) or custom.get(field)
        if value:
            return canonical_email(value)
    return ""


def owner_tags(registry: list[dict], owner: str) -> str:
    """The owner's tags, primary first, for the message's rename advice."""
    rows = [r for r in registry if owner and r.get("owner_email") == owner]
    rows.sort(key=lambda r: (r.get("tag_kind") != "primary", r.get("tag", "")))
    return ", ".join(r["tag"] for r in rows if r.get("tag"))


def strip_marker(text: str) -> str:
    return OWNER_RE.sub("", text or "").strip()


def owner_entry(registry: list[dict], owner: str) -> dict:
    return next((r for r in registry if r.get("owner_email") == owner and r.get("tag_kind") == "primary"), None) or next(
        (r for r in registry if r.get("owner_email") == owner), {}
    )


def decide(
    owner: str, entry: dict, mode: str, sent_today: int, max_per_day: int, allowlist: list[str] | None = None
) -> tuple[bool, bool, str]:
    """Returns (assign, notify, reason)."""
    if owner in NO_OWNER or "@" not in owner:
        return False, False, f"no person to assign (owner '{owner or 'none'}')"
    if not entry or not entry.get("slack_id"):
        return True, False, "assigned; no DM because the owner has no Slack ID in the registry"
    if mode == "off":
        return True, False, "assigned; DMs are switched off (notify.mode = off)"
    if mode == "allowlist" and owner not in {a.lower() for a in (allowlist or [])}:
        return True, False, "assigned; DMs go to the notify.allowlist only for now (notify.mode = allowlist)"
    if mode == "admins_only" and entry.get("role") != "admin":
        return True, False, "assigned; DMs go to CTT admins only for now (notify.mode = admins_only)"
    if sent_today >= max_per_day:
        return True, False, f"assigned; daily DM limit reached ({max_per_day})"
    return True, True, "assigned and notified"


OBJ_RE = re.compile(r"(?:created|saved|on) (?P<kind>[A-Za-z][\w ]*?) '(?P<name>[^']+)'")
OWNED_BY_RE = re.compile(r"which belongs to (?P<owner>[^\s,(]+)")
RAN_RE = re.compile(r"ran '(?P<action>[^']+)'")
# The finding runs to the first full stop that ends a sentence, so names with dots stay whole.
FINDING_RE = re.compile(r"'[^']+': (?P<finding>.+?)\.(?= [A-Z]|$)")
UNDERSCORE_KINDS = {"Script", "Lookup dataset", "Dataset", "DATASETS", "LOOKUPS"}


def rename_target(kind: str, name: str, tag: str) -> str:
    """The name with the owner's tag in front, replacing a prefix that is not a registered tag."""
    sep = "_" if kind in UNDERSCORE_KINDS else " - "
    rest = (
        re.sub(r"^\s*[A-Za-z0-9]{2,16}\s*(?: - |-|_)\s*", "", name) if re.match(r"^\s*[A-Za-z0-9]{2,16}\s*[-_]", name) else name
    )
    return f"{tag}{sep}{rest}"


ITEM_RE = re.compile(r"^(?P<kind>[A-Za-z][A-Za-z ]*?) '(?P<name>.+?)': (?P<detail>.+)$")
MAX_NAMES = 8


def summarize_items(lines: list[str]) -> str:
    """The inventory items for the DM: items of one kind with the same finding on one line
    ("Endpoints 'A', 'B': no registered endpoint or server tag"), and the reason the owner was
    chosen once at the end when all items share it."""
    groups: dict[tuple[str, str], list[str]] = {}
    notes: list[str] = []
    for line in lines:
        m = ITEM_RE.match(line)
        if not m:
            groups.setdefault(("", line), [])
            continue
        detail, _, note = m.group("detail").partition("; owner: ")
        groups.setdefault((m.group("kind"), detail), []).append(m.group("name"))
        notes.append(note)
    shared = notes[0] if notes and all(n == notes[0] for n in notes) else ""
    parts = []
    for (kind, detail), names in groups.items():
        if not kind:
            parts.append(detail)
            continue
        quoted = ", ".join(f"'{n}'" for n in names[:MAX_NAMES]) + (
            f" and {len(names) - MAX_NAMES} more" if len(names) > MAX_NAMES else ""
        )
        label = kind if len(names) == 1 else (kind[:-1] + "ies" if kind.endswith("y") else kind + "s")
        parts.append(f"{label} {quoted}: {detail}")
    text = "; ".join(parts[:4]) + ("; ..." if len(parts) > 4 else "") + "."
    if shared:
        text += f" Why you: {shared}."
    return text


def compose(gid: str, title: str, details: str, tags: list[str], lab_octet: str) -> tuple[str, list[str]]:
    """FOUND sentence and FIX steps for the DM, per guideline, from the issue text."""
    tag = tags[0] if tags else "<your tag>"
    others = ", ".join(tags[1:])
    obj = OBJ_RE.search(details or "")
    kind, name = (obj.group("kind"), obj.group("name")) if obj else ("", "")
    m = FINDING_RE.search(details or "")
    finding = m.group("finding") if m else ""
    lines = [line[2:] for line in (details or "").splitlines() if line.startswith("- ")]
    if lines:  # an inventory check issue: a list of items
        found = f"The inventory check found {len(lines)} item(s): " + summarize_items(lines)
        tag02 = []
        if any(line.startswith("Playbook ") for line in lines):
            tag02.append(f"Add one of your tags ({', '.join(tags) or tag}) to each playbook's Tags field")
        if any(line.startswith("Policy rule ") for line in lines):
            tag02.append(f"Scope each policy rule to your endpoint tag (target: endpoint tag {tag}) instead of endpoint names")
        fixes = {
            "CTT-TAG-01": [f'Rename each one with your tag, for example "{tag} - <name>"'],
            "CTT-TAG-02": tag02 or [f"Add one of your tags ({', '.join(tags) or tag}) to each item's tag field or scope"],
            "CTT-LIFE-02": ["Hand them over to another DC or delete them"],
            "CTT-LAB-02": [
                f"Add {tag} as an endpoint tag on each endpoint (Endpoints > All Endpoints > Endpoint Tags)",
                "Or uninstall the agents you no longer use",
            ],
        }
        return found, fixes.get(gid, [f"Fix the items listed (guideline {gid})"])
    if gid in ("CTT-TAG-01", "CTT-TAG-04") and name:
        what = "without your tag prefix" if finding.startswith("no tag") else f"({finding})" if finding else "without your tag"
        fix = [f'Rename it to "{rename_target(kind, name, tag)}"']
        if gid == "CTT-TAG-01" and kind.lower() in ("playbook", "script", "automation", "job", "jobcenter"):
            noun = {"automation": "script", "jobcenter": "job"}.get(kind.lower(), kind.lower())
            fix.append(f"Or add {tag} to the {noun}'s Tags field; then the name needs no prefix")
        if others:
            fix.append(f"Or use another of your tags: {others}")
        return f'{kind} "{name}" was created {what}.', fix
    if gid == "CTT-TAG-02" and name:
        return f'{kind} "{name}" is not scoped by your tag: {finding or "it targets something else"}.', [
            f"Change its target to endpoints tagged {tag}",
            f"Add {tag} as an endpoint tag on your lab machines first",
        ]
    if gid == "CTT-OWN-01" and name:
        owned = OWNED_BY_RE.search(details)
        ran = RAN_RE.search(details)
        owner = owned.group("owner").rstrip(".") if owned else "another DC"
        action = ran.group("action") if ran else "a change"
        return (
            f'You ran "{action}" on {kind} "{name}", which belongs to {owner}.',
            [f"Ask {owner} before changing their objects", "To make your own version, duplicate it under your tag"],
        )
    if gid in ("CTT-OOTB-01", "CTT-OOTB-02") and name:
        return (
            f'You changed {kind} "{name}", which has no registered owner tag ({finding or "built-in or untagged"}).',
            ["Leave built-in and marketplace content as it is", f'Duplicate it and change the copy, named "{tag} - <name>"'],
        )
    if gid == "CTT-CEN-01":
        area = (
            details.split("centrally managed area: ", 1)[-1].split(" (guideline")[0]
            if "centrally managed area: " in details
            else title
        )
        return (
            f"You made a change in a centrally managed area: {area}.",
            ["Central settings, packs and integrations are for the CTT admins", "Ask in the CTT channel when you need a change"],
        )
    if gid == "CTT-LAB-01":
        found = details.split(" Move it", 1)[0] if details else title
        return found, [
            f"Move it into your lab range 10.{lab_octet}.0.0/16 or 172.16.{lab_octet}.0/24"
            if lab_octet
            else "Ask a CTT admin for your lab range"
        ]
    first = (details or title).split(". ")[0].rstrip(".")
    return f"{first}.", [f"Follow guideline {gid}"]


def fallback_message(first_name: str, title: str, details: str, gid: str, gtitle: str, url: str = "") -> str:
    """Template body in the same shape as the AI message; CTTHygieneSendDM adds header and link."""
    return (
        f"Hi {first_name},\n\n"
        f"The CTT monitoring found: {title}. {details}\n\n"
        f"Fix:\n• Follow guideline {gid}: {gtitle}.\n\n"
        "If this was intended, reply in the CTT channel."
    )


def issue_url(issue_id: str) -> str:
    """Issue link in the format the 8.15 UI opens (/issue-view/<id>); demistoUrls()['investigation']
    still points to the older incidents page and treats the issue ID as a case ID."""
    server = ((demisto.demistoUrls() or {}).get("server") or "").rstrip("/")
    return f"{server}/issue-view/{issue_id}"


def get_json_list(name: str, default):
    res = demisto.executeCommand("getList", {"listName": name})
    if is_error(res) or not res[0].get("Contents") or "Item not found" in str(res[0].get("Contents")):
        return default
    try:
        return json.loads(res[0]["Contents"])
    except ValueError:
        return default


def tenant_users() -> list[dict]:  # pragma: no cover
    """The tenant's users with their last sign-in (rbac/get_users), or [] when the API can't be reached."""
    res = demisto.executeCommand(
        "core-api-post", {"uri": "/public_api/v1/rbac/get_users", "body": json.dumps({"request_data": {}})}
    )
    if is_error(res):
        demisto.debug(f"rbac/get_users failed: {get_error(res)}")
        return []
    response = (res[0].get("Contents") or {}).get("response") or {}
    users = response.get("reply", response) if isinstance(response, dict) else response
    return users if isinstance(users, list) else []


def main():  # pragma: no cover
    try:
        issue = demisto.incident() or {}
        issue_id = str(issue.get("id", ""))
        name = issue.get("name", "")
        details = strip_marker(issue.get("details") or issue.get("description") or "")
        cfg = get_json_list("CTT - Config", {})
        notify_cfg = cfg.get("notify", {})
        registry = get_json_list(cfg.get("registry", {}).get("output_list", "CTT - Registry"), [])
        guidelines = get_json_list("CTT - Guidelines Index", {})
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        state = get_json_list(NOTIFY_STATE, {})

        owner = find_owner(issue)
        entry = owner_entry(registry, owner)
        sent_today = int(state.get(today, {}).get(owner, 0))
        assign, notify, reason = decide(
            owner,
            entry,
            notify_cfg.get("mode", "allowlist"),
            sent_today,
            int(notify_cfg.get("max_dms_per_owner_per_day", 3)),
            notify_cfg.get("allowlist", []),
        )
        match = GUIDELINE_RE.search(name) or GUIDELINE_RE.search(details)
        gid = match.group(1) if match else ""
        guideline = guidelines.get(gid, {})
        title = re.sub(r"^CTT - Hygiene - CTT-[A-Z]+-\d+ - ", "", name)
        first_name = (entry.get("owner_name") or owner.split("@")[0] or "there").split()[0]
        tags = [t.strip() for t in owner_tags(registry, owner).split(",") if t.strip()]
        found, fix = compose(gid, title, details, tags, entry.get("lab_octet", ""))
        url = issue_url(issue_id)
        out = {
            "issue_id": issue_id,
            "issue_title": title,
            "issue_details": details,
            "issue_url": url,
            "guideline_id": gid,
            "guideline_title": guideline.get("title", ""),
            "guideline_text": guideline.get("text", ""),
            "owner_email": owner,
            "assignee_email": pick_assignee(owner, tenant_users()) if assign else owner,
            "owner_name": entry.get("owner_name", ""),
            "first_name": first_name,
            "slack_id": entry.get("slack_id", ""),
            "owner_tags": owner_tags(registry, owner),
            "found": found,
            "fix": "\n".join(fix),
            "use_ai": "true" if notify and notify_cfg.get("use_ai") else "false",
            "buttons": "true" if notify_cfg.get("buttons") else "false",
            "assign": "true" if assign else "false",
            "notify": "true" if notify else "false",
            "reason": reason,
            "fallback_message": fallback_message(first_name, title, details, gid, guideline.get("title", ""), url),
        }
        md = tableToMarkdown(
            "CTT hygiene triage",
            out,
            headers=["guideline_id", "owner_email", "assignee_email", "slack_id", "assign", "notify", "reason"],
        )
        return_results(CommandResults(readable_output=md, outputs_prefix="CTT.Triage", outputs_key_field="issue_id", outputs=out))
    except Exception as e:
        return_error(f"CTTHygieneTriage failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
