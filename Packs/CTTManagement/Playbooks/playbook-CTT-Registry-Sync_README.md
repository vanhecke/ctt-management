Syncs the CTT registry (tags, lab octets, Slack IDs, admins) from the Google Sheet into the ctt_registry lookup dataset and the 'CTT - Registry' list, then updates the ctt_object_owners lookup (who created and last changed each object) from the audit log. Run by the job of the same name every hour.

Runs `CTTRegistrySync`, then `CTTOwnerIndex`.
