# Correlation rule sources

`gen_correlation_rules.py` writes `Packs/CTTManagement/CorrelationRules/*.yml` from the rule specs
it contains and the shared XQL fragments here. Edit the specs or fragments, never the YAML, then:

```bash
uv run --with pyyaml python3 tools/correlation_rules/gen_correlation_rules.py   # from content/
```

- `10_extract.xql`: human `management_auditing` events, with `actor_email`, `actor_name`,
  `object_kind`, `action` (create, modify, delete, other), `object_name` parsed from the
  description, and `obj_tag` (the name prefix before `-`, ` - ` or `_`).
- `20_actor_join.xql`: joins the `ctt_registry` lookup for the actor (`actor`,
  `actor_is_admin`, `actor_registered`).
- `30_object_join.xql`: joins it for the object tag (`obj_owner`,
  `obj_owner_role`), and drops object kinds that carry no owner tag.

Compare `management_auditing_type` with `ENUM.MANAGEMENT_AUDIT_X`. A quoted string never matches,
and xql-lint does not warn about it.
