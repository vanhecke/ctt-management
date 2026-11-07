Checks whether open CTT hygiene issues from the correlation rules are fixed, and resolves the fixed
ones. **Every close carries a close note saying why**, for example "Auto-closed by the CTT fix check:
playbook 'x' no longer exists under that name (renamed or deleted) (checked 07 Nov 10:00 SGT)".

| Guideline | Automatic check |
|---|---|
| CTT-GEN-01 | The person is now in the CTT registry |
| CTT-TAG-01, CTT-TAG-04 | Playbooks, scripts, jobs, integration instances, correlation rules, datasets: no object with that name any more (renamed or deleted). Other object types: none |
| CTT-TAG-02 | The policy rule's latest scope targets one of the owner's tags, or it was deleted (audit log, 90 days) |
| CTT-OOTB-01 | Playbooks and scripts: the built-in object is attached to its pack again, a custom object carries the owner's tag, or it's gone |
| CTT-LAB-01 | The endpoint no longer breaks the rule (same query as the rule), or it no longer reports |
| CTT-OWN-01, CTT-OOTB-02, CTT-CEN-01 | None: they record something that already happened |

Issues raised by the inventory check are skipped: it resolves them itself.

**Cases.** A hygiene issue opens its own Health case, and the case stays open when the issue is
resolved. The fix check closes a case once all its issues are resolved: right after it resolves an
issue, and on every hourly run for all open `CTT - Hygiene - …` cases (whoever resolved the issues).
The case note quotes the issues' close notes.

## Modes

- **Check** (default, the hourly `CTT - Hygiene - Fix Check` job): resolves issues the check finds
  fixed (`Resolved - Fixed`, or `Resolved - Other` where the tenant doesn't offer Fixed).
- **confirm=true** (the owner pressed **Mark as Fixed**, or told the CTT Assistant): verified issues and
  issues without a check are resolved; an issue the check still sees stays open, and `note` says
  what is still wrong (the Notify Owner playbook puts it in the next DM).
- **false_positive=true** (the owner pressed **Mark as False Positive**): posts it to the CTT channel for
  the admins, then resolves as `Resolved - False Positive`.
- **remind=true** (the daily `CTT - Hygiene - Reminders` job): after checking, one digest DM per
  owner with their open issues older than a day and what closed since yesterday, at most once a day
  (state in the `CTT - Fix State` list). DMs follow `notify` in `CTT - Config`.

`dry_run=true` reports only.
