import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import time
from typing import Any

# Reply options of the "Did you fix it?" question in CTT - Hygiene - Notify Owner.
OPTIONS = {"Fixed": "fixed_url", "Not a violation": "not_violation_url"}


def newest_links(value: Any, task_id: str) -> dict[str, str]:
    """The newest link per reply option of one Ask task. The task writes Ask.Links.Task-<id> as an
    object; asking again appends, so the key becomes a list. Later entries win. In a sub-playbook
    the task ID may carry a prefix; the playbook clears Ask before each round, so when no link
    matches the task ID the links that are there are used."""

    def collect(node: Any, match: bool, found: dict[str, str]) -> None:
        if isinstance(node, dict):
            if "link" in node and "option" in node:
                tid = str(node.get("taskID", ""))
                if not match or not task_id or tid == str(task_id) or tid.endswith(f".{task_id}"):
                    key = OPTIONS.get(str(node["option"]))
                    if key:
                        found[key] = str(node["link"])
                return
            for k in sorted(node, key=lambda k: (not str(k).isdigit(), int(k) if str(k).isdigit() else 0, str(k))):
                collect(node[k], match, found)
        elif isinstance(node, list):
            for item in node:
                collect(item, match, found)

    if isinstance(value, dict) and task_id and f"Task-{task_id}" in value:
        value = value[f"Task-{task_id}"]
    found: dict[str, str] = {}
    collect(value, True, found)
    if not found:
        collect(value, False, found)
    return found


def context_query_body(path: str) -> str:
    """The body for POST /investigation/<id>/context. The platform resolves ${...} in command
    arguments against this script's starting snapshot of the context (before the links exist), so
    the dollar sign goes out as the JSON escape \\u0024: core-api-post decodes it and the API
    receives ${path}, which it resolves against the live context."""
    return json.dumps({"query": "${" + path + "}"}).replace("$", "\\u0024")


def live_links(investigation_id: str) -> Any:
    """The investigation's Ask.Links as they are now; the Ask task writes them while this script waits."""
    res = demisto.executeCommand(
        "core-api-post", {"uri": f"/investigation/{investigation_id}/context", "body": context_query_body("Ask.Links")}
    )
    if is_error(res):
        raise DemistoException(get_error(res))
    contents = res[0].get("Contents") or {}
    return contents.get("response") if isinstance(contents, dict) else None


def main():  # pragma: no cover
    args = demisto.args()
    try:
        task_id = str(args.get("task_id") or "")
        timeout = int(args.get("timeout") or 90)
        investigation_id = str(demisto.investigation().get("id"))
        deadline = time.time() + timeout
        links: dict[str, str] = {}
        while True:
            links = newest_links(live_links(investigation_id), task_id)
            if len(links) == len(OPTIONS) or time.time() >= deadline:
                break
            time.sleep(3)
        if len(links) < len(OPTIONS):
            raise DemistoException(
                f"No answer links for task {task_id} after {timeout} s: is the question asked by Generated link?"
            )
        return_results(
            CommandResults(
                readable_output="Answer links ready: " + ", ".join(sorted(links)),
                outputs_prefix="CTT.Ask",
                outputs_key_field="issue_id",
                outputs={"issue_id": investigation_id, **links},
            )
        )
    except Exception as e:
        return_error(f"CTTHygieneAskLinks: {e}")


if __name__ in ("__main__", "__builtin__", "builtins"):
    main()
