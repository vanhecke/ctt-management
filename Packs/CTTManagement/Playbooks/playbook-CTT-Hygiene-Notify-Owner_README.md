Runs on every CTT hygiene health issue (trigger `CTT - Hygiene - Notify Owner`).

1. `CTTHygieneTriage` finds the owner from the issue's `[owner: ...]` marker, their name, role and Slack ID in the CTT registry, and the guideline.
2. `core-update-issue` assigns the issue to the owner's email.
3. With `notify.use_ai`, the `CTTHygieneMessagePrompt` AI task writes the DM text; otherwise the FOUND / RULE / FIX template from triage is used.
4. **Did you fix it?** is asked by Generated link (no timeout). In parallel `CTTHygieneAskLinks` waits for its links and `CTTHygieneSendDM` sends the DM: as Slack buttons **Fixed!**, **Not a violation** and **Open issue** with `notify.buttons`, otherwise with the links in the text. The issue is set to In Progress.
5. **Fixed!** runs `CTTHygieneFixCheck confirm=true`: a verified fix (or a guideline without a check) is resolved with a close note; otherwise the question is asked again and the next DM says what is still wrong.
6. **Not a violation** runs `CTTHygieneFixCheck false_positive=true`: a post in the CTT channel, then Resolved - False Positive with a close note.

The hourly `CTT - Hygiene - Fix Check` job also resolves issues it finds fixed; resolving the issue stops this playbook. Assigning and the AI step continue on error. DMs follow `notify.mode` (`off`, `admins_only`, `all`) and the daily limit in `CTT - Config`.
