import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json

REGISTRY_LIST = "CTT - Registry"


# CTT SSO accounts (<user>@asean.ctt) are the same people as <user>@paloaltonetworks.com, the email in
# the CTT registry. Every email from the tenant goes through canonical_email before a registry lookup.
SSO_DOMAIN, HOME_DOMAIN = "@asean.ctt", "@paloaltonetworks.com"


def canonical_email(email) -> str:
    """The registry email for a sign-in email: <user>@asean.ctt (CTT SSO) is <user>@paloaltonetworks.com."""
    e = str(email or "").strip().lower()
    return e[: -len(SSO_DOMAIN)] + HOME_DOMAIN if e.endswith(SSO_DOMAIN) else e


def resolve_owner(rows: list[dict], who: str) -> tuple[str, set[str]]:
    """Returns (owner email, all tags of that owner) for a tag or an email."""
    q = canonical_email(who)
    match = next((r for r in rows if r.get("tag") == q), None) or next((r for r in rows if r.get("owner_email") == q), None)
    if not match:
        return (q if "@" in q else ""), set()
    email = match.get("owner_email") or ""
    tags = {r["tag"] for r in rows if email and r.get("owner_email") == email} or {match["tag"]}
    return email, tags


def filter_for_owner(sweep: dict, email: str, tags: set[str]) -> tuple[list[dict], list[dict]]:
    def mine(item: dict) -> bool:
        return (email and item.get("owner") == email) or item.get("tag") in tags

    inventory = [i for i in sweep.get("Inventory") or [] if mine(i)]
    owned = {(i["kind"], i["name"]) for i in inventory}
    findings = [f for f in sweep.get("Findings") or [] if (email and f.get("owner") == email) or (f["kind"], f["name"]) in owned]
    return inventory, findings


def main():  # pragma: no cover
    try:
        who = demisto.args().get("owner", "")
        res = demisto.executeCommand("getList", {"listName": REGISTRY_LIST})
        rows = [] if is_error(res) else json.loads(res[0]["Contents"] or "[]")
        email, tags = resolve_owner(rows, who)
        if not email and not tags:
            raise DemistoException(f"'{who}' is not a registered tag or email. Use CTTRegistryLookup to find the right one.")
        # Always a dry run: this action reports, it never raises or resolves issues.
        sweep_res = demisto.executeCommand("CTTInventoryCheck", {"dry_run": "true", "include_inventory": "true"})
        if is_error(sweep_res):
            raise DemistoException(f"CTTInventoryCheck failed: {get_error(sweep_res)}")
        sweep = sweep_res[0].get("Contents") or {}
        if isinstance(sweep, str):
            sweep = json.loads(sweep)
        inventory, findings = filter_for_owner(sweep, email, tags)
        md = f"### CTT footprint of {email or who} (tags: {', '.join(sorted(tags)) or 'none'})\n"
        md += tableToMarkdown(f"Objects ({len(inventory)})", inventory, headers=["kind", "name", "tag"])
        md += tableToMarkdown(f"Guideline findings ({len(findings)})", findings, headers=["guideline", "kind", "name", "detail"])
        return_results(
            CommandResults(
                readable_output=md,
                outputs_prefix="CTT.Footprint",
                outputs={"owner": email, "tags": sorted(tags), "objects": inventory, "findings": findings},
            )
        )
    except Exception as e:
        return_error(f"CTTMyFootprint failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
