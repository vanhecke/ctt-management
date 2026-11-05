# CTT Guideline coverage

Which guidelines in `CTT-Guidelines.md` are monitored, and how. Update this file in the same
commit as any change to a rule, a sweep check or a guideline.

**Monitored** values:

- **Yes**: a deployed rule or check raises a health issue.
- **Partial**: some cases are caught; see Limitations.
- **Planned**: designed, not deployed yet.
- **No**: not monitored, and no design yet.
- **Not feasible**: the tenant offers no data to check it.

**Mechanisms:**

- **Rule**: a health-domain correlation rule over `management_auditing` or `endpoints`. It runs
  every 30 minutes (daily for endpoints) and catches changes as they happen.
- **Sweep**: the `CTT - Hygiene - Daily Sweep` job. It inventories objects through the API and
  catches the current state, including objects created before monitoring started.

Issue names follow `CTT - Hygiene - <ID> - <what happened>`. Every issue is Medium severity or
higher, in the Health domain, and never creates a case.

## Coverage

| ID | Guideline | Status | Monitored | Mechanism | Issue | Limitations | Next step |
|---|---|---|---|---|---|---|---|
| CTT-GEN-01 | Register before you build | Active | Planned | Sweep: users active in the last 30 days (`management_auditing` logins) with no registry row | `Active user not in registry` | Needs the registry sync | Build with the sweep |
| CTT-GEN-02 | Announce disruptive work | Proposed | Not feasible | None | None | Behavioural | None |
| CTT-GEN-03 | No real customer data or secrets | Proposed | Not feasible | None | None | Content inspection is out of scope | None |
| CTT-TAG-01 | Prefix object names with your tag | Active | Planned | Rule 1 on create events; Sweep on object names | `Object created without owner tag` | The audit log has no name for automation rules or issue layout rules (sweep only) | Build rule 1 and the sweep |
| CTT-TAG-02 | Set your tag on objects with a tag field | Active | Planned | Sweep: playbook `tags`; policies, layout rules and automation rules where the API exposes tags | `Object missing owner tag field` | Policy and layout-rule tag fields to be confirmed per API | Confirm the APIs on joris |
| CTT-TAG-03 | Tag parsing/modeling rules and list entries in a comment | Active | No | Lists: Sweep on the list description. Parsing/modeling rules: none yet | None | Parsing and modeling rule text has no public API (only crtxtool) | Revisit when crtxtool can sign in to cttasean |
| CTT-TAG-04 | Use only your own tags | Active | Planned | Rule 1: prefix tag not owned by the actor | `Object created with someone else's tag` | Shares rule 1 | Build rule 1 |
| CTT-OWN-01 | Don't change other people's objects | Active | Planned | Rule 2 on edit and delete events | `Another owner's object changed` | Only object types whose audit entry carries the name | Build rule 2 |
| CTT-OOTB-01 | Don't edit built-in content; duplicate it | Active | Planned | Rule 3 on edit, delete, detach and adopt events for untagged objects | `Built-in or unowned content changed` | Can't tell built-in from untagged custom objects; both are flagged | Build rule 3 |
| CTT-OOTB-02 | Don't edit built-in AI agents | Active | Planned | Rule 3: `Edit - Agent` on agents without a tag | `Built-in or unowned content changed` | As above | Build rule 3 |
| CTT-CEN-01 | Leave centrally managed areas to the CTT admins | Active | Planned | Rule 4: tenant settings, permissions, SSO, pack installs, managed integration instances, `CTT` objects, by non-admins | `Centrally managed setting changed` (High) | The admin list comes from the registry (`role = admin`) | Build rule 4 |
| CTT-CEN-02 | API keys with expiry date and tag | Proposed | Planned | Rule on `Add New Key` with `Expiration UTC Time: Not specified` | `API key created without expiry` | Activate when the guideline is accepted | Decide on the guideline |
| CTT-LAB-01 | Build your lab in your own IP range | Active | Planned | Rule 5 (daily, `endpoints`): a `10.x.*` IP whose `x` is not the owner's `lab_octet` | `Endpoint outside owner's lab range` | Only endpoints with an agent; IPs outside 10.0.0.0/8 are skipped | Build rule 5 |
| CTT-LAB-02 | Tag your endpoints | Proposed | Planned | Rule 5: no registered tag in `endpoint_tags` | `Endpoint without owner tag` | Activate when the guideline is accepted | Decide on the guideline |
| CTT-LAB-03 | Remove what you no longer use | Proposed | No | Candidate: Sweep for endpoints disconnected over 30 days | None | None | Decide on the guideline |
| CTT-CASE-01 | Close Security Testing cases when done | Active | Planned | Sweep: open Security-domain cases idle over N days (default 7) | `Stale open case` | "Done" is inferred from inactivity | Build with the sweep |
| CTT-CASE-02 | Assign your test cases to yourself | Proposed | No | Candidate: Sweep for open unassigned Security cases older than 1 day | None | None | Decide on the guideline |
| CTT-LIFE-01 | Clean up after yourself | Proposed | No | Candidate: Sweep for objects untouched over 90 days | None | Needs modified times per object type | Decide on the guideline |
| CTT-LIFE-02 | Hand over when you leave | Proposed | Planned | Sweep: objects whose tag owner is `active = false` in the registry | `Object owned by inactive DC` | Needs the registry sync | Build with the sweep |

## History

| Date | Change |
|---|---|
| 2026-11-05 | First version; all mechanisms planned |
