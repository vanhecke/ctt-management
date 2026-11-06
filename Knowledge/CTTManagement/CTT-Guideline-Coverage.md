# CTT Guideline coverage

Which guidelines in `CTT-Guidelines.md` are monitored, and how. Update this file in the same
commit as any change to a rule, a sweep check or a guideline.

**Monitored** values:

- **Yes**: a deployed rule or check raises a health issue.
- **Partial**: some cases are caught; see Limitations.
- **Built**: in the CTTManagement pack and tested on the joris test tenant, not deployed to cttasean yet.
- **Planned**: designed, not built yet.
- **No**: not monitored, and no design yet.
- **Not feasible**: the tenant offers no data to check it.

**Mechanisms:**

- **Rule**: a health-domain correlation rule over `management_auditing` or `endpoints`. It runs
  every 30 minutes (daily for endpoints) and catches changes as they happen.
- **Sweep**: the `CTT - Hygiene - Daily Sweep` job. It inventories objects through the API and
  catches the current state, including objects created before monitoring started.

Issue names follow `CTT - Hygiene - <ID> - <what happened>`. Every issue is Medium severity or
higher and opens its own case, both in the Health domain (verified on joris on 2026-11-05).

## Coverage

| ID | Guideline | Status | Monitored | Mechanism | Issue | Limitations | Next step |
|---|---|---|---|---|---|---|---|
| CTT-GEN-01 | Register before you build | Active | Built | Rule `CTT - Hygiene - Active user not in registry` (daily, sign-ins in `management_auditing` without a registry row) | `Active user not in registry` | Sign-ins through crtxtool (`@crtxtool.invalid`) are ignored | Deploy |
| CTT-GEN-02 | Announce disruptive work | Proposed | Not feasible | None | None | Behavioural | None |
| CTT-GEN-03 | No real customer data or secrets | Proposed | Not feasible | None | None | Content inspection is out of scope | None |
| CTT-TAG-01 | Prefix object names with your tag | Active | Built | Rule `CTT - Hygiene - Object created without owner tag` (every 30 min, create events); Sweep on playbooks, scripts, jobs, integration instances, correlation rules and lookups | `Object created without owner tag`; `Objects without a registered owner tag` | Audit entries for automation rules and issue layout rules carry no name; lists are not swept (pack lists can't be told apart) | Deploy |
| CTT-TAG-02 | Set your tag on objects with a tag field | Active | Partial | Sweep: playbook Tags field must hold one of the owner's tags | `Playbooks missing the owner tag field` | Policies, layout rules and automation rules not checked yet (tag fields not exposed by the APIs used) | Add the other object types |
| CTT-TAG-03 | Tag parsing/modeling rules and list entries in a comment | Active | No | Lists: Sweep on the list description. Parsing/modeling rules: none yet | None | Parsing and modeling rule text has no public API (only crtxtool) | Revisit when crtxtool can sign in to cttasean |
| CTT-TAG-04 | Use only your own tags | Active | Built | Rule `CTT - Hygiene - Object created without owner tag`: prefix tag owned by someone else | `Object created with someone else's tag` | Shares the TAG-01 rule | Deploy |
| CTT-OWN-01 | Don't change other people's objects | Active | Built | Rule `CTT - Hygiene - Another owner's object changed` (every 30 min, edit and delete events; CTT admins exempt) | `Another owner's object changed` | Only object types whose audit entry carries the name | Deploy |
| CTT-OOTB-01 | Don't edit built-in content; duplicate it | Active | Built | Rule `CTT - Hygiene - Built-in or untagged content changed` (edit, delete, adopt and detach on objects without a registered tag; CTT admins exempt) | `Built-in or untagged content changed` | Can't tell built-in from untagged custom objects; both are flagged | Deploy |
| CTT-OOTB-02 | Don't edit built-in AI agents | Active | Built | Same rule as CTT-OOTB-01, for agents and agent actions | `Built-in or untagged content changed` | As above | Deploy |
| CTT-CEN-01 | Leave centrally managed areas to the CTT admins | Active | Built | Rule `CTT - Hygiene - Centrally managed setting changed` (tenant settings, permissions, SSO, pack installs, managed integration brands, `CTT` objects; non-admins only) | `Centrally managed setting changed` (High) | Managed brands are listed in the rule; CIE and XTI/TIM audit types not identified yet | Deploy; add CIE and TIM types |
| CTT-CEN-02 | API keys with expiry date and tag | Proposed | Designed | Rule spec `CTT - Hygiene - API key created without expiry` in the generator, not shipped | `API key created without expiry` | Ship when the guideline is accepted | Decide on the guideline |
| CTT-LAB-01 | Build your lab in your own IP range | Active | Built | Rule `CTT - Hygiene - Endpoint outside owner's lab range` (daily, `endpoints`; owner from endpoint tag, prevention policy tag or installation package tag) | `Endpoint outside owner's lab range` | Only endpoints with an agent; IPs outside 10.0.0.0/8 are skipped | Deploy |
| CTT-LAB-02 | Tag your endpoints | Proposed | Designed | Rule spec `CTT - Hygiene - Endpoint without owner tag` in the generator, not shipped | `Endpoint without owner tag` | Ship when the guideline is accepted | Decide on the guideline |
| CTT-LAB-03 | Remove what you no longer use | Proposed | No | Candidate: Sweep for endpoints disconnected over 30 days | None | None | Decide on the guideline |
| CTT-CASE-01 | Close Security Testing cases when done | Active | Built | Sweep: open Security cases unchanged for 7 days, grouped per assignee; the CTT Assistant can close cases on request | `Stale open Security cases` | "Done" is inferred from inactivity | Deploy |
| CTT-CASE-02 | Assign your test cases to yourself | Proposed | No | Candidate: Sweep for open unassigned Security cases older than 1 day | None | None | Decide on the guideline |
| CTT-LIFE-01 | Clean up after yourself | Proposed | No | Candidate: Sweep for objects untouched over 90 days | None | Needs modified times per object type | Decide on the guideline |
| CTT-LIFE-02 | Hand over when you leave | Proposed | Built | Sweep: objects whose tag owner is `active = false` | `Objects owned by an inactive DC` | Raised even though the guideline is proposed (it only fires for inactive owners) | Decide on the guideline |

## History

| Date | Change |
|---|---|
| 2026-11-05 | First version; all mechanisms planned |
| 2026-11-06 | Rules, sweep and agent built in the CTTManagement pack |
| 2026-11-06 | CTT-CEN-02 and CTT-LAB-02 rules kept out of the pack until accepted (pack installs ignore is_enabled: false); tested end to end on joris (1.0.8) |
