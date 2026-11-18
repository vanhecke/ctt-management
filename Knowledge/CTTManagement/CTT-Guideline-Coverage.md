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

**Fix check** values (how an open issue closes; see [Remediation](#remediation)):

- **Auto**: the hourly fix check verifies the fix and resolves the issue.
- **Partial**: auto for some object types, owner confirmation for the rest.
- **Confirm**: the issue records something that already happened; it closes when the owner presses
  Mark as Fixed (or tells the CTT Assistant).
- **Inventory**: the inventory check resolves its own issues once the objects are fixed.
- **—**: no issue is raised.

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

| ID | Guideline | Status | Type | Monitored | Fix check | Mechanism | Issue | Limitations | Next step |
|---|---|---|---|---|---|---|---|---|---|
| CTT-GEN-01 | Register before you build | Active | CR | Built | Auto | Rule `Active user not in registry` (daily, sign-ins in `management_auditing` without a registry row) | `Active user not in registry` | Sign-ins through crtxtool (`@crtxtool.invalid`) are ignored | Deploy |
| CTT-GEN-02 | Announce disruptive work | Proposed | — | Not feasible | — | None | None | Behavioural | None |
| CTT-GEN-03 | No real customer data or secrets | Proposed | — | Not feasible | — | None | None | Content inspection is out of scope | None |
| CTT-TAG-01 | Prefix object names with your tag | Active | CR + PB | Built | Partial + Inventory | Rule `Object created without owner tag` (every 30 min, create events: playbooks, scripts, integration instances, correlation rules, agent installers, policy rules and more). Inventory check (daily) for objects that already exist: playbooks, scripts, jobs, integration instances, correlation rules, lookups | `Object created without owner tag`; `Objects without a registered owner tag` | Audit entries for automation rules and issue layout rules carry no name. Lists are not checked (pack lists can't be told apart). The inventory check skips objects already in an open rule issue. A playbook with a registered tag in its Tags field needs no prefix: the rule still raises the issue on create (the audit entry has no tags), and the Notify Owner watch closes it on its first check | Deploy |
| CTT-TAG-02 | Set your tag on objects with a tag field | Active | CR + PB | Partial | Auto + Inventory | Rule `Policy rule not scoped by your tag` (policy rule creates and scope edits that target endpoint names or someone else's tags). Inventory check: the playbook Tags field must hold one of the owner's tags | `Policy rule not scoped by your tag`; `Playbooks missing the owner tag field` | Layout rules and automation rules are not checked: neither the API nor the audit log shows their tag field. Collector policies are skipped | Add layout and automation rules if an API appears |
| CTT-TAG-03 | Tag parsing/modeling rules and list entries in a comment | Active | — | No | — | None yet | None | Parsing and modeling rule text has no public API (only crtxtool) | Revisit when crtxtool can sign in to cttasean |
| CTT-TAG-04 | Use only your own tags | Active | CR | Built | Partial | Rule `Object created without owner tag`: prefix tag owned by someone else | `Object created with someone else's tag` | Shares the TAG-01 rule | Deploy |
| CTT-OWN-01 | Don't change other people's objects | Active | CR | Built | Confirm | Rule `Another owner's object changed` (every 30 min, edit and delete events; CTT admins exempt, since cleanup is their job) | `Another owner's object changed` | Only object types whose audit entry carries the name | Deploy |
| CTT-OOTB-01 | Don't edit built-in content; duplicate it | Active | CR | Built | Partial | Rule `Built-in or untagged content changed` (edit, delete, adopt and detach on objects without a registered tag; applies to CTT admins too) | `Built-in or untagged content changed` | Can't tell built-in from untagged custom objects; both are flagged | Deploy |
| CTT-OOTB-02 | Don't edit built-in AI agents | Active | CR | Built | Confirm | Same rule as CTT-OOTB-01, for agents and agent actions | `Built-in or untagged content changed` | As above | Deploy |
| CTT-CEN-01 | Leave centrally managed areas to the CTT admins | Active | CR | Built | Confirm | Rule `Centrally managed setting changed` (tenant settings, permissions, SSO, pack installs, managed integration brands, `CTT` objects; non-admins only) | `Centrally managed setting changed` (High) | Managed brands are listed in the rule; CIE and XTI/TIM audit types not identified yet | Deploy; add CIE and TIM types |
| CTT-CEN-02 | API keys with expiry date and tag | Proposed | CR | Designed | — | Rule spec `API key created without expiry` in the generator, not shipped | `API key created without expiry` | Ship when the guideline is accepted | Decide on the guideline |
| CTT-LAB-01 | Build your lab in your own IP range | Active | CR | Built | Auto | Rule `Endpoint outside owner's lab range` (daily, `endpoints`). Owner: endpoint tag, the tag in its policy or installer name, the creator of its installer, or the last editor of its policy rule (from the `ctt_object_owners` lookup) | `Endpoint outside owner's lab range` | Only endpoints with an agent; addresses outside 10.0.0.0/8 and 172.16.0.0/16 are skipped (a lab octet covers `10.<octet>.0.0/16` and `172.16.<octet>.0/24`). Policies named Default or tagged CTT don't count as an owner | Deploy |
| CTT-LAB-02 | Tag your endpoints | Proposed | CR | Designed | — | Rule spec `Endpoint without owner tag` in the generator, not shipped (same owner chain as LAB-01) | `Endpoint without owner tag` | Ship when the guideline is accepted | Decide on the guideline |
| CTT-LAB-03 | Remove what you no longer use | Proposed | — | No | — | Candidate: a rule over `endpoints` for agents disconnected over 30 days | None | None | Decide on the guideline |
| CTT-CASE-01 | Close Security Testing cases when done | Active | PB | Built | — | Case housekeeping (every 4 h): a Slack reminder to the owner when a case gets no new issue for a day; open Security cases are resolved as Security Testing after 7 days. Starred cases are left alone | None (acts on the case and sends a DM) | "Done" is inferred from inactivity | Deploy with `cases.dry_run` first |
| CTT-CASE-02 | Assign your test cases to yourself | Active | PB | Built | — | Case housekeeping: a Security case unassigned for a day is assigned to its owner (tag of the correlation rule behind it, an endpoint's owner, or the lab range of a 10.x or 172.16.x address), who gets a DM | None (acts on the case and sends a DM) | Cases with no rule tag, known endpoint or lab address stay unassigned | Deploy |
| CTT-LIFE-01 | Clean up after yourself | Proposed | PB | No | — | Candidate: inventory check for objects untouched over 90 days | None | Needs modified times per object type | Decide on the guideline |
| CTT-LIFE-02 | Hand over when you leave | Proposed | PB | Built | Inventory | Inventory check: objects whose tag owner is `active = false` | `Objects owned by an inactive DC` | Raised even though the guideline is proposed (it only fires for inactive owners) | Decide on the guideline |

## Remediation

How an open hygiene issue closes. Every close by the pack writes a close note saying why, and an
issue with a running Notify Owner playbook is closed by that playbook's last task, never halfway.

| Way | When | Close note starts with |
|---|---|---|
| Fix check, hourly: the Notify Owner playbook's watch, or the `CTT - Hygiene - Fix Check` job for issues without a running playbook | The check verifies the fix | "Auto-closed by the CTT fix check: …" |
| Owner presses **Mark as Fixed** in the DM (or tells the CTT Assistant) | The check verifies it, or the guideline has no check | "Confirmed fixed by …" |
| Owner presses **Mark as False Positive** | Always; the CTT channel is told so admins can tune the rule | "Marked as false positive by …" (False Positive) |
| Inventory check (daily) | All objects of the owner's issue are fixed | its own note |
| Notify Owner playbook, first step | An older issue about the same endpoint, user or object is still open, or one was marked a false positive in the last `notify.false_positive_days` days (30). The daily rules (LAB-01, GEN-01) raise a finding again once their one-day suppression ends | "Duplicate of issue #…" / "Same … as issue #…, which was marked a false positive …" (Duplicate Issue) |
| Notify Owner playbook, second step | The guideline's check already sees the fix (for example a playbook created with the owner's tag in its Tags field), before anyone is assigned or notified | "Auto-closed by the CTT fix check: …" |

Each hygiene issue has its own Health case, which stays open when the issue is resolved; the fix
check closes the case once all its issues are resolved, with a note quoting their close notes.

If the owner presses Mark as Fixed but the check still sees the violation, the issue stays open and a
second DM says what is still wrong; after a second unconfirmed answer the hourly check closes it once
it's fixed. An unanswered issue stays open; the owner gets one daily digest
(`CTT - Hygiene - Reminders`, 10:00 SGT) with their issues open for more than a day.

What each fix check verifies:

| Guideline | Verified when |
|---|---|
| CTT-GEN-01 | The person is in the CTT registry |
| CTT-TAG-01, CTT-TAG-04 | No playbook, script, job, integration instance, correlation rule or dataset has that name any more (renamed or deleted). For CTT-TAG-01 a playbook, script or job also passes when its Tags field carries one of the owner's tags. Other object types: owner confirmation |
| CTT-TAG-02 | The policy rule's latest scope targets one of the owner's tags, or it was deleted (audit log, 90 days) |
| CTT-OOTB-01 | Playbooks and scripts: attached to their pack again, renamed with the owner's tag, or deleted. Other object types: owner confirmation |
| CTT-LAB-01 | The endpoint no longer breaks the rule (the rule's own query), or it no longer reports |

The Tenant Status canvas shows closes by way, median time to fix per guideline, top fixers and the
oldest open issue.

### Suggestions not built yet

- **Exceptions with expiry**: a `ctt_exceptions` lookup (guideline, object, owner, reason, approver,
  expiry) that the rules and the inventory check skip; matching issues close as Risk Accepted.
- **Repeat-offender escalation**: the same owner and guideline three times in 30 days raises the
  next issue as High and lists it for the CTT admins.
- **Issue SLA timers**: start a resolution timer per issue and report breaches.
- **Self-service fixes**: the CTT Assistant renames an object with the owner's tag on request.

## Why some checks are playbook-based

Correlation rules query datasets, and the only datasets with this information are
`management_auditing` (changes) and `endpoints`. Three things need a playbook:

| Check | Job | Why a correlation rule can't do it |
|---|---|---|
| Objects that already exist (TAG-01) and objects of inactive owners (LIFE-02) | `CTT - Hygiene - Inventory Check` (daily) | No dataset lists playbooks, scripts, jobs or integration instances. The audit log only shows changes, so objects created before monitoring started, or never fixed, are only found through the API |
| The playbook Tags field (TAG-02) | `CTT - Hygiene - Inventory Check` (daily) | The audit log records that a playbook changed, not its Tags field |
| Assigning, reminding and resolving cases (CASE-01, CASE-02) | `CTT - Case Housekeeping` (every 4 h) | Correlation rules can only raise issues; changing a case and sending a DM need the case API and the Slack webhook |

The fix check (`CTT - Hygiene - Fix Check`, hourly) re-checks open rule issues: a correlation rule
fires on a change and can't close the issue it raised.

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
| 2026-11-07 | 1.4.0: remediation loop. Fix check column; hourly fix check with close notes; Mark as Fixed / Mark as False Positive buttons in the DM (answer links by Generated link); daily digest; time-to-fix metrics |
| 2026-11-07 | CTT-LAB-01: the rule, the fix check and case housekeeping also accept `172.16.<octet>.0/24` |
| 2026-11-09 | Duplicates and repeated false positives close as Duplicate Issue without a DM; the jobs run on schedule (they were created without the fields the scheduler needs) |
| 2026-11-09 | CTT-TAG-01: a playbook with the owner's tag in its Tags field passes (fix check and inventory check) |
| 2026-11-10 | Notify Owner: duplicate check first, then "already fixed?", then assignment and the Ask Owner sub-playbook next to the hourly watch |
| 2026-11-18 | CTT-TAG-01: a script or job with the owner's tag in its Tags field passes too (fix check, inventory check, DM advice) |
