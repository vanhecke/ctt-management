import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import re
from datetime import UTC, datetime

OWNER_RE = re.compile(r"\[owner: ([^\]]+)\]")
GUIDELINE_RE = re.compile(r"(CTT-[A-Z]+-\d+)")
NO_OWNER = {"", "unknown", "unassigned", "central", "null", "empty", "none"}
NOTIFY_STATE = "CTT - Notify State"
# Duplicates: the daily rules (LAB-01, GEN-01) raise the same finding again once their one-day
# suppression ends, and a false positive would come back the next day.
NAME_RE = re.compile(r"^CTT - Hygiene - (CTT-[A-Z]+-\d+) - ")
ENDPOINT_RE = re.compile(r"^Endpoint (?P<name>.+?): ")
EMAIL_RE = re.compile(r"^(?P<email>[^\s@]+@[^\s@]+) signed in")
INVENTORY_MARKERS = ("The inventory check found", "The sweep found", "Daily sweep found")
DUPLICATE_REASON = "Resolved - Duplicate Issue"
DAY_MS = 86_400_000
PAGE = 100


def find_owner(issue: dict) -> str:
    """The owner marker the CTT rules and sweep put in every issue description, else a mapped field."""
    custom = issue.get("CustomFields") or {}
    for text in (issue.get("details"), issue.get("description"), custom.get("description")):
        m = OWNER_RE.search(text or "")
        if m:
            return m.group(1).strip().lower()
    for field in ("actor_effective_username", "actoreffectiveusername"):
        value = issue.get(field) or custom.get(field)
        if value:
            return str(value).strip().lower()
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
        found = f"The inventory check found {len(lines)} item(s): " + "; ".join(lines[:4]) + ("; ..." if len(lines) > 4 else ".")
        fixes = {
            "CTT-TAG-01": [f'Rename each one with your tag, for example "{tag} - <name>"'],
            "CTT-TAG-02": [f"Add one of your tags ({', '.join(tags) or tag}) to each playbook's Tags field"],
            "CTT-LIFE-02": ["Hand them over to another DC or delete them"],
        }
        return found, fixes.get(gid, [f"Fix the items listed (guideline {gid})"])
    if gid in ("CTT-TAG-01", "CTT-TAG-04") and name:
        what = "without your tag prefix" if finding.startswith("no tag") else f"({finding})" if finding else "without your tag"
        fix = [f'Rename it to "{rename_target(kind, name, tag)}"']
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


def object_key(name: str, text: str) -> tuple[str, str]:
    """(key, label) of the object a rule issue is about: guideline plus endpoint, user or object.
    Empty for inventory check issues, which keep one issue per guideline and owner themselves."""
    m = NAME_RE.match(name or "")
    text = strip_marker(text)
    if not m or text.startswith(INVENTORY_MARKERS):
        return "", ""
    gid = m.group(1)
    endpoint = ENDPOINT_RE.match(text)
    if endpoint:
        return f"{gid}|endpoint|{endpoint.group('name').lower()}", f"endpoint {endpoint.group('name')}"
    email = EMAIL_RE.match(text)
    if email:
        return f"{gid}|user|{email.group('email').lower()}", email.group("email").lower()
    obj = OBJ_RE.search(text)
    if obj:
        return f"{gid}|{obj.group('kind').lower()}|{obj.group('name')}", f"{obj.group('kind').lower()} '{obj.group('name')}'"
    return "", ""


