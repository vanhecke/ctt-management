# CTT Management

Keeps a shared Cortex Team Tenant (CTT) clean. CTT means Cortex Team Tenant: one XSIAM tenant
that a team of Domain Consultants shares for demos, tests and labs. The pack monitors the CTT
guidelines (`Knowledge/CTTManagement/CTT-Guidelines.md` in the repo), keeps Security cases tidy,
publishes the tenant status to the team's Slack channel, and adds the CTT Assistant agent.

Correlation rules raise a health issue for each broken guideline; an automation rule assigns it
to the person responsible and sends them a Slack DM through a Slack workflow webhook. Where a rule
can't see something (objects that already exist, tag fields, case actions), a playbook check does;
`Knowledge/CTTManagement/CTT-Guideline-Coverage.md` says which is which. Nothing in the pack
changes or deletes the objects it checks. Security cases are the exception: they are assigned
after a day and resolved as Security Testing after 7 days.

## Content

| Type | Name | What it does |
| --- | --- | --- |
| Correlation rule | CTT - Hygiene - Active user not in registry | Daily: someone signed in but has no registry row (CTT-GEN-01) |
| Correlation rule | CTT - Hygiene - Object created without owner tag | Every 30 min: new object without the creator's tag prefix (CTT-TAG-01, CTT-TAG-04) |
| Correlation rule | CTT - Hygiene - Another owner's object changed | Every 30 min: another DC's object edited or deleted (CTT-OWN-01) |
| Correlation rule | CTT - Hygiene - Built-in or untagged content changed | Every 30 min: built-in or untagged content edited, deleted, adopted or detached, CTT admins included (CTT-OOTB-01/02) |
| Correlation rule | CTT - Hygiene - Policy rule not scoped by your tag | Every 30 min: policy rule targets endpoint names or someone else's tags (CTT-TAG-02) |
| Correlation rule | CTT - Hygiene - Centrally managed setting changed | Every 30 min, High: settings, permissions, SSO, packs, managed integrations or `CTT` content changed by a non-admin (CTT-CEN-01) |
| Correlation rule | CTT - Hygiene - Endpoint outside owner's lab range | Daily: endpoint in an unassigned or someone else's 10.x.0.0/16 range; owner from tags, its installer's creator or its policy's editor (CTT-LAB-01) |
| (not shipped) | CTT - Hygiene - Endpoint without owner tag | Spec in tools/, ships once CTT-LAB-02 is accepted |
| (not shipped) | CTT - Hygiene - API key created without expiry | Spec in tools/, ships once CTT-CEN-02 is accepted |
| Job + playbook | CTT - Registry Sync | Every hour: Google Sheet registry to the `ctt_registry` lookup and the `CTT - Registry` list, then the audit log to the `ctt_object_owners` lookup |
| Job + playbook | CTT - Hygiene - Inventory Check | 08:30 SGT: objects that already exist without a tag, playbook Tags fields, inactive owners; one issue per guideline and owner |
| Job + playbook | CTT - Hygiene - Fix Check | Every hour: resolves open rule issues whose fix it can verify, with a close note saying why |
| Job + playbook | CTT - Hygiene - Reminders | Daily 10:00 SGT: one Slack digest per owner with their hygiene issues open for more than a day |
| Job + playbook | CTT - Case Housekeeping | Every 4 h: assigns Security cases unassigned for a day, reminds owners to close quiet cases, resolves cases open for 7 days (starred cases are skipped) |
| Job + playbook | CTT - Tenant Status | Daily 09:00 SGT: replaces the Tenant Status canvas and sets the CTT channel topic |
| Job + playbooks | CTT - Marketplace Updates (+ sub-playbook CTT - Marketplace Release Analysis) | Mon-Thu 05:00 SGT: TypeSafe Jev reviews newer pack releases, approved updates are installed and verified, held or failed ones get a review case, and a summary goes to the CTT channel |
| Playbook | CTT - Hygiene - Notify Owner | Per CTT hygiene issue: assign it to its owner, send a Slack DM (FOUND / RULE / FIX template, or AI text with `notify.use_ai`) with the buttons Fixed! / Not a violation / Open issue, set it to In Progress, and wait for the answer: Fixed! runs the fix check, Not a violation closes it as False Positive |
| Automation rule | CTT - Hygiene - Notify Owner | Runs the playbook on every Medium or higher health issue named `CTT - Hygiene - …`; enabled on install (`is_auto_enabled`) |
| Script | CTTRegistrySync, CTTOwnerIndex, CTTInventoryCheck, CTTCaseHousekeeping, CTTTenantStatus, CTTMarketplaceUpdates (JavaScript) | Backing scripts for the jobs |
| Script | CTTSlackPost | Posts a message to the CTT Slack channel (used for the marketplace summary) |
| Script | CTTHygieneTriage, CTTHygieneMessagePrompt (optional AI prompt), CTTHygieneAskLinks, CTTHygieneSendDM, CTTHygieneFixCheck | Backing scripts for notifying owners and closing fixed issues |
| Integration | CTT Slack Webhook | One-way Slack workflow webhook: DM, channel message, channel topic, Tenant Status canvas |
| Script | CTTRegistryLookup, CTTMyFootprint | Backing scripts for the agent |
| Agent action | CTTHygieneConfirmFixAction | "I fixed issue 1234": runs the fix check for the user's issue (with their approval) |
| Script | CTTEnsureJobs | Creates or updates the seven jobs from the `CTT - Jobs` list (run after every install or upgrade) |
| List | CTT - Jobs | The job definitions CTTEnsureJobs applies |
| List | CTT - Guidelines Index | Every guideline by ID, generated from CTT-Guidelines.md; quoted in the DMs |
| List | CTT - Config | Pack settings (registry sheet, notify mode, inventory check, case housekeeping) |
| List | CTT - Registry Source | CSV fallback registry, used when the sheet can't be read |
| Dashboard | CTT - Hygiene | Issues by guideline, who changes what, untagged objects, stale cases, endpoint ownership, registry |
| AI agent | CTT Assistant (`ctt-assistant-agent`) | Explains guidelines, looks up owners, shows a DC's footprint, closes finished Security Testing cases on request |

