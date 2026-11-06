| join type = left (dataset = ctt_registry | alter obj_tag = ctt_tag, obj_owner = owner_email, obj_owner_role = role | fields obj_tag, obj_owner, obj_owner_role) as ro ro.obj_tag = obj_tag
| filter object_kind not in ("AITask", "CaseField", "IssueField", "Credentials", "KnowledgeSource", "Investigation", "Indicator", "Entry", "War Room", "Whitelist", "Content", "Execute")
