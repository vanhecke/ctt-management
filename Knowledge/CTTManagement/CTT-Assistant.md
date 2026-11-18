# CTT Assistant

The CTT Assistant is the AI agent of the ASEAN Cortex Team Tenant (CTT). It helps Domain Consultants
(DCs) and CTT admins keep the shared tenant tidy: it explains the CTT guidelines, says who owns what,
shows a DC what they own and what breaks the guidelines, and helps them clean up after a lab. It is
installed by the CTTManagement pack and is public: everyone on the tenant can use it.

## How to use it

Open the Agentic Assistant, pick **CTT Assistant**, and ask in plain language or click a conversation
starter. It knows who you are (the signed-in user) and looks you up in the CTT registry for your tags
and lab range. Some answers take a minute or two (your footprint runs the inventory check); it says so.

Conversation starters:

- What are my tags and my IP ranges?
- What do I own on this tenant, and does anything break the CTT guidelines?
- Which CTT hygiene issues are open for me, and how do I fix them?
- List my open cases so I can close the finished ones
- Explain guideline CTT-TAG-01 and how to rename my playbook
- I fixed my hygiene issue, please check it and close it

## What it can do

| You ask | What it does | Uses |
|---|---|---|
| "What does CTT-LAB-02 say?", "How do I name a script?" | Quotes the guideline by ID and gives an example for your case; the naming table for every object type | Its instructions, the CTT guideline documents (knowledge) |
| "Which guidelines are checked automatically?" | Says which guidelines a correlation rule or the daily inventory check monitors, and how issues close | CTT-Guideline-Coverage (knowledge) |
| "What are my tags and my IP ranges?" | Your primary tag, aliases, lab octet and ranges (10.x.0.0/16, 172.16.x.0/24) | CTTRegistryLookupAction |
| "Who owns tag jva / 10.23.4.5 / octet 7 / `SF - Labs`?" | The registered owner; for an object, the owner of its name prefix. No match means not registered (CTT-GEN-01) | CTTRegistryLookupAction |
| "Who are the CTT admins?" | The people with the admin role in the registry | CTTRegistryLookupAction |
| "What do I own, and is it compliant?" | Your playbooks, scripts, jobs, integration instances, correlation rules, lookups, data collectors, policy profiles, policy rules and untagged endpoints, and every guideline finding for them with the fix | CTTMyFootprintAction (the inventory check, as a dry run) |
| "Which hygiene issues are open for me?" | Lists your open `CTT - Hygiene - …` issues and explains each one and its fix | CortexRunXQLQuery |
| "I fixed issue 1234" | Runs the issue's fix check: a verified fix (or a guideline without a check) resolves the issue and its case with a close note; otherwise it says what is still wrong. Asks for your approval first. For a daily inventory issue it shows which items are fixed; that issue closes at the next inventory run | CTTHygieneConfirmFixAction, CTTMyFootprintAction |
| "My attack chain is done, close my test cases" | Lists your open Security cases, waits for the exact case IDs you name, repeats them, and after your yes resolves them as Security Testing (CTT-CASE-01) | SearchCases, CortexUpdateCase |
| "Core 3.7.2 is installed, close the Marketplace Guard case" | Checks that the pack is installed at the target version, then resolves the review issue and its case and marks the review done. Asks for your approval first | CTTMarketplaceCloseReviewAction |
| "Close health case 32, I fixed it" | Closes a Health case whose issues are fixed or already resolved, after you say what was fixed and confirm the case ID | SearchCases, CortexUpdateCase |
| "Are my endpoints OK?" | For each endpoint: lab address inside your range (CTT-LAB-01), your tag on it (CTT-LAB-02), its prevention policy | CortexListEndpoints, CTTRegistryLookupAction |
| "Does jdoe have an account here?" | Confirms a person exists before you contact them | CortexListSystemUsers |
| General Cortex questions | Answers from the Cortex platform documentation | cortex-platform-docs (knowledge) |

## What it never does

- It changes nothing on the tenant except what you ask for and confirm: recording a hygiene fix,
  resolving your finished Security Testing cases, and resolving Health cases whose issues are fixed.
- It never renames, retags, disables or deletes objects. It explains the fix; you make it.
- It never acts on another DC's objects or test cases (CTT-OWN-01) and never edits built-in content
  (CTT-OOTB-01). It tells you who to ask instead.
- It never guesses an owner from a name that only looks similar; the CTT registry decides. Every DC
  is an administrator on the tenant, so permissions say nothing about ownership.

## Approvals

- **Recording a fix** (CTTHygieneConfirmFixAction) and **closing a Marketplace review**
  (CTTMarketplaceCloseReviewAction) are sensitive actions: the Agentic Assistant asks you to approve
  them.
- **Closing other cases** (CortexUpdateCase) asks for an explicit list of case IDs and a yes in the
  conversation before it runs. The platform does not mark that action as sensitive, so this
  confirmation comes from the agent's instructions.
- Everything the agent runs is logged in the `agentix_agents_actions` dataset (user, prompt, action,
  input).

## Limits

- It only knows what the CTT registry (Google Sheet) and the tenant say. A person missing from the
  sheet has no tag, no lab range and gets no hygiene DMs.
- The inventory check runs once a day (08:30 SGT). A fix you made today shows in your footprint
  right away, but a daily inventory issue ("The inventory check found …") closes at the next run.
- Data collectors are known from the audit log only: a collector that was edited after it was
  created is not listed (an edit can be a rename). Policy rules are known when they are assigned to
  an installed endpoint.
- It is used in the Agentic Assistant only. The CTT Slack channel gets one-way posts and DMs from the
  pack (webhook); you cannot chat with the agent from Slack.

## For CTT admins: what it is made of

| Part | Content |
|---|---|
| Agent | `ctt-assistant-agent` (CTT Assistant), public, built-in action InvokeLLM |
| Instructions | The ground rules and the guideline index (pack file `ctt-assistant-agent_systeminstructions.md`) |
| Skills | `ctt-guidelines-skill` (guidelines and registry), `ctt-hygiene-skill` (footprint, hygiene issues, fixes), `ctt-lab-housekeeping-skill` (Security and Health cases, endpoints, users) |
| Custom actions | CTTRegistryLookupAction (script CTTRegistryLookup), CTTMyFootprintAction (CTTMyFootprint), CTTHygieneConfirmFixAction (CTTHygieneFixCheck `confirm=true`, needs approval), CTTMarketplaceCloseReviewAction (CTTMarketplaceUpdates `action=close_review`, needs approval) |
| System actions | CortexRunXQLQuery, SearchCases, CortexUpdateCase, CortexListEndpoints, CortexListSystemUsers |
| Knowledge | CTT-Guidelines, CTT-Guideline-Coverage and this document (uploaded with the pack), the `CTT Guidelines` collection, Palo Alto's `cortex-platform-docs` |

The custom actions run pack scripts that read the tenant through the Core REST API instance and the
CTT lists. The agent's knowledge only works on XSIAM 4.0 (8.16) or later.
