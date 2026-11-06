# CTT Guidelines: ASEAN Cortex Team Tenant

| | |
|---|---|
| Tenant | `japac-ctt-x5-asean` ("cttasean"), Cortex XSIAM |
| Who it is for | ASEAN Domain Consultants (DCs) building demos, tests and labs |
| Owned by | The CTT admins |
| Questions | The team Slack channel, or ask the CTT Assistant agent |
| Source | Git repo `vanhecke/ctt-management`, file `Knowledge/CTTManagement/CTT-Guidelines.md` |
| Monitoring status | See `CTT-Guideline-Coverage.md` |

CTT means Cortex Team Tenant. The tenant is shared: a dozen people build on it at once, and
everyone wants to demo from a clean tenant. These guidelines keep it that way. Every guideline has
a stable ID (`CTT-<AREA>-<nn>`). Monitoring, health issues and the CTT Assistant all refer to
guidelines by ID.

**Status.** *Active* guidelines apply today. *Proposed* guidelines are under review by the CTT
admins and are not monitored yet.

## The short version

1. Get your tag first, and put it on everything you create (`CTT-GEN-01`, `CTT-TAG-01`).
2. Only change your own objects (`CTT-OWN-01`).
3. Never edit built-in or marketplace content; duplicate it (`CTT-OOTB-01`).
4. Leave centrally managed settings to the CTT admins (`CTT-CEN-01`).
5. Build your lab in your own IP range (`CTT-LAB-01`).
6. Close your Security Testing cases when your attack chain is done (`CTT-CASE-01`).

## Your tag

Every DC owns tags, listed in the CTT registry: a Google Sheet maintained by the CTT admins and
synced into the tenant every 6 hours.

- Your **primary tag** is your email username, for example `jvanhecke`.
- You also get a short **alias**, usually three letters, for example `jva`. Both are yours; use
  whichever you like.
- Tags are not case sensitive. `JVA` and `jva` are the same tag.
- `CTT` is reserved for central content owned by the CTT admins.
- Your **lab range** is `10.<octet>.0.0/16`, where the octet is your number in the registry.
- The registry also records your Slack member ID and whether you are a CTT admin.

The registry sheet has two tabs: `ctt_asean_users` (tag, octet, owner_email, owner_name,
slack_id, ctt_admin, active) and `ctt_asean_extra_tags` (tag, owner_email, owner_name,
original_tag). Ask a CTT admin to add or change a row.

## Guidelines

### GEN: General

**CTT-GEN-01: Register before you build.** *Active*
Ask a CTT admin for your tag and lab range before you create anything. Objects without a
registered tag cannot be traced back to an owner.

**CTT-GEN-02: Announce disruptive work.** *Proposed*
Post in the team channel before you do something others will notice: large ingestion tests,
tenant-wide content changes, agent upgrades, isolating endpoints, or anything that floods the
issues and cases tables.

**CTT-GEN-03: No real customer data or secrets.** *Proposed*
Use sample, synthetic or anonymised data. Don't store customer logs, credentials or personal data
in the tenant, its lists or its knowledge sources.

### TAG: Tags and naming

**CTT-TAG-01: Prefix object names with your tag.** *Active*
Start the name of every object you create with `<tag> - `, for example
`jvanhecke - Phishing triage`. This applies to:

- Playbooks, scripts, jobs, lists
- Dashboards, widgets, reports and report templates, saved XQL queries (query library)
- Correlation rules, BIOCs, scheduled queries
- Endpoint profiles and policy rules (prevention, extensions, agent settings, XDR collectors)
- FIM rule groups, host firewall rule groups, device control profiles
- Cloud workload and posture rules
- Endpoint groups, asset groups, saved views and filters
- Integration instances, engines, Broker VMs, agent installation packages
- AI agents and AI actions you build

Names that cannot hold spaces use `<tag>_<name>` instead: scripts (`jvanhecke_GetLabUsers`),
lookup tables and other datasets (`jvanhecke_lab_assets`, lower case).

**CTT-TAG-02: Set your tag on objects that have a tag field.** *Active*
Where an object has a tag or label field, add your tag to it. This applies to:

- Playbooks (the playbook *Tags* field)
- Endpoint policies and vulnerability policies
- Case and issue layout rules
- Automation rules (triggers)

**CTT-TAG-03: Tag custom parsing rules, modeling rules and list entries in a comment.** *Active*
Rules and list entries have no name of their own on the tenant, so mark them in a comment:

- Parsing and modeling rules: a comment line `// <tag>: <what this rule is for>` above your
  rule block.
- Lists, including entries you add to built-in lists: put your tag in the list description, or
  in a comment next to each entry you add.

**CTT-TAG-04: Use only your own tags.** *Active*
Never create objects with a tag that is not yours in the registry. Use `CTT` only if you are a CTT
admin building central content.

### OWN: Ownership

**CTT-OWN-01: Don't change other people's objects.** *Active*
Don't edit, rename, disable or delete an object whose tag belongs to someone else. Ask the owner
(look them up in the registry, or ask the CTT Assistant), or duplicate the object under your own
tag.

### OOTB: Built-in and marketplace content

