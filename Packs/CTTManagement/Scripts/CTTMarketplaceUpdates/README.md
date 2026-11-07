Jev-reviewed Marketplace updates for the tenant, imported from the TypeSafe Jev Marketplace Guard.
The `CTT - Marketplace Updates` playbook runs it one action at a time:

| Action | What it does |
|---|---|
| collect | Lists installed packs, their newer Marketplace releases and the enabled integration instances. |
| prepare_ai, unpack_ai, wrap_ai, apply_ai | Batch the release evidence for TypeSafe Jev (`jev-evaluate`) and validate its answers. |
| publish | One deduplicated validation issue per breaking change that affects an enabled integration. |
| install | Installs approved updates with their mandatory dependencies through the tenant Marketplace and verifies each exact version. |
| review | One deduplicated review issue and case per held, unresolved or failed update; resolves stale ones. |
| summary | A plain-text run summary for the CTT Slack channel (`TypeSafeJevMarketplace.Summary.text`), posted by `CTTSlackPost`. |
| pack_detail, close_review | Manual use: review details for one pack, and closing its review once the update is verified. |

State lists keep their `TypeSafeJevMarketplace*` names, so the ledgers of runs before the import stay
valid. Needs the `Core REST API` integration (`core-api-get`, `core-api-post`). JavaScript, so it runs
in the server's engine without a Docker image.
