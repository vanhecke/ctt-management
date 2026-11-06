Runs on every CTT hygiene health issue (trigger `CTT - Hygiene - Notify Owner`).

1. `CTTHygieneTriage` finds the owner from the issue's `[owner: ...]` marker, their name, role and Slack ID in the CTT registry, and the guideline.
2. `core-update-issue` assigns the issue to the owner's email.
3. The `CTTHygieneMessagePrompt` AI task writes a short Slack DM.
4. `CTTHygieneSendDM` sends it through the CTT Slack Webhook integration.

Assigning and the AI step continue on error. DMs follow `notify.mode` (`off`, `admins_only`, `all`) and the daily limit in `CTT - Config`.
