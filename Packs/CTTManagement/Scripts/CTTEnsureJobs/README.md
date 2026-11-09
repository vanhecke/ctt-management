Creates or updates the CTT jobs from the `CTT - Jobs` list. Uploads of a pack to XSIAM 8.15 skip the
pack's Jobs folder, so run `!CTTEnsureJobs remove_obsolete=true` once after installing or upgrading
the pack. An existing job keeps its id, start date and owner; only its definition is updated.

A job only runs when it has `category: job`, `parent` set to its own id, `endingType` and an owner,
as the web UI sets them. Without them the scheduler accepts the job but drops every run silently
(the job shows a last run time, but there is no run under Jobs > Job Runs). CTTEnsureJobs sets all
four and repairs jobs made by CTTManagement 1.4.0 and earlier.

## Arguments

| Argument | Description |
|---|---|
| dry_run | `true` shows what would change without changing anything. |
| remove_obsolete | `true` also deletes jobs named `CTT - …` that the list no longer defines. |
| owner | Email of the user the jobs run as (a CTT admin). Default: the job's current owner, else the user running the script. |
