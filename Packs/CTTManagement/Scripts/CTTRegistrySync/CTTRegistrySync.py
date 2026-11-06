import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import csv
import io
import json
import re
from typing import Any

CONFIG_LIST = "CTT - Config"
LOOKUP_FIELDS = ["ctt_tag", "primary_tag", "owner_email", "owner_name", "slack_id", "role", "lab_octet", "active", "tag_kind"]
TAG_RE = re.compile(r"^[a-z0-9]{2,16}$")
TRUE_VALUES = {"yes", "y", "true", "1", "x"}


# ---------- pure helpers (unit tested) ----------


def norm_header(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def is_true(value: Any) -> bool:
    return str(value or "").strip().lower() in TRUE_VALUES


def rows_to_dicts(rows: list[list[Any]]) -> list[dict[str, str]]:
    """First row is the header. Blank rows are skipped."""
    if not rows:
        return []
    header = [norm_header(h) for h in rows[0]]
    out = []
    for row in rows[1:]:
        cells = [str(c).strip() if c is not None else "" for c in row]
        if not any(cells):
            continue
        cells += [""] * (len(header) - len(cells))
        out.append({h: cells[i] for i, h in enumerate(header) if h})
    return out


def csv_to_rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text or "")))


def sheet_values(sheet: dict) -> list[list[Any]]:
    """GoogleSheets returns rowData as [{"values": [...]}, ...] (or plain lists)."""
    rows = []
    for row in sheet.get("rowData") or []:
        rows.append(row.get("values", []) if isinstance(row, dict) else list(row))
    return rows


def build_registry(
    users: list[dict[str, str]], extra: list[dict[str, str]], central_tags: list[str]
) -> tuple[list[dict[str, str]], list[str]]:
    """Merge primary and extra tags into one record per tag. Returns (records, errors)."""
    records: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    octet_owner: dict[str, str] = {}

    for u in users:
        tag = u.get("tag", "").strip().lower()
        email = u.get("owner_email", "").strip().lower()
        if not TAG_RE.match(tag):
            errors.append(f"Invalid tag '{u.get('tag', '')}' (2-16 letters or digits)")
            continue
        if tag in records:
            errors.append(f"Duplicate tag '{tag}'")
            continue
        if not email:
            errors.append(f"Tag '{tag}' has no owner_email")
            continue
        octet = (u.get("octet") or u.get("lab_octet") or "").strip()
        if octet:
            if not octet.isdigit() or not 0 < int(octet) < 256:
                errors.append(f"Tag '{tag}' has an invalid octet '{octet}'")
                octet = ""
            elif octet_owner.get(octet, email) != email:
                errors.append(f"Octet {octet} is assigned to both {octet_owner[octet]} and {email}")
            else:
                octet_owner[octet] = email
        original = (u.get("original_tag") or "").strip().lower()
        if original:  # CSV fallback: extra tags live in the same table
            extra = [*extra, u]
            continue
        records[tag] = {
            "tag": tag,
            "primary_tag": tag,
            "owner_email": email,
            "owner_name": u.get("owner_name", "").strip(),
            "slack_id": u.get("slack_id", "").strip(),
            "role": "admin" if is_true(u.get("ctt_admin")) or u.get("role", "").lower() == "admin" else "dc",
            "lab_octet": octet,
            "active": "true" if is_true(u.get("active", "yes")) else "false",
            "tag_kind": "primary",
        }

    by_email = {r["owner_email"]: r for r in records.values()}
    for e in extra:
        tag = e.get("tag", "").strip().lower()
        original = (e.get("original_tag") or "").strip().lower()
        email = e.get("owner_email", "").strip().lower()
        if not TAG_RE.match(tag):
            errors.append(f"Invalid extra tag '{e.get('tag', '')}'")
            continue
        if tag in records:
            errors.append(f"Duplicate tag '{tag}'")
            continue
        parent = records.get(original) or by_email.get(email)
        if not parent:
            errors.append(f"Extra tag '{tag}' has no matching primary tag ('{original or email}')")
            continue
        if email and email != parent["owner_email"]:
            errors.append(f"Extra tag '{tag}' owner {email} differs from {parent['tag']} owner {parent['owner_email']}")
            continue
        records[tag] = {**parent, "tag": tag, "tag_kind": "extra"}

    for ct in central_tags:
        ct = ct.strip().lower()
        if ct and ct not in records:
            records[ct] = {
                "tag": ct,
                "primary_tag": ct,
                "owner_email": "",
                "owner_name": "CTT admins",
                "slack_id": "",
                "role": "central",
                "lab_octet": "",
                "active": "true",
                "tag_kind": "central",
            }
        elif ct:
            errors.append(f"Central tag '{ct}' is also registered to a person")

    return sorted(records.values(), key=lambda r: r["tag"]), errors


def to_lookup_row(record: dict[str, str]) -> dict[str, str]:
    """The lookup column is ctt_tag: `tag` is an XQL stage name and breaks queries that join on it."""
    row = {k: v for k, v in record.items() if k != "tag"}
    return {"ctt_tag": record["tag"], **row}


def tags_to_remove(existing: list[dict[str, Any]], records: list[dict[str, str]]) -> list[str]:
    keep = {r["tag"] for r in records}
    return sorted({str(row.get("ctt_tag", "")) for row in existing if row.get("ctt_tag") and row.get("ctt_tag") not in keep})


# ---------- tenant I/O ----------


def load_config() -> dict:
    res = demisto.executeCommand("getList", {"listName": CONFIG_LIST})
    if is_error(res):
        raise DemistoException(f"Cannot read list '{CONFIG_LIST}': {get_error(res)}")
    return json.loads(res[0]["Contents"] or "{}")


