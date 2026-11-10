Runs on every CTT hygiene health issue (trigger `CTT - Hygiene - Notify Owner`).

1. **Same problem already known?** `CTTHygieneDuplicateCheck` looks for another open issue about the same endpoint, user or object, or one marked a false positive in the last `notify.false_positive_days` days. If so, the issue is closed as Duplicate Issue.
2. **Already fixed?** `CTTHygieneFixCheck resolve=false` runs the guideline's automatic check. If it sees the fix (for example a playbook with the owner's tag in its Tags field), the issue is closed with a note saying why, before anyone is assigned or notified.
3. `CTTHygieneTriage` finds the owner from the issue's `[owner: ...]` marker, their name, role and Slack ID in the CTT registry, and the guideline; `core-update-issue` assigns the issue and sets it In Progress.
4. In parallel:
   - **Ask the owner:** the `CTT - Hygiene - Ask Owner` sub-playbook (DM with Mark as Fixed / Mark as False Positive, the answer and the fix check on it). When its result closes the issue, the next task does.
   - **Watch:** `CTTHygieneFixCheck watch=true`, a scheduled command (polling) that checks every hour and closes the issue once the check sees it fixed.
5. Before either of those closes, `CTTHygieneSendDM closed=true` thanks the owner and quotes the close note (same DM gate; it doesn't count toward the daily limit). Duplicates and issues that were already fixed close without a DM: the owner was never asked.

An issue without an owner only gets the watch. The issue is always closed by the last task of a branch (`closeInvestigation` with the close note), never halfway; closing it stops the other branch. Assigning continues on error. DMs follow `notify.mode` (`off`, `allowlist`, `admins_only`, `all`) and the daily limit in `CTT - Config`.
