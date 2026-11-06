Keeps the `ctt_object_owners` lookup dataset up to date from the management audit log: for every object (agent installer, policy rule, playbook, integration instance, correlation rule, …) the person who created it and the person who last changed it.

The CTT correlation rules, `CTTInventoryCheck` and `CTTCaseHousekeeping` use it to find an owner when an object carries no registered tag. The `CTT - Registry Sync` job runs it every hour over the last 3 hours of audit log; on an empty lookup (or with `backfill=true`) it reads 365 days.

## Script Data

| **Name** | **Description** |
| --- | --- |
| Script Type | python3 |
| Tags | CTT |

## Inputs

| **Argument Name** | **Description** |
| --- | --- |
| hours | Hours of audit log to read on a normal run (default 3). |
| backfill | Read `backfill_days` of audit log instead. Done automatically when the lookup is empty. |
| backfill_days | Days of audit log to read on a backfill (default 365). |

## Outputs

| **Path** | **Description** | **Type** |
| --- | --- | --- |
| CTT.OwnerIndex.RowsWritten | Lookup rows added or updated. | Number |
| CTT.OwnerIndex.ObjectsSeen | Objects changed in the window that was read. | Number |
