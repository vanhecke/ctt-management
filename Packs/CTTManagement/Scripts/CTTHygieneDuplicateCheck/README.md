First step of the `CTT - Hygiene - Notify Owner` playbook: is this problem already known?

- **Open duplicate:** an older open CTT hygiene issue about the same endpoint (CTT-LAB-01), user
  (CTT-GEN-01) or object (the other rules) and guideline.
- **Recent false positive:** the same finding was resolved as False Positive in the last
  `notify.false_positive_days` days (`CTT - Config`, default 30; 0 switches this off).

Either way the playbook closes the issue as Duplicate Issue with the note from
`CTT.Duplicate.note`, before triage, assignment or a DM. The daily rules raise a finding again
once their one-day suppression ends, so without this an owner got the same DM every day.
Inventory check issues are skipped: the inventory check keeps one issue per guideline and owner.

## Outputs

| Path | Description |
|---|---|
| CTT.Duplicate.duplicate_of | The other issue; empty when this issue is new. |
| CTT.Duplicate.note | The close note. |
| CTT.Duplicate.reason | `Resolved - Duplicate Issue` for a duplicate. |
| CTT.Duplicate.object | The endpoint, user or object the issue is about. |
