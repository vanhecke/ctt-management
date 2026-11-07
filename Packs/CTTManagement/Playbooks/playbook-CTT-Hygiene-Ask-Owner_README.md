Sub-playbook of `CTT - Hygiene - Notify Owner`, looped until the issue is resolved.

1. Clears the previous answer links (`Ask`).
2. Asks **Did you fix it?** by Generated link; in parallel `CTTHygieneAskLinks` waits for the links, `CTTHygieneSendDM` sends the DM with them (Slack buttons with `notify.buttons`) and the issue is set to In Progress.
3. **Fixed** runs `CTTHygieneFixCheck confirm=true`; **Not a violation** runs `CTTHygieneFixCheck false_positive=true`.

An unconfirmed fix leaves `CTT.FixCheck.resolved` false, so the parent loop runs another round whose DM starts with what is still wrong.
