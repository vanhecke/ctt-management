Sub-playbook of `CTT - Hygiene - Notify Owner`; runs in its context (CTT.Triage) and writes its result to CTT.FixCheck (`close`, `reason`, `note`). The parent closes the issue.

1. With `notify.use_ai`, the `CTTHygieneMessagePrompt` AI task writes the DM text; otherwise the FOUND / RULE / FIX template from triage is used.
2. **Round 1**: **Did you fix it?** is asked by Generated link (no timeout); in parallel `CTTHygieneAskLinks` gets its links and `CTTHygieneSendDM` sends the DM with the buttons **Mark as Fixed**, **Mark as False Positive** and **View Issue** (`notify.buttons`; otherwise links in the text). Without a DM (DMs off, not on the allowlist, no Slack ID, daily limit) only the DM is skipped.
3. **Mark as Fixed** runs `CTTHygieneFixCheck confirm=true resolve=false`: a verified fix (or a guideline without a check) ends the sub-playbook with `close`; otherwise **round 2** asks once more with a DM that says what is still wrong, and after a second unconfirmed answer a last DM says the issue closes by itself once fixed.
4. **Mark as False Positive** runs `CTTHygieneFixCheck false_positive=true resolve=false` (a post in the CTT channel) and ends with `close` (False Positive).
