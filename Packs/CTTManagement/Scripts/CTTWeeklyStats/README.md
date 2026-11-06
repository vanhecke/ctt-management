Posts a weekly statistics summary of the tenant to the team Slack channel. Run by the
`CTT - Weekly Stats` job every Monday.

It covers new cases and issues by domain and severity, open cases, playbook runs and failures,
the busiest scripts and commands, data ingested per day and the biggest datasets, XQL compute
use, sign-ins, the most active builders, endpoints by status, AI agent use, and the CTT hygiene
issues raised that week.

Set the channel in the `CTT - Config` list (`stats.slack_channel`, optionally `stats.slack_instance`).
It needs a SlackV3 instance. Without a channel, the summary only goes to the War Room.

## Arguments

| Argument | Description |
| --- | --- |
| period_days | Days to report on (default `stats.period_days`, 7). |
| channel | Slack channel; overrides `stats.slack_channel`. |
| send | `false` shows the summary without posting it. |