**CTT-OOTB-01: Don't edit built-in content; duplicate it.** *Active*
Built-in (out-of-the-box) and marketplace content is shared by everyone, and pack updates
overwrite it. This includes playbooks, scripts, correlation rules, dashboards, layouts, BIOCs and
analytics rules. To customise one, duplicate it, give the copy your tag (`CTT-TAG-01`), and change
the copy. Don't detach or adopt marketplace playbooks.

**CTT-OOTB-02: Don't edit built-in AI agents.** *Active*
Leave the Palo Alto Networks agents (Case Investigation, Threat Intel, IT, …) as they are. Build
your own agent with your tag in its name.

### CEN: Centrally managed

**CTT-CEN-01: Leave centrally managed areas to the CTT admins.** *Active*
Only CTT admins change these:

- CIE
- The VirusTotal integration
- Tenant settings (Settings > Configurations)
- The marketplace: installing, updating and uninstalling content packs
- SSO, RBAC, roles, user groups and permission testing
- The Slack bot integration
- XTI and TIM rules
- Central content (anything named or tagged `CTT`)

Need a pack installed or a setting changed? Ask in the team channel.

**CTT-CEN-02: Create API keys with an expiry date and your tag.** *Proposed*
Give every API key you create an expiration date, the lowest role that works, and your tag in its
comment. Delete it when you are done.

### LAB: Lab network and endpoints

**CTT-LAB-01: Build your lab in your own IP range.** *Active*
Put the machines, broker VMs and collectors of your lab in `10.<x>.0.0/16`, where `x` is your
`lab_octet` in the registry. Never use another DC's range.

**CTT-LAB-02: Tag your endpoints.** *Proposed*
Add your tag as an endpoint tag on every agent you install, so endpoints, policies and cases can be
traced to you. Scope your policies to your own endpoints (`CTT-TAG-02`).

**CTT-LAB-03: Remove what you no longer use.** *Proposed*
Uninstall agents, delete broker VMs and engines, and disable collectors once a lab is finished.

### CASE: Cases and issues

**CTT-CASE-01: Close Security Testing cases when your attack chain is done.** *Active*
When you finish a test or demo attack chain, resolve its cases with the resolution reason
*Security Testing*. Open test cases bury everyone else's demos.

**CTT-CASE-02: Assign your test cases to yourself.** *Proposed*
While you are testing, assign the cases your lab creates to yourself so others can see who is
working on them.

### LIFE: Lifecycle

**CTT-LIFE-01: Clean up after yourself.** *Proposed*
Delete objects you no longer need. Objects untouched for 90 days may be flagged for review.

**CTT-LIFE-02: Hand over when you leave.** *Proposed*
Before you leave the team, delete your objects or hand them over to another DC, who re-tags them.

## How monitoring works

- The CTT Management pack watches the management audit log and runs a daily sweep.
- When a guideline is broken, it raises a **health issue** named
  `CTT - Hygiene - <guideline ID> - <what happened>`. Each one appears in the Issues table and
  opens its own case, both in the **Health** domain, apart from the Security cases you demo with.
- The issue is **assigned to you** when it is about something you did or own, and you get a short
  **Slack DM** from the CTT workflow explaining what was found, the guideline, how to fix it, and a
  link to the issue. At most three DMs per person per day.
- Nothing on the tenant is changed or deleted automatically. You fix the object; the daily sweep
  closes its own issues once things are fixed.
- If something was intended (a test, a demo), reply in the team channel and a CTT admin resolves
  the issue.
- The **Tenant Status** canvas and the topic of the team channel show the tenant's health every
  morning, and the `CTT - Hygiene` dashboard has the details.
- `CTT-Guideline-Coverage.md` lists which guidelines are monitored and how.

## Getting help

- Ask in the team Slack channel.
- Ask the CTT Assistant agent in the Agentic Assistant (once the tenant runs XSIAM 4.0), or tag
  the Cortex bot in Slack and pick the CTT Assistant.
- To change your tag or lab range, ask a CTT admin to update the registry.

## Quick reference: naming

| Object | Format | Example |
|---|---|---|
| Playbook | `<tag> - <name>`, plus tag in the Tags field | `jvanhecke - Phishing triage` |
| Script | `<tag>_<Name>` | `jvanhecke_GetLabUsers` |
| Job, list, dashboard, widget, report | `<tag> - <name>` | `SF - Weekly lab report` |
| Correlation rule, BIOC, scheduled query | `<tag> - <name>` | `SF - Mimikatz on lab DC` |
| Lookup table or dataset | `<tag>_<name>` (lower case) | `sf_lab_assets` |
| Endpoint profile or policy rule | `<tag> - <name>` | `SF - Labs` |
| Integration instance, engine, Broker VM | `<tag> - <name>` | `jvanhecke - jev` |
| Parsing or modeling rule | `// <tag>: <purpose>` comment | `// SF: fortigate lab parsing` |
| List entry in a built-in list | Tag in a comment or the description | |
| Endpoint | Endpoint tag `<tag>` | |

## Changelog

| Date | Change |
|---|---|
| 2026-11-05 | First draft: guideline IDs, Active and Proposed guidelines |
| 2026-11-06 | Your tag: primary tag plus alias, registry sheet layout |
| 2026-11-06 | How monitoring works: issues are assigned to their owner, Slack DM, Tenant Status canvas |
