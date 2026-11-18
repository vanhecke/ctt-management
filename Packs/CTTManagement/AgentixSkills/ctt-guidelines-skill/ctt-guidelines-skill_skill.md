# CTT guidelines and registry

## Explain a guideline

Quote the guideline by ID from your instructions, then give the user one concrete example for
their case. If they ask about something the guidelines do not cover, say so; don't invent a rule.
For the naming format, use this table:

| Object | Format |
|---|---|
| Playbook | `<tag> - <name>`, and the tag in the playbook Tags field |
| Script | `<tag>_<Name>`, or the tag in the script Tags field |
| Job | `<tag> - <name>`, or the tag in the job Tags field |
| Data collector (HTTP collector) | `<tag> - <name>` |
| List, dashboard, widget, report, correlation rule, BIOC, scheduled query | `<tag> - <name>` |
| Lookup table or dataset | `<tag>_<name>` in lower case |
| Endpoint profile, policy rule, integration instance, engine, Broker VM | `<tag> - <name>` |
| Parsing or modeling rule | a comment `// <tag>: <purpose>` |
| Endpoint | the tag as an endpoint tag |

## Look someone up

Use <action=CTTRegistryLookupAction> with whatever the user gave you:

- a tag or alias (`jvanhecke`, `jva`): returns that person with all their tags;
- an email or part of a name;
- a lab octet (`7`) or an address (`10.7.4.20`): returns who owns that range;
- an object name: take the prefix before ` - ` or `_` and look that up as a tag.

No match means the tag or person is not registered. Say so, and point to CTT-GEN-01: a CTT admin
adds them to the registry sheet. Never treat a near match as the owner.

To list the CTT admins, look up with an empty query and keep the people whose role is admin.

## "What are my tags and my IP ranges?"

Look up the signed-in user's email and answer with their primary tag, their aliases, their lab
octet and both lab ranges (10.<x>.0.0/16 and 172.16.<x>.0/24). Remind them to prefix everything they
create with one of their tags and to tag their endpoints. If they are not in the registry, say so and
point to CTT-GEN-01.
