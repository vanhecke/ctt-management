Runs on every CTT hygiene health issue (trigger `CTT - Hygiene - Notify Owner`).

1. `CTTHygieneTriage` finds the owner from the issue's `[owner: ...]` marker, their name, role and Slack ID in the CTT registry, and the guideline.
2. `core-update-issue` assigns the issue to the owner's email.
3. With `notify.use_ai`, the `CTTHygieneMessagePrompt` AI task writes the DM text; otherwise the FOUND / RULE / FIX template from triage is used.
4. **Round 1**: **Did you fix it?** is asked by Generated link (no timeout); in parallel `CTTHygieneAskLinks` gets its links and `CTTHygieneSendDM` sends the DM with the buttons **Mark as Fixed**, **Mark as False Positive** and **View Issue** (`notify.buttons`; otherwise links in the text). The issue is set to In Progress.
5. **Watch** (parallel): `CTTHygieneFixCheck watch=true` checks every hour and closes the issue once the check sees it fixed (guidelines with an automatic check).
6. **Mark as Fixed** runs `CTTHygieneFixCheck confirm=true resolve=false`: a verified fix (or a guideline without a check) closes the issue; otherwise **round 2** asks once more with a DM that says what is still wrong, and after a second unconfirmed answer a last DM says the issue closes by itself once fixed.
7. **Mark as False Positive** runs `CTTHygieneFixCheck false_positive=true resolve=false` (a post in the CTT channel) and closes the issue as False Positive.

Without a DM (no owner, DMs off or the daily limit) only the watch runs. The issue is always closed by the last task of a branch (`closeInvestigation` with the close note), never halfway. Assigning and the AI step continue on error. DMs follow `notify.mode` (`off`, `admins_only`, `all`) and the daily limit in `CTT - Config`.
