# CTT Assistant

The CTT Assistant is the AI agent of the ASEAN Cortex Team Tenant (CTT). It helps Domain Consultants
(DCs) and CTT admins keep the shared tenant tidy: it explains the CTT guidelines, says who owns what,
shows a DC what they own and what breaks the guidelines, and helps them clean up after a lab. It is
installed by the CTTManagement pack and is public: everyone on the tenant can use it.

## How to use it

1. Open the Agentic Assistant and pick **CTT Assistant** (or click one of its conversation starters).
2. Tell it your email or tag first. It does not know who you are, and it confirms you against the CTT
   registry before it looks up anything of "yours".
3. Ask in plain language. Some answers take a minute or two (your footprint runs the inventory
   check); it says so.

Conversation starters:

- What is my tag and lab range?
- What do I own on this tenant, and does anything break the CTT guidelines?
- Who owns the tag sfi, and what is their lab range?
- List my open Security cases so I can close the finished ones
- Explain guideline CTT-TAG-01 and how to rename my playbook
- I fixed hygiene issue 61001, please close it

## What it can do

| You ask | What it does | Uses |
|---|---|---|
| "What does CTT-LAB-02 say?", "How do I name a script?" | Quotes the guideline by ID and gives an example for your case; the naming table for every object type | Its instructions, the CTT guideline documents (knowledge) |
| "Which guidelines are checked automatically?" | Says which guidelines a correlation rule or the daily inventory check monitors, and how issues close | CTT-Guideline-Coverage (knowledge) |
| "What is my tag and lab range?" | Your primary tag, aliases, lab octet and ranges (10.x.0.0/16, 172.16.x.0/24) | CTTRegistryLookupAction |
| "Who owns tag jva / 10.23.4.5 / octet 7 / `SF - Labs`?" | The registered owner; for an object, the owner of its name prefix. No match means not registered (CTT-GEN-01) | CTTRegistryLookupAction |
| "Who are the CTT admins?" | The people with the admin role in the registry | CTTRegistryLookupAction |
| "What do I own, and is it compliant?" | Your playbooks, scripts, jobs, integration instances, correlation rules, lookups, data collectors, policy profiles, policy rules and untagged endpoints, and every guideline finding for them with the fix | CTTMyFootprintAction (the inventory check, as a dry run) |
| "Why did I get a CTT hygiene DM?", "Which hygiene issues are open for me?" | Lists your open `CTT - Hygiene - …` issues and explains each one and its fix | CortexRunXQLQuery |
| "I fixed issue 48" | Runs the issue's fix check: a verified fix (or a guideline without a check) resolves the issue with a close note; otherwise it says what is still wrong. Asks for your approval first | CTTHygieneConfirmFixAction |
| "My attack chain is done, close my test cases" | Lists your open Security cases, waits for the exact case IDs you name, repeats them, and after your yes resolves them as Security Testing (CTT-CASE-01) | SearchCases, CortexUpdateCase |
| "Are my endpoints OK?" | For each endpoint: lab address inside your range (CTT-LAB-01), your tag on it (CTT-LAB-02), its prevention policy | CortexListEndpoints, CTTRegistryLookupAction |
| "Does jdoe have an account here?" | Confirms a person exists before you contact them | CortexListSystemUsers |
| General Cortex questions | Answers from the Cortex platform documentation | cortex-platform-docs (knowledge) |

## What it never does

- It changes nothing on the tenant except two things you ask for and confirm: resolving your own
  Security Testing cases, and resolving a hygiene issue you say you fixed (after its check).
- It never renames, retags, disables or deletes objects. It explains the fix; you make it.
- It never acts on another DC's objects or cases (CTT-OWN-01) and never edits built-in content
  (CTT-OOTB-01). It tells you who to ask instead.
- It never guesses an owner from a name that only looks similar; the CTT registry decides.

## Approvals

- **Recording a fix** (CTTHygieneConfirmFixAction) is a sensitive action: the Agentic Assistant asks
  you to approve it (in Slack: Approve and Deny buttons).
- **Closing cases** asks for an explicit list of case IDs and a yes in the conversation before it runs.
  The platform does not mark that action as sensitive, so this confirmation comes from the agent's
  instructions.
- Everything the agent runs is logged in the `agentix_agents_actions` dataset (user, prompt, action,
  input).

## Limits

- It works with your permissions: an action you are not allowed to run fails for the agent too.
- It only knows what the CTT registry (Google Sheet) and the tenant say. A person missing from the
  sheet has no tag, no lab range and no Slack DMs.
- The inventory check runs once a day (08:30 SGT). A fix you made today shows in your footprint
  right away, but a daily inventory issue closes at the next run (or when you press Mark as Fixed).
- Data collectors are known from the audit log only: a collector that was edited after it was
  created is not listed (an edit can be a rename). Policy rules are known when they are assigned to
  an installed endpoint.

## For CTT admins: what it is made of

| Part | Content |
|---|---|
| Agent | `ctt-assistant-agent` (CTT Assistant), public, built-in action InvokeLLM |
| Instructions | The ground rules and the guideline index (pack file `ctt-assistant-agent_systeminstructions.md`) |
| Skills | `ctt-guidelines-skill` (guidelines and registry), `ctt-hygiene-skill` (footprint, hygiene issues, fixes), `ctt-lab-housekeeping-skill` (cases, endpoints, users) |
| Custom actions | CTTRegistryLookupAction (script CTTRegistryLookup), CTTMyFootprintAction (CTTMyFootprint), CTTHygieneConfirmFixAction (CTTHygieneFixCheck `confirm=true`, needs approval) |
| System actions | CortexRunXQLQuery, SearchCases, CortexUpdateCase, CortexListEndpoints, CortexListSystemUsers |
| Knowledge | CTT-Guidelines, CTT-Guideline-Coverage and this document (uploaded with the pack), the `CTT Guidelines` collection, Palo Alto's `cortex-platform-docs` |

The custom actions run pack scripts that read the tenant through the Core REST API instance and the
CTT lists. The agent's knowledge only works on XSIAM 4.0 (8.16) or later.