Every hygiene issue is a Medium (or High) health issue named
`CTT - Hygiene - <guideline ID> - <what happened>`, and each opens its own case in the Health
domain. Automation rules only run on Medium or higher issues.

Lookups the pack keeps: `ctt_registry` (tags, owners, lab octets, Slack IDs) and
`ctt_object_owners` (who created and last changed each object, from the audit log). The rules
join both.

## Requirements

- A Core REST API instance (used by all scripts).
- A GoogleSheets instance that can read the registry sheet (otherwise the sync falls back to the
  `CTT - Registry Source` list).
- A `CTT Slack Webhook` instance: the Slack workflow trigger URL, the CTT channel ID and a placeholder member ID.
- A `TypeSafe Jev` instance (pack TypeSafeJev, command `jev-evaluate`) for `CTT - Marketplace Updates`. It is not a
  pack dependency, so the pack installs without it; the job then closes each run without changes.
- `notify.mode` in `CTT - Config`: `allowlist` (default, DMs only to `notify.allowlist`), `admins_only`, `all` or `off`. `notify.use_ai` switches the DM text from the template to the AI prompt. `notify.buttons` (default `false`) sends the answer links as Slack buttons through the webhook action `msg_person_health_issue`; turn it on once the Slack workflow has that branch (see the CTT Slack Webhook README).
- Install the pack fresh (uninstall first) when upgrading from a version before 1.1.3: `adopted: true` only takes effect when a playbook is first installed, and playbooks must be adopted to run on issues.
- `cases.dry_run` in `CTT - Config` ships as `true`: case housekeeping only reports until you set it to `false`.
- XSIAM 4.0 for the agent's knowledge documents. On 8.15 the agent installs, but its knowledge is
  empty.

## After installing

