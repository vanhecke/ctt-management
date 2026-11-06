Keeps open Security cases tidy, run every 4 hours by the `CTT - Case Housekeeping` job
(guidelines CTT-CASE-01 and CTT-CASE-02). Starred cases are left alone.

| When | Action |
| --- | --- |
| Open for 7 days | Resolved as *Security Testing*, with a comment |
| Unassigned for a day | Assigned to its owner, if one is found |
| No new issue for a day | The owner is asked to close it if the test is done |

The owner of a case is, in this order:

1. The tag of the correlation rule behind its latest issues (`jva - my rule` belongs to the owner of `jva`).
2. The owner of an endpoint in the case: its endpoint tag, the tag in its policy or installer name, the creator of its installer or the last editor of its policy rule (the same chain as the CTT-LAB-01 rule, using the `ctt_object_owners` lookup).
3. The owner of the lab range of a `10.x` address in the case.

Each owner gets one Slack DM per run listing the cases assigned to them, the ones to consider
closing and the ones closed. DMs follow `notify.mode`, the allowlist and the daily limit in
`CTT - Config`, and are sent through `CTTHygieneSendDM`. Each action happens once per case; the
`CTT - Case State` list remembers what was done.

## Settings (`cases` in `CTT - Config`)

| Key | Default | Meaning |
| --- | --- | --- |
| domains | `["Security"]` | Case domains to tidy |
| assign_after_hours | 24 | Age before an unassigned case is assigned |
| suggest_after_hours | 24 | Hours without a new issue before the owner is asked to close it |
| close_after_days | 7 | Age at which a case is resolved |
| skip_starred | true | Leave starred cases alone |
| resolve_reason | `Resolved - Security Testing` | Resolution reason |
| max_closes_per_run | 200 | Cap on cases resolved per run |
| max_assigns_per_run | 100 | Cap on cases assigned per run |
| retry_owner_hours | 24 | How long to wait before looking for an owner again |
| dry_run | false | Report only |

## Arguments

| Argument | Description |
| --- | --- |
| dry_run | `true` only reports what would change. Defaults to `cases.dry_run`. |
