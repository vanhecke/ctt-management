Daily CTT inventory check, run by the `CTT - Hygiene - Inventory Check` job. It covers what the
correlation rules cannot see: they only read changes in the audit log, and no dataset lists the
objects that already exist.

It reads the registry from the `CTT - Registry` list (written by CTTRegistrySync), inventories
custom playbooks, scripts, jobs, integration instances, correlation rules and lookup datasets
through the tenant API, and data collectors (HTTP collectors and other data collection) from the
audit log, and checks them against the CTT guidelines. No API lists data collectors, and the audit
log records a rename as an edit of the old name, so it lists collectors created in the last year and
never edited or deleted since. It skips platform objects with fixed names: the `testmodule` instance
and the user hook scripts (`CommonServerUserPython`, `CommonServerUserPowerShell`, `CommonUserServer`).

| Guideline | Check |
| --- | --- |
| CTT-TAG-01 | Name has no tag prefix, or the prefix is not a registered tag (objects that already exist) |
| CTT-TAG-02 | A playbook's Tags field lacks one of its owner's tags (tag fields are not in the audit log) |
| CTT-LIFE-02 | The tag's owner is marked inactive in the registry |

The owner of an untagged object is its creator from the API when that is a person, else whoever
last changed it according to the `ctt_object_owners` lookup (CTTOwnerIndex), else `unknown`.
Objects already named in an open hygiene issue raised by a correlation rule are skipped, so one
object never has two issues.

Findings are grouped per guideline and owner, and each group raises one Medium health issue named
`CTT - Hygiene - <ID> - <title> (<owner>)`. The `CTT - Sweep State` list remembers what was raised.
A group keeps its issue while it is unchanged or only shrinks (items were fixed). When new items
appear, its issue is replaced; when the group is empty, its issue is resolved. The check never
changes the objects it checks. Open Security cases are handled by CTTCaseHousekeeping.

## Arguments

| Argument | Description |
| --- | --- |
| dry_run | `true` reports findings without raising or resolving issues. |
| include_inventory | `true` also returns every inspected object with its tag and owner. |
