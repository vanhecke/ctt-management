Daily CTT hygiene sweep, run by the `CTT - Hygiene - Daily Sweep` job.

It reads the registry from the `CTT - Registry` list (written by CTTRegistrySync), inventories
custom playbooks, scripts, jobs, integration instances, correlation rules, lookup datasets and
open Security cases through the tenant API, and checks them against the CTT guidelines:

| Guideline | Check |
| --- | --- |
| CTT-TAG-01 | Name has no tag prefix, or the prefix is not a registered tag |
| CTT-TAG-02 | A playbook's Tags field lacks one of its owner's tags |
| CTT-LIFE-02 | The tag's owner is marked inactive in the registry |
| CTT-CASE-01 | An open Security case has not changed for `stale_case_days` days |

Findings are grouped per guideline and owner, and each group raises one Medium health issue named
`CTT - Hygiene - <ID> - <title> (<owner>)`. The `CTT - Sweep State` list remembers what was raised.
A group keeps its issue while it is unchanged or only shrinks (items were fixed). When new items
appear, its issue is replaced; when the group is empty, its issue is resolved. The sweep never
changes the objects it checks.

## Arguments

| Argument | Description |
| --- | --- |
| dry_run | `true` reports findings without raising or resolving issues. |
| stale_case_days | Overrides `sweep.stale_case_days` in `CTT - Config` (default 7). |
