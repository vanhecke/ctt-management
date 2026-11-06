import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import re
from datetime import UTC, datetime

OWNER_RE = re.compile(r"\[owner: ([^\]]+)\]")
GUIDELINE_RE = re.compile(r"(CTT-[A-Z]+-\d+)")
NO_OWNER = {"", "unknown", "unassigned", "central", "null", "empty", "none"}
NOTIFY_STATE = "CTT - Notify State"


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


def fallback_message(first_name: str, title: str, details: str, gid: str, gtitle: str, url: str = "") -> str:
    """Template body in the same shape as the AI message; CTTHygieneSendDM adds header and link."""
    return (
        f"Hi {first_name},\n\n"
        f"The CTT monitoring found: {title}. {details}\n\n"
        f"Fix:\n• Follow guideline {gid}: {gtitle}.\n\n"
        "If this was intended, reply in the CTT channel."
    )


def issue_url(issue_id: str) -> str:
    urls = demisto.demistoUrls() or {}
    return urls.get("investigation") or f"{urls.get('server', '').rstrip('/')}/issue-view/{issue_id}"


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
            "owner_name": entry.get("owner_name", ""),
            "first_name": first_name,
            "slack_id": entry.get("slack_id", ""),
            "assign": "true" if assign else "false",
            "notify": "true" if notify else "false",
            "reason": reason,
            "fallback_message": fallback_message(first_name, title, details, gid, guideline.get("title", ""), url),
        }
        md = tableToMarkdown(
            "CTT hygiene triage", out, headers=["guideline_id", "owner_email", "slack_id", "assign", "notify", "reason"]
        )
        return_results(CommandResults(readable_output=md, outputs_prefix="CTT.Triage", outputs=out))
    except Exception as e:
        return_error(f"CTTHygieneTriage failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
