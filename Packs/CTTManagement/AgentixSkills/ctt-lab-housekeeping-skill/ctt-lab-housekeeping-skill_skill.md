# CTT lab housekeeping

## Close finished Security Testing cases (CTT-CASE-01)

1. Find the signed-in user's open Security cases with <action=SearchCases>:
   case_domains `DOMAIN_SECURITY`, not_status `resolved`, assignee the user's email, limit 50,
   sorted by creation time. If they have none assigned, ask whether to search by host name or case
   name instead (hosts or case_name filters); many lab cases are unassigned.
2. Show them as a table: case ID, name, severity, created, assignee.
3. Ask which ones are finished test or demo cases. Wait for an explicit list of case IDs, or an
   explicit "all of these". Never pick cases yourself.
4. Repeat the exact IDs back and ask for a yes. Only after the yes, call
   <action=CortexUpdateCase> with case_ids set to those IDs, status `resolved`, resolve_reason
   `security_testing`, and resolved_comment "Closed by the CTT Assistant at the request of <email>:
   attack chain finished (CTT-CASE-01)."
5. Report what was resolved. If an update failed, say which ID and why.

Only resolve cases the user confirms are their own test cases. If a case clearly belongs to
someone else (assigned to another person, or a host outside their lab range), leave it and tell
them who to ask (CTT-OWN-01).

## Close Health cases whose issues are fixed

Health cases hold tenant health issues: CTT hygiene issues, Marketplace Guard reviews and platform
health issues. A Health case may be closed once its issues are fixed or already resolved.

1. Find them with <action=SearchCases>: case_domains `DOMAIN_HEALTH`, not_status `resolved`, or the
   case IDs the user gives. Show case ID, name, issues and status.
2. Per case, by its name:
   - `CTT - Hygiene - ...`: the hygiene issues close through their fix check. Use
     <action=CTTHygieneConfirmFixAction> with the issue IDs (the case closes with its issues). Only
     the user's own hygiene issues, as in the CTT Hygiene skill. Daily inventory issues ("The
     inventory check found ...") close at the next inventory run instead; don't close their case by
     hand.
   - `Marketplace Guard - manual review: <pack> <current> -> <target>`: use
     <action=CTTMarketplaceCloseReviewAction> with the pack ID and the target version from the name.
     It checks that the pack is installed at the target; if not, the case stays open and you say which
     version is installed.
   - Any other Health case: ask the user what was fixed, unless all its issues are already resolved.
     Then resolve it with <action=CortexUpdateCase>: status `resolved`, resolve_reason `other`,
     resolve_all_alerts `true`, resolved_comment "Closed by the CTT Assistant at the request of
     <email>: <what was fixed>."
3. As for Security cases: wait for the exact case IDs, repeat them, and act only after the user's yes.
   Report what was resolved and what stayed open, and why.

## Check my endpoints (CTT-LAB-01)

1. Get the user's lab range with <action=CTTRegistryLookupAction>.
2. List endpoints with <action=CortexListEndpoints>: ip_list for addresses they give you, or
   hostname for their machines.
3. For each endpoint, say whether its lab address (10.x or 172.16.x) is inside their range, whether it carries
   their tag, and which prevention policy it uses. An address in someone else's range breaks
   CTT-LAB-01. Endpoints outside 10.0.0.0/8 and 172.16.0.0/16 (home networks) are only checked for the tag.

## Who else is around?

<action=CortexListSystemUsers> lists the tenant's users. Use it to confirm a person exists before
suggesting they contact someone, never to change anything.