1. Configure the `CTT Slack Webhook` instance.
2. Run `!CTTEnsureJobs remove_obsolete=true` in the playground. Pack uploads to XSIAM 8.15 skip the Jobs folder, so
   this creates the seven jobs from the `CTT - Jobs` list and deletes jobs of older versions.
3. Run `!CTTRegistrySync` and `!CTTOwnerIndex` once. They create the `ctt_registry` and
   `ctt_object_owners` lookups that the correlation rules join on (the owner index reads 365 days
   of audit log on its first run). The rules raise nothing until both exist.
4. Check under Automation Rules that `CTT - Hygiene - Notify Owner` is enabled.
5. Check the `CTT - Hygiene` dashboard's registry widget.
6. Run `!CTTInventoryCheck dry_run=true`, `!CTTCaseHousekeeping dry_run=true` and
   `!CTTHygieneFixCheck dry_run=true` once to preview what the first real runs will do.
7. For the DM buttons: add the `msg_person_health_issue` branch to the Slack workflow (CTT Slack
   Webhook README), then set `notify.buttons` to `true` in `CTT - Config`.

## Source

All content lives in git: <https://github.com/vanhecke/ctt-management>. The correlation rules,
job playbooks and dashboard are generated by the scripts in `tools/`; edit those, not the YAML or
JSON.

## Version History (Managed by GoCortex Spellbook)

<!-- spellbook:version-history:start -->
### 1.4.0

- Remediation loop: the hygiene DM asks "Did you fix it?" with the buttons Fixed! / Not a violation (links generated by the playbook, no Cortex login). Fixed! runs the new `CTTHygieneFixCheck`; a fix it can't confirm keeps the issue open and the next DM says what is still wrong. Not a violation closes it as False Positive and tells the CTT channel.
- New `CTT - Hygiene - Fix Check` job (hourly): resolves rule issues whose fix it can verify. Every close carries a note saying why.
- New `CTT - Hygiene - Reminders` job (daily): one digest per owner of their open hygiene issues.
- Tenant Status: closes by way, median time to fix, top fixers, oldest open issue.
- CTT Assistant: `CTTHygieneConfirmFixAction` ("I fixed issue 1234").

### 1.3.0

- `CTT - Marketplace Updates` job and playbooks, imported from the TypeSafe Jev Marketplace Guard: Jev-reviewed pack updates with a run summary in the CTT Slack channel.
- New `CTTSlackPost` script: posts a message to the CTT Slack channel.

### 1.2.0

- The Notify Owner automation rule is enabled on install (`is_auto_enabled`); the Notify Dispatcher job is gone.
- New rule `Policy rule not scoped by your tag` (CTT-TAG-02). The OOTB rule applies to CTT admins too. LAB-01 finds owners through installer creators and policy editors.
- New `CTTOwnerIndex` and `ctt_object_owners` lookup (hourly, with the registry sync).
- The daily sweep is now `CTT - Hygiene - Inventory Check`: only what the rules can't see, with owners from the audit log, skipping objects already in a rule issue.
- New `CTT - Case Housekeeping` job: assigns, reminds and resolves Security cases (CTT-CASE-01, CTT-CASE-02).
- Tenant Status: the topic shows tenant activity only; the canvas has an Automation section with top playbooks and AI agent plans. Open-case counts now use the filtered count.

### 1.1.7

- Notify Dispatcher job (pack uploads to 8.15 skip triggers); the issue goes to In Progress after the DM; deterministic FOUND / RULE / FIX DM template with optional AI text; playbooks adopted on install; re-runs send one DM.

### 1.1.0

- Hygiene issues are assigned to their owner and the owner gets an AI-written Slack DM (CTT - Hygiene - Notify Owner, CTT Slack Webhook).
- CTT - Tenant Status replaces CTT - Weekly Stats: daily Tenant Status canvas and channel topic.

### 1.0.0

- Initial release: guideline monitoring rules, registry sync, daily sweep, weekly stats, CTT - Hygiene dashboard, CTT Assistant agent.

<!-- spellbook:version-history:end -->
