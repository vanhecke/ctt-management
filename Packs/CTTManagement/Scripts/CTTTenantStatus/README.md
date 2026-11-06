Publishes the tenant's status to the CTT Slack channel. Run daily by the `CTT - Tenant Status` job.

It collects open CTT hygiene issues (by guideline and owner), new cases and issues, open cases, playbook runs and failures, the busiest scripts and commands, sign-ins, the most active builders, data ingested per day and the biggest datasets, XQL compute use, endpoints by status and AI agent use. Then, through the `CTT Slack Webhook` integration, it:

- replaces the **Tenant Status** canvas in the CTT channel (`canvas_update`, markdown), and
- sets the channel **topic** to a one-line summary (`channel_update_topic`).

Switch either off with `status.update_canvas` / `status.update_topic` in `CTT - Config`.

## Arguments

| Argument | Description |
| --- | --- |
| period_days | Days of activity to report (default `status.period_days`, 7). |
| send | `false` shows the canvas and topic in the War Room without sending them. |
