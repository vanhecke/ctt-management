Waits until the **Did you fix it?** question of the `CTT - Hygiene - Notify Owner` playbook (an Ask
task asked by Generated link) has written its answer links to the issue context, and returns the
newest link per answer. `CTTHygieneSendDM` puts them behind the **Mark as Fixed** and **Mark as False Positive**
buttons of the owner's DM.

The links open a confirmation page that needs no Cortex login; one click on Submit answers the
question. Asking again (after a "Fixed" that the fix check could not confirm) appends new links;
this script always returns the newest ones.

| Argument | Description |
|---|---|
| task_id | ID of the Ask task in the playbook. |
| timeout | Seconds to wait for the links (default 90). |

Outputs: `CTT.Ask.fixed_url`, `CTT.Ask.not_violation_url`, `CTT.Ask.issue_id`.