def find_duplicate(issue_id: str, name: str, text: str, others: list[dict], now_ms: int, fp_days: int) -> tuple[str, str]:
    """(issue id, close note) when an older issue about the same object is still open, or one was
    marked a false positive in the last fp_days days; ("", "") otherwise."""
    key, label = object_key(name, text)
    if not key or not str(issue_id).isdigit():
        return "", ""
    for other in sorted(others, key=lambda o: int(o.get("id") or 0)):
        oid = str(other.get("id") or "")
        if not oid.isdigit() or oid == str(issue_id):
            continue
        if object_key(str(other.get("name") or ""), str(other.get("description") or ""))[0] != key:
            continue
        status = str(other.get("status.progress") or "")
        if status in ("New", "In Progress") and int(oid) < int(issue_id):
            return (
                oid,
                f"Duplicate of issue #{oid}, which is still open for the same {label}. "
                "Closed by the CTT Notify Owner playbook without a DM.",
            )
        resolved = int(other.get("resolution_status_modified_ts") or 0)
        if (
            status == "Resolved"
            and "FALSE_POSITIVE" in str(other.get("status.resolution_reason") or "").upper()
            and fp_days > 0
            and now_ms - resolved < fp_days * DAY_MS
        ):
            day = datetime.fromtimestamp(resolved / 1000, UTC).strftime("%d %b %Y")
            return oid, (
                f"Same {label} as issue #{oid}, which was marked a false positive on {day}. It is not raised again for "
                f"{fp_days} days (notify.false_positive_days in CTT - Config)."
            )
    return "", ""


def related_issues(now_ms: int, fp_days: int) -> list[dict]:
    """Open CTT hygiene issues, plus resolved ones recent enough for the false positive window."""
    searches = [[{"field": "status.progress", "operator": "in", "value": ["New", "In Progress"]}]]
    if fp_days > 0:
        searches.append(
            [
                {"field": "status.progress", "operator": "in", "value": ["Resolved"]},
                {"field": "_insert_time", "operator": "gte", "value": now_ms - 2 * fp_days * DAY_MS},
            ]
        )
    issues: list[dict] = []
    for filters in searches:
        filters = [{"field": "issue_domain", "operator": "in", "value": ["Health"]}, *filters]
        for start in range(0, 3000, PAGE):
            body = {"request_data": {"filters": filters, "search_from": start, "search_to": start + PAGE}}
            res = demisto.executeCommand("core-api-post", {"uri": "/public_api/v1/issue/search", "body": json.dumps(body)})
            if is_error(res):
                raise DemistoException(get_error(res))
            response = res[0]["Contents"].get("response", {})
            page = (response.get("reply", response) if isinstance(response, dict) else {}).get("DATA") or []
            issues.extend(i for i in page if str(i.get("name", "")).startswith("CTT - Hygiene - "))
            if len(page) < PAGE:
                break
    return issues


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
        fp_days = int(notify_cfg.get("false_positive_days", 30))
        duplicate_of, duplicate_note, errors = "", "", []
        try:
            now_ms = int(datetime.now(UTC).timestamp() * 1000)
            duplicate_of, duplicate_note = find_duplicate(
                issue_id, name, details, related_issues(now_ms, fp_days), now_ms, fp_days
            )
        except Exception as e:  # a failed search must not stop the notification
            errors.append(f"duplicate check: {e}")
        if duplicate_of:
            assign, notify, reason = False, False, f"duplicate of issue #{duplicate_of}; closed without a DM"
        out = {
            "issue_id": issue_id,
            "issue_title": title,
            "issue_details": details,
            "issue_url": url,
            "guideline_id": gid,
            "guideline_title": guideline.get("title", ""),
            "guideline_text": guideline.get("text", ""),
            "owner_email": owner,
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
            "duplicate_of": duplicate_of,
            "duplicate_note": duplicate_note,
            "duplicate_reason": DUPLICATE_REASON if duplicate_of else "",
            "fallback_message": fallback_message(first_name, title, details, gid, guideline.get("title", ""), url),
        }
        md = tableToMarkdown(
            "CTT hygiene triage",
            out,
            headers=["guideline_id", "owner_email", "slack_id", "assign", "notify", "duplicate_of", "reason"],
        )
        if errors:
            md += "\n" + "\n".join(f"- {e}" for e in errors)
        return_results(CommandResults(readable_output=md, outputs_prefix="CTT.Triage", outputs_key_field="issue_id", outputs=out))
    except Exception as e:
        return_error(f"CTTHygieneTriage failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
