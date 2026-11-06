import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import re

REGISTRY_LIST = "CTT - Registry"
IP_RE = re.compile(r"^10\.(\d{1,3})\.\d{1,3}\.\d{1,3}$")


def lab_range(octet: str) -> str:
    return f"10.{octet}.0.0/16" if octet else ""


def lookup(rows: list[dict], query: str) -> tuple[str, list[dict]]:
    """Match a tag, email, name, lab octet or 10.x.y.z address. Returns (match type, rows)."""
    q = (query or "").strip().lower()
    if not q:
        return "all", rows
    m = IP_RE.match(q)
    if m or q.isdigit():
        octet = m.group(1) if m else q
        return "lab range", [r for r in rows if r.get("lab_octet") == octet]
    by_tag = [r for r in rows if r.get("tag") == q]
    if by_tag:
        owner = by_tag[0].get("owner_email")
        return "tag", [r for r in rows if owner and r.get("owner_email") == owner] or by_tag
    if "@" in q:
        return "email", [r for r in rows if r.get("owner_email") == q]
    return "name", [r for r in rows if q in str(r.get("owner_name", "")).lower()]


def summarise(rows: list[dict]) -> list[dict]:
    people: dict[str, dict] = {}
    for r in rows:
        key = r.get("owner_email") or r.get("tag")
        p = people.setdefault(
            key,
            {
                "owner_name": r.get("owner_name"),
                "owner_email": r.get("owner_email"),
                "role": r.get("role"),
                "active": r.get("active"),
                "primary_tag": r.get("primary_tag"),
                "tags": [],
                "lab_range": lab_range(r.get("lab_octet", "")),
                "slack_id": r.get("slack_id"),
            },
        )
        p["tags"].append(r.get("tag"))
    for p in people.values():
        p["tags"] = sorted(set(p["tags"]))
    return list(people.values())


def main():  # pragma: no cover
    try:
        query = demisto.args().get("query", "")
        res = demisto.executeCommand("getList", {"listName": REGISTRY_LIST})
        if is_error(res):
            raise DemistoException(f"Cannot read '{REGISTRY_LIST}'. Has the CTT - Registry Sync job run? {get_error(res)}")
        rows = json.loads(res[0]["Contents"] or "[]")
        match_type, matches = lookup(rows, query)
        people = summarise(matches)
        md = tableToMarkdown(
            f"CTT registry: {len(people)} match(es) for '{query}' by {match_type}",
            people,
            headers=["owner_name", "owner_email", "tags", "lab_range", "role", "active"],
        )
        return_results(CommandResults(readable_output=md, outputs_prefix="CTT.RegistryLookup", outputs=people))
    except Exception as e:
        return_error(f"CTTRegistryLookup failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
