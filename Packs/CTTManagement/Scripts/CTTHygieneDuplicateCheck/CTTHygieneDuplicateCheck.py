import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import re
from datetime import UTC, datetime

# The daily rules (LAB-01, GEN-01) raise the same finding again once their one-day suppression
# ends, and a finding marked a false positive would come back the next day. The Notify Owner
# playbook runs this first and closes such an issue as a duplicate.
NAME_RE = re.compile(r"^CTT - Hygiene - (CTT-[A-Z]+-\d+) - ")
OWNER_RE = re.compile(r"\[owner: ([^\]]+)\]")
OBJ_RE = re.compile(r"(?:created|saved|on) (?P<kind>[A-Za-z][\w ]*?) '(?P<name>[^']+)'")
ENDPOINT_RE = re.compile(r"^Endpoint (?P<name>.+?): ")
EMAIL_RE = re.compile(r"^(?P<email>[^\s@]+@[^\s@]+) signed in")
INVENTORY_MARKERS = ("The inventory check found", "The sweep found", "Daily sweep found")
DUPLICATE_REASON = "Resolved - Duplicate Issue"
CONFIG_LIST = "CTT - Config"
DAY_MS = 86_400_000
PAGE = 100


# CTT SSO accounts (<user>@asean.ctt) are the same people as <user>@paloaltonetworks.com, the email in
# the CTT registry. Every email from the tenant goes through canonical_email before a registry lookup.
SSO_DOMAIN, HOME_DOMAIN = "@asean.ctt", "@paloaltonetworks.com"


def canonical_email(email) -> str:
    """The registry email for a sign-in email: <user>@asean.ctt (CTT SSO) is <user>@paloaltonetworks.com."""
    e = str(email or "").strip().lower()
    return e[: -len(SSO_DOMAIN)] + HOME_DOMAIN if e.endswith(SSO_DOMAIN) else e


def strip_marker(text: str) -> str:
    return OWNER_RE.sub("", text or "").strip()


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
        return f"{gid}|user|{canonical_email(email.group('email'))}", canonical_email(email.group("email"))
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
            return oid, (
                f"Duplicate of issue #{oid}, which is still open for the same {label}. "
                "Closed by the CTT Notify Owner playbook before anyone was assigned or notified."
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


def related_issues(now_ms: int, fp_days: int) -> list[dict]:  # pragma: no cover
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


def false_positive_days() -> int:  # pragma: no cover
    res = demisto.executeCommand("getList", {"listName": CONFIG_LIST})
    try:
        return int(json.loads(res[0]["Contents"]).get("notify", {}).get("false_positive_days", 30))
    except Exception:
        return 30


def main():  # pragma: no cover
    try:
        issue = demisto.incident() or {}
        issue_id = str(demisto.args().get("issue_id") or issue.get("id") or "")
        name = str(issue.get("name") or "")
        text = str(issue.get("details") or issue.get("description") or "")
        fp_days = false_positive_days()
        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        duplicate_of, note = find_duplicate(issue_id, name, text, related_issues(now_ms, fp_days), now_ms, fp_days)
        out = {
            "issue_id": issue_id,
            "object": object_key(name, text)[1],
            "duplicate_of": duplicate_of,
            "note": note,
            "reason": DUPLICATE_REASON if duplicate_of else "",
        }
        md = (
            f"Duplicate of issue #{duplicate_of}: {note}"
            if duplicate_of
            else f"No other open issue for {out['object'] or 'this issue'}, and no recent false positive."
        )
        return_results(
            CommandResults(readable_output=md, outputs_prefix="CTT.Duplicate", outputs_key_field="issue_id", outputs=out)
        )
    except Exception as e:
        return_error(f"CTTHygieneDuplicateCheck failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