def core_api_post(uri: str, body: dict) -> Any:
    res = demisto.executeCommand("core-api-post", {"uri": uri, "body": json.dumps(body)})
    if is_error(res):
        raise DemistoException(f"core-api-post {uri} failed: {get_error(res)}")
    response = res[0]["Contents"].get("response", {})
    return response.get("reply", response) if isinstance(response, dict) else response


def read_sheet(reg: dict) -> tuple[list[dict], list[dict]]:
    args = {
        "spreadsheet_id": reg["spreadsheet_id"],
        "include_grid_data": "true",
        "ranges": f"{reg['users_range']},{reg['extra_tags_range']}",
        "using-brand": reg.get("sheets_brand") or "GoogleSheets",
    }
    res = demisto.executeCommand("google-sheets-spreadsheet-get", args)
    if is_error(res):
        raise DemistoException(f"google-sheets-spreadsheet-get failed: {get_error(res)}")
    contents = res[0].get("Contents") or {}
    if isinstance(contents, str):
        contents = json.loads(contents)
    sheets = contents.get("sheets", [])
    users_title = reg["users_range"].split("!")[0]
    extra_title = reg["extra_tags_range"].split("!")[0]
    by_title = {s.get("title"): s for s in sheets}
    if users_title not in by_title:
        raise DemistoException(f"Sheet tab '{users_title}' not found (got {list(by_title)})")
    users = rows_to_dicts(sheet_values(by_title[users_title]))
    extra = rows_to_dicts(sheet_values(by_title.get(extra_title, {})))
    return users, extra


def read_source_list(name: str) -> list[dict]:
    res = demisto.executeCommand("getList", {"listName": name})
    if is_error(res):
        raise DemistoException(f"Cannot read list '{name}': {get_error(res)}")
    return rows_to_dicts(csv_to_rows(res[0]["Contents"] or ""))


def ensure_lookup(dataset: str) -> bool:
    datasets = core_api_post("/public_api/v1/xql/get_datasets", {"request_data": {}})
    names = {d.get("Dataset Name") or d.get("dataset_name") for d in (datasets or []) if isinstance(d, dict)}
    if dataset in names:
        return False
    core_api_post(
        "/public_api/v1/xql/add_dataset",
        {
            "request_data": {
                "dataset_name": dataset,
                "dataset_type": "lookup",
                "dataset_schema": dict.fromkeys(LOOKUP_FIELDS, "text"),
            }
        },
    )
    return True


def sync_lookup(dataset: str, records: list[dict[str, str]]) -> list[str]:
    existing = core_api_post("/public_api/v1/xql/lookups/get_data", {"request_data": {"dataset_name": dataset}})
    rows = existing.get("data", []) if isinstance(existing, dict) else (existing or [])
    removed = tags_to_remove(rows, records)
    for tag in removed:
        core_api_post(
            "/public_api/v1/xql/lookups/remove_data", {"request_data": {"dataset_name": dataset, "filters": {"ctt_tag": tag}}}
        )
    core_api_post(
        "/public_api/v1/xql/lookups/add_data",
        {"request_data": {"dataset_name": dataset, "key_fields": ["ctt_tag"], "data": [to_lookup_row(r) for r in records]}},
    )
    return removed


def save_list(name: str, records: list[dict[str, str]]) -> None:
    data = json.dumps(records, indent=1)
    res = demisto.executeCommand("setList", {"listName": name, "listData": data})
    if is_error(res):
        res = demisto.executeCommand("createList", {"listName": name, "listData": data})
        if is_error(res):
            raise DemistoException(f"Cannot write list '{name}': {get_error(res)}")


def main():  # pragma: no cover
    try:
        args = demisto.args()
        dry_run = argToBoolean(args.get("dry_run", "false"))
        reg = load_config().get("registry", {})
        source = args.get("source") or reg.get("source", "auto")

        used = source
        users: list[dict] = []
        extra: list[dict] = []
        warnings: list[str] = []
        if source in ("auto", "sheet") and reg.get("spreadsheet_id"):
            try:
                users, extra = read_sheet(reg)
                used = "sheet"
            except Exception as e:
                if source == "sheet":
                    raise
                warnings.append(f"Google Sheet not readable, using list '{reg.get('source_list')}': {e}")
        if not users:
            users = read_source_list(reg.get("source_list", "CTT - Registry Source"))
            used = "list"

        records, errors = build_registry(users, extra, reg.get("central_tags", ["ctt"]))
        if not records:
            raise DemistoException("The registry is empty; nothing was changed.")

        created, removed = False, []
        dataset = reg.get("lookup_dataset", "ctt_registry")
        if not dry_run:
            created = ensure_lookup(dataset)
            removed = sync_lookup(dataset, records)
            save_list(reg.get("output_list", "CTT - Registry"), records)

        summary = {
            "Source": used,
            "Tags": len(records),
            "People": len({r["owner_email"] for r in records if r["owner_email"]}),
            "Admins": len({r["owner_email"] for r in records if r["role"] == "admin"}),
            "LookupCreated": created,
            "Removed": removed,
            "DryRun": dry_run,
        }
        md = tableToMarkdown("CTT registry sync", summary)
        problems = warnings + errors
        if problems:
            md += tableToMarkdown("Problems (rows skipped)", [{"Problem": p} for p in problems])
        return_results(
            CommandResults(
                readable_output=md,
                outputs_prefix="CTT.Registry",
                outputs_key_field="tag",
                outputs=records,
                raw_response={"summary": summary, "problems": problems},
            )
        )
    except Exception as e:
        return_error(f"CTTRegistrySync failed: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
