Sends one-way messages from the tenant to the CTT Slack channel through a Slack workflow webhook.

The workflow accepts JSON with `action`, `slack_user_id`, `slack_channel_id`, `content`, `fixed_url`, `not_violation_url` and `issue_url`; every call sends all seven (actions without buttons send `-` for the button links). It supports five actions:

| Action | Effect |
| --- | --- |
| msg_person | Direct message to `slack_user_id` (shown as plain text; links are clickable) |
| msg_person_health_issue | Like msg_person, plus three buttons: **Mark as Fixed** (`fixed_url`), **Mark as False Positive** (`not_violation_url`) and **View Issue** (`issue_url`) |
| msg_channel | Message to `slack_channel_id` |
| channel_update_topic | Sets the topic of the CTT channel to `content` |
| canvas_update | Replaces the 'Tenant Status' canvas in the CTT channel with `content` |

## Configure

Create one instance with the workflow trigger URL (stored encrypted), the CTT channel ID, and a placeholder Slack member ID. The workflow types its inputs and rejects a call with an empty user or channel ID (`invalid_workflow_input`), so every call carries both; the placeholder is never messaged. **Test** checks the URL format only, because any real call sends a Slack message.

## Commands

### ctt-slack-webhook-send

| Argument | Description |
| --- | --- |
| action | msg_person, msg_person_health_issue, msg_channel, channel_update_topic or canvas_update |
| content | The message, topic or canvas content |
| slack_user_id | Slack member ID, for msg_person |
| slack_channel_id | Slack channel ID, for msg_channel |
| fixed_url, not_violation_url, issue_url | Button links, for msg_person_health_issue (all three required) |

## Workflow branch for msg_person_health_issue

The CTT hygiene DMs use this action while `notify.buttons` is `true` in `CTT - Config` (the default).
The workflow branch sends `content` to `slack_user_id` (like msg_person) with three link buttons,
labels fixed in the workflow:

| Input | Button | Opens |
| --- | --- | --- |
| `fixed_url` | Mark as Fixed | The issue's confirmation page: one more click on Submit answers "Fixed" |
| `not_violation_url` | Mark as False Positive | The same page for the "False positive" answer |
| `issue_url` | View Issue | The issue in Cortex |

Every call sends all three (typed workflow inputs reject empty values). The confirmation pages need
no Cortex login; once the issue is closed they show "expired".
