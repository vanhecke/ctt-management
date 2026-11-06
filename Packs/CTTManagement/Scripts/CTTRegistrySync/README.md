Syncs the CTT registry into the tenant.

Reads the Google Sheet configured in the `CTT - Config` list (`registry.spreadsheet_id`, tabs
`ctt_asean_users` and `ctt_asean_extra_tags`) through the GoogleSheets integration. If the sheet
cannot be read, it falls back to the CSV in the `CTT - Registry Source` list. It writes one row per
tag to the `ctt_registry` lookup dataset (created on first run) and to the `CTT - Registry` list.
Extra tags inherit their owner's octet, Slack ID and admin flag. The central tags from
`registry.central_tags` (default `ctt`) are added with role `central`.

Run by the `CTT - Registry Sync` job. Requires a Core REST API instance.

## Arguments

| Argument | Description |
| --- | --- |
| source | `auto` (default), `sheet` or `list`. |
| dry_run | `true` validates and shows the result without writing anything. |
