"""Generate the 'CTT - Guidelines Index' list from Knowledge/CTTManagement/CTT-Guidelines.md.

Run from content/:  python3 tools/docs/gen_guideline_index.py
The triage playbook quotes guidelines from this list, so the doc in git stays the only source.
"""

import json
import re
from pathlib import Path

CONTENT = Path(__file__).resolve().parent.parent.parent
DOC = CONTENT / "Knowledge" / "CTTManagement" / "CTT-Guidelines.md"
OUT = CONTENT / "Packs" / "CTTManagement" / "Lists" / "list-CTT_-_Guidelines_Index.json"
HEAD = re.compile(r"^\*\*(CTT-[A-Z]+-\d+): (.+?)\*\* \*(Active|Proposed)\*\s*$")


def parse(text: str) -> dict:
    index, current, body = {}, None, []
    for line in text.splitlines() + ["### end"]:
        m = HEAD.match(line)
        if m or line.startswith("#"):
            if current:
                index[current["id"]]["text"] = " ".join(" ".join(body).split())
            current, body = None, []
        if m:
            current = {"id": m.group(1)}
            index[m.group(1)] = {"title": m.group(2).rstrip("."), "status": m.group(3), "text": ""}
        elif current and line.strip():
            body.append(line.strip())
    return index


def main() -> None:
    index = parse(DOC.read_text())
    item = {
        "id": "CTT - Guidelines Index",
        "name": "CTT - Guidelines Index",
        "type": "json",
        "description": "Every CTT guideline by ID (title, status, text), generated from CTT-Guidelines.md in git. Read by CTTHygieneTriage.",
        "data": json.dumps(index, indent=1),
        "version": -1,
        "fromVersion": "8.9.0",
        "itemVersion": "",
        "locked": False,
        "nameLocked": False,
        "packID": "CTTManagement",
        "system": False,
        "allRead": True,
        "allReadWrite": False,
        "marketplaces": ["marketplacev2", "platform"],
    }
    OUT.write_text(json.dumps(item, indent=4) + "\n")
    print(f"wrote {OUT.relative_to(CONTENT)} with {len(index)} guidelines")


if __name__ == "__main__":
    main()
