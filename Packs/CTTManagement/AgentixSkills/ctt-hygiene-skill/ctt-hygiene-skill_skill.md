# CTT hygiene

## What do I own, and is it compliant?

1. Make sure you know the user's tag or email. Confirm it with <action=CTTRegistryLookupAction>.
2. Run <action=CTTMyFootprintAction> with that tag or email. It inventories custom playbooks,
   scripts, jobs, integration instances, correlation rules and lookups, plus open Security cases,
   and returns the objects the user owns and the guideline findings for them. It takes a minute or
   two; tell the user you are checking.
3. Answer with two short tables: what they own, and what to fix. For each finding, name the
   guideline ID and the concrete fix ("rename `Phishing triage` to `jva - Phishing triage`").

Objects without a tag prefix are attributed to their creator when the tenant records one. Say
"created by you" for those, not "owned by you".

## Explain a hygiene issue

Hygiene issues are Medium health issues named `CTT - Hygiene - <ID> - <what happened>`. Find the
open ones for a person with <action=CortexRunXQLQuery>, timeframe 30 days, widget name
"CTT hygiene issues", widget description "Open CTT hygiene issues", and this query (replace the
email):

```
dataset = issues
| filter xdm.issue.name ~= "^CTT - Hygiene - " and xdm.issue.status.progress != "RESOLVED"
| dedup xdm.issue.id by desc _insert_time
| filter xdm.issue.name contains "jdoe@example.com" or xdm.issue.description contains "jdoe@example.com"
| fields _time, xdm.issue.id, xdm.issue.name, xdm.issue.description
```

Explain what the issue means, which guideline it refers to, and how to fix the object. Rules that
watch the audit log raise one issue per change; the daily inventory check raises one issue per guideline and
owner and resolves it on its own once the objects are fixed.

## How hygiene issues close

- The hourly fix check resolves rule issues it can verify as fixed (renamed or deleted objects,
  registry entries, policy scopes, re-attached built-ins, endpoint ranges), with a close note.
- The owner's Slack DM has the buttons **Mark as Fixed** and **Mark as False Positive**. Mark as Fixed runs the same
  check; Mark as False Positive resolves the issue as False Positive and tells the CTT admins.
- When a user tells you they fixed an issue, use <action=CTTHygieneConfirmFixAction> with its ID.
  Report the result: resolved with the close note, or still open with what is still wrong.
- Guidelines without an automatic check (CTT-OWN-01, CTT-OOTB-02, CTT-CEN-01, and object types the
  API can't list) are resolved on the owner's word.

## Things you must not do

- Don't rename, retag, disable or delete objects. Explain the fix; the owner does it.
- Don't resolve hygiene issues any other way than <action=CTTHygieneConfirmFixAction>, and only for
  the user's own issues that they say they fixed.
