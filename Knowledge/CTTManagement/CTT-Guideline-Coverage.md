# CTT Guideline coverage

Which guidelines in `CTT-Guidelines.md` are monitored, and how. Update this file in the same
commit as any change to a rule, a playbook check or a guideline.

**Type** values:

- **CR**: a health-domain correlation rule. Correlation rules are the default: they catch a
  change minutes after it happens, from `management_auditing` or `endpoints`.
- **PB**: a playbook-based check, run by a job. Used only where a correlation rule can't do the
  job; the reason is in [Why some checks are playbook-based](#why-some-checks-are-playbook-based).
- **CR + PB**: a rule for changes as they happen, plus a playbook check for what the rule can't
  see.
- **—**: not monitored.

**Monitored** values:

- **Built**: in the CTTManagement pack and tested on the joris test tenant, not deployed to cttasean yet.
- **Partial**: some cases are caught; see Limitations.
- **Designed**: the rule or check is written but not shipped.
- **No**: not monitored, and no design yet.
- **Not feasible**: the tenant offers no data to check it.

Issue names follow `CTT - Hygiene - <ID> - <what happened>`. Every issue is Medium severity or
higher and opens its own case, both in the Health domain. The `CTT - Hygiene - Notify Owner`
automation rule runs on each one: it assigns the issue to its owner, sends a Slack DM and sets it
to In Progress.

## Coverage

| ID | Guideline | Status | Type | Monitored | Mechanism | Issue | Limitations | Next step |
|---|---|---|---|---|---|---|---|---|
| CTT-GEN-01 | Register before you build | Active | CR | Built | Rule `Active user not in registry` (daily, sign-ins in `management_auditing` without a registry row) | `Active user not in registry` | Sign-ins through crtxtool (`@crtxtool.invalid`) are ignored | Deploy |
| CTT-GEN-02 | Announce disruptive work | Proposed | — | Not feasible | None | None | Behavioural | None |
| CTT-GEN-03 | No real customer data or secrets | Proposed | — | Not feasible | None | None | Content inspection is out of scope | None |
| CTT-TAG-01 | Prefix object names with your tag | Active | CR + PB | Built | Rule `Object created without owner tag` (every 30 min, create events: playbooks, scripts, integration instances, correlation rules, agent installers, policy rules and more). Inventory check (daily) for objects that already exist: playbooks, scripts, jobs, integration instances, correlation rules, lookups | `Object created without owner tag`; `Objects without a registered owner tag` | Audit entries for automation rules and issue layout rules carry no name. Lists are not checked (pack lists can't be told apart). The inventory check skips objects already in an open rule issue | Deploy |
| CTT-TAG-02 | Set your tag on objects with a tag field | Active | CR + PB | Partial | Rule `Policy rule not scoped by your tag` (policy rule creates and scope edits that target endpoint names or someone else's tags). Inventory check: the playbook Tags field must hold one of the owner's tags | `Policy rule not scoped by your tag`; `Playbooks missing the owner tag field` | Layout rules and automation rules are not checked: neither the API nor the audit log shows their tag field. Collector policies are skipped | Add layout and automation rules if an API appears |
| CTT-TAG-03 | Tag parsing/modeling rules and list entries in a comment | Active | — | No | None yet | None | Parsing and modeling rule text has no public API (only crtxtool) | Revisit when crtxtool can sign in to cttasean |
| CTT-TAG-04 | Use only your own tags | Active | CR | Built | Rule `Object created without owner tag`: prefix tag owned by someone else | `Object created with someone else's tag` | Shares the TAG-01 rule | Deploy |
| CTT-OWN-01 | Don't change other people's objects | Active | CR | Built | Rule `Another owner's object changed` (every 30 min, edit and delete events; CTT admins exempt, since cleanup is their job) | `Another owner's object changed` | Only object types whose audit entry carries the name | Deploy |
| CTT-OOTB-01 | Don't edit built-in content; duplicate it | Active | CR | Built | Rule `Built-in or untagged content changed` (edit, delete, adopt and detach on objects without a registered tag; applies to CTT admins too) | `Built-in or untagged content changed` | Can't tell built-in from untagged custom objects; both are flagged | Deploy |
| CTT-OOTB-02 | Don't edit built-in AI agents | Active | CR | Built | Same rule as CTT-OOTB-01, for agents and agent actions | `Built-in or untagged content changed` | As above | Deploy |
| CTT-CEN-01 | Leave centrally managed areas to the CTT admins | Active | CR | Built | Rule `Centrally managed setting changed` (tenant settings, permissions, SSO, pack installs, managed integration brands, `CTT` objects; non-admins only) | `Centrally managed setting changed` (High) | Managed brands are listed in the rule; CIE and XTI/TIM audit types not identified yet | Deploy; add CIE and TIM types |
| CTT-CEN-02 | API keys with expiry date and tag | Proposed | CR | Designed | Rule spec `API key created without expiry` in the generator, not shipped | `API key created without expiry` | Ship when the guideline is accepted | Decide on the guideline |
| CTT-LAB-01 | Build your lab in your own IP range | Active | CR | Built | Rule `Endpoint outside owner's lab range` (daily, `endpoints`). Owner: endpoint tag, the tag in its policy or installer name, the creator of its installer, or the last editor of its policy rule (from the `ctt_object_owners` lookup) | `Endpoint outside owner's lab range` | Only endpoints with an agent; IPs outside 10.0.0.0/8 are skipped. Policies named Default or tagged CTT don't count as an owner | Deploy |
| CTT-LAB-02 | Tag your endpoints | Proposed | CR | Designed | Rule spec `Endpoint without owner tag` in the generator, not shipped (same owner chain as LAB-01) | `Endpoint without owner tag` | Ship when the guideline is accepted | Decide on the guideline |
| CTT-LAB-03 | Remove what you no longer use | Proposed | — | No | Candidate: a rule over `endpoints` for agents disconnected over 30 days | None | None | Decide on the guideline |
| CTT-CASE-01 | Close Security Testing cases when done | Active | PB | Built | Case housekeeping (every 4 h): a Slack reminder to the owner when a case gets no new issue for a day; open Security cases are resolved as Security Testing after 7 days. Starred cases are left alone | None (acts on the case and sends a DM) | "Done" is inferred from inactivity | Deploy with `cases.dry_run` first |
| CTT-CASE-02 | Assign your test cases to yourself | Active | PB | Built | Case housekeeping: a Security case unassigned for a day is assigned to its owner (tag of the correlation rule behind it, an endpoint's owner, or the lab range of a 10.x address), who gets a DM | None (acts on the case and sends a DM) | Cases with no rule tag, known endpoint or lab address stay unassigned | Deploy |
| CTT-LIFE-01 | Clean up after yourself | Proposed | PB | No | Candidate: inventory check for objects untouched over 90 days | None | Needs modified times per object type | Decide on the guideline |
| CTT-LIFE-02 | Hand over when you leave | Proposed | PB | Built | Inventory check: objects whose tag owner is `active = false` | `Objects owned by an inactive DC` | Raised even though the guideline is proposed (it only fires for inactive owners) | Decide on the guideline |

## Why some checks are playbook-based

Correlation rules query datasets, and the only datasets with this information are
`management_auditing` (changes) and `endpoints`. Three things need a playbook:

| Check | Job | Why a correlation rule can't do it |
|---|---|---|
| Objects that already exist (TAG-01) and objects of inactive owners (LIFE-02) | `CTT - Hygiene - Inventory Check` (daily) | No dataset lists playbooks, scripts, jobs or integration instances. The audit log only shows changes, so objects created before monitoring started, or never fixed, are only found through the API |
| The playbook Tags field (TAG-02) | `CTT - Hygiene - Inventory Check` (daily) | The audit log records that a playbook changed, not its Tags field |
| Assigning, reminding and resolving cases (CASE-01, CASE-02) | `CTT - Case Housekeeping` (every 4 h) | Correlation rules can only raise issues; changing a case and sending a DM need the case API and the Slack webhook |

These jobs support the rules but check nothing themselves:

- `CTT - Registry Sync` (hourly): copies the registry Google Sheet into the `ctt_registry` lookup,
  and updates the `ctt_object_owners` lookup (who created and last changed each object, from the
  audit log). The rules join both.
- `CTT - Tenant Status` (daily): the Tenant Status canvas and the channel topic in Slack.

## History

| Date | Change |
|---|---|
| 2026-11-05 | First version; all mechanisms planned |
| 2026-11-06 | Rules, sweep and agent built in the CTTManagement pack |
| 2026-11-06 | CTT-CEN-02 and CTT-LAB-02 rules kept out of the pack until accepted (pack installs ignore is_enabled: false); tested end to end on joris (1.0.8) |
| 2026-11-06 | 1.2.0: Type column (CR/PB). New rule for policy scope (TAG-02); OOTB applies to CTT admins; LAB-01 owners from installer creators and policy editors. The daily sweep became the inventory check (existing objects, Tags field, inactive owners); case checks moved to case housekeeping, which assigns, reminds and resolves cases (CASE-01, CASE-02 now Active) |
