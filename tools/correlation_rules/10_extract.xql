dataset = management_auditing
| filter management_auditing_result = ENUM.MANAGEMENT_AUDIT_SUCCESS
| filter email != null and email != "" and email not in ("Palo Alto Networks", "N/A", "Xpanse Development", "Cortex Automation")
| filter user_name = null or user_name !~= "^(Public API - [0-9]+|APIKeyUser_[0-9]+|XSIAM Automation|Cortex Automation)$"
| alter actor_email = if(email contains "@", lowercase(email), null), actor_name = lowercase(user_name)
| alter object_kind = coalesce(arrayindex(regextract(subtype, "^[A-Za-z ]+ - (.+)$"), 0), replex(to_string(management_auditing_type), "^(MANAGEMENT_AUDIT_|management_auditing_type_)", ""))
| alter action = if(subtype ~= "^(Add|Upload|Copy|Create|New|Save as new|Import)" or subtype ~= "^(Create|Upload lookup|Addition)", "create", if(subtype ~= "(Delete|Remove)", "delete", if(subtype ~= "(Edit|Change|Update|Modif|Adopt|Detach|Enable|Disable|Rename|Scope Edit)", "modify", "other")))
| alter object_name = coalesce(
    arrayindex(regextract(description, "ClonedPlaybookName: (.+?), ID:"), 0),
    arrayindex(regextract(description, "playbookName: (.+?), ID:"), 0),
    arrayindex(regextract(description, "scriptName: (.+?), (?:removed from|ID):"), 0),
    arrayindex(regextract(description, "aiTaskName: (.+?), "), 0),
    arrayindex(regextract(description, "CredentialsName: (.+?), ID:"), 0),
    arrayindex(regextract(description, "ModuleName: ([^,]+)"), 0),
    arrayindex(regextract(description, "ModuleBrand: (.+?), ID:"), 0),
    arrayindex(regextract(description, "Layout (?:created|edited|deleted) - Name: (.+?), ID:"), 0),
    arrayindex(regextract(description, "CaseField (?:created|edited|deleted) - Name: (.+?), Type:"), 0),
    arrayindex(regextract(description, "Name: (.+?), JobID:"), 0),
    arrayindex(regextract(description, "JobID: [^,]+, Name: (.+?), ID:"), 0),
    arrayindex(regextract(description, "^name: (.+?), ID:"), 0),
    arrayindex(regextract(description, "^Name: (.+?), ID:"), 0),
    arrayindex(regextract(description, "dashboard '(.+?)'"), 0),
    arrayindex(regextract(description, "(?:BIOC|Correlations? rule|IOC|Analytics BIOC|Attack Surface Rule) [a-z]+ - name: (.+?),? id: "), 0),
    arrayindex(regextract(description, " profile (.+?) was (?:created|edited|deleted)"), 0),
    arrayindex(regextract(description, "policy rule (.+?) (?:with target|updated|scope updated|was deleted|was created|created|was)"), 0),
    arrayindex(regextract(description, "^Rule (.+?) status changed"), 0),
    arrayindex(regextract(description, "Security Control: [^,]+, (.+)$"), 0),
    arrayindex(regextract(description, "Connector Template '?(.+?)'? (?:created|deleted|modified)"), 0),
    arrayindex(regextract(description, "Endpoint group '(.+?)'"), 0),
    arrayindex(regextract(description, "lookup dataset called (\S+)"), 0),
    arrayindex(regextract(description, "Dataset (\S+) of type"), 0),
    arrayindex(regextract(description, "(?:query|macro) '(.+?)'"), 0),
    arrayindex(regextract(description, "report template\(?s?\)? '(.+?)'"), 0),
    arrayindex(regextract(description, "Cloud Security Rule '(.+?)'"), 0),
    arrayindex(regextract(description, "installation package '(.+?)'"), 0),
    arrayindex(regextract(description, "script, name: (.+?), description"), 0),
    arrayindex(regextract(description, "^Edit (.+?), script id"), 0),
    if(object_kind in ("Agent", "Action", "KnowledgeSource", "JobCenter"), arrayindex(regextract(description, "^(.+?)(?:, ID: .*)?$"), 0), null)
  )
| alter obj_tag = lowercase(arrayindex(regextract(object_name, "^\s*([A-Za-z0-9]{2,16})\s*[-_]"), 0))
| alter object_kind = if(object_kind = "RULES", if(description ~= "^Correlations? rule", "Correlation rule", if(description ~= "^BIOC", "BIOC rule", if(description ~= "^IOC", "IOC rule", "Detection rule"))), if(object_kind = "DISTRIBUTIONS", "Agent installer", if(object_kind = "POLICY_RULES", "Policy rule", if(object_kind = "POLICY_PROFILES", "Policy profile", if(object_kind = "DASHBOARD", "Dashboard", if(object_kind = "LOOKUPS", "Lookup dataset", if(object_kind = "DATASETS", "Dataset", if(object_kind = "CLOUDSEC_RULE", "Cloud security rule", object_kind))))))))
