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
watch the audit log raise one issue per change; the daily sweep raises one issue per guideline and
owner and resolves it on its own once the objects are fixed.

## Things you must not do

- Don't rename, retag, disable or delete objects. Explain the fix; the owner does it.
- Don't close or resolve hygiene issues. The sweep resolves its own issues; CTT admins handle the
  rest.
