import demistomock as demisto  # noqa: F401
from CommonServerPython import *  # noqa: F401

import json
import time
from typing import Any

# Reply options of the "Did you fix it?" question in CTT - Hygiene - Notify Owner.
OPTIONS = {"Fixed": "fixed_url", "Not a violation": "not_violation_url"}


def newest_links(value: Any, task_id: str) -> dict[str, str]:
    """The newest link per reply option of one Ask task. The task writes Ask.Links.Task-<id> as an
    object; asking again appends, so the key becomes a list. Later entries win."""
    found: dict[str, str] = {}

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if "link" in node and "option" in node:
                if not task_id or str(node.get("taskID", task_id)) == str(task_id):
                    key = OPTIONS.get(str(node["option"]))
                    if key:
                        found[key] = str(node["link"])
                return
            for k in sorted(node, key=lambda k: (not str(k).isdigit(), int(k) if str(k).isdigit() else 0, str(k))):
                walk(node[k])
        elif isinstance(node, list):
            for item in node:
                walk(item)

    if isinstance(value, dict) and task_id and f"Task-{task_id}" in value:
        value = value[f"Task-{task_id}"]
    walk(value)
    return found


def live_links(investigation_id: str) -> Any:
    """The investigation's context as it is now (demisto.context() is a snapshot from the start of
    this script, and the Ask task writes its links while this script waits)."""
    res = demisto.executeCommand(
        "core-api-post", {"uri": f"/investigation/{investigation_id}/context", "body": json.dumps({"query": "${Ask.Links}"})}
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
