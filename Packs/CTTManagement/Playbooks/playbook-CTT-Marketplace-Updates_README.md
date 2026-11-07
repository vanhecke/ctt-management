Jev-reviewed Marketplace updates: collects newer pack releases, has TypeSafe Jev review each one against the enabled integrations, installs approved updates with their mandatory dependencies and verifies the versions. Held, unresolved or failed updates get one deduplicated review case each, breaking changes that affect an enabled integration get a validation issue, and a summary goes to the CTT Slack channel. Run by the job of the same name (Monday to Thursday, 05:00 Singapore time). Needs the TypeSafe Jev and Core REST API integrations.

Runs `CTTMarketplaceUpdates` (collect, prepare_ai, apply_ai, publish, install, review, summary), the `CTT - Marketplace Release Analysis` sub-playbook for each batch of releases, then `CTTSlackPost` with the run summary.

Needs the `TypeSafe Jev` integration (command `jev-evaluate`) and the `Core REST API` integration. Set the `DryRun` input to `true` to review and report without installing or changing cases.
