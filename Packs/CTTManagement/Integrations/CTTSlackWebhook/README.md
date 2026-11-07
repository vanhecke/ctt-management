Sends one-way messages from the tenant to the CTT Slack channel through a Slack workflow webhook.

The workflow accepts JSON with `action`, `slack_user_id`, `slack_channel_id` and `content`, and supports five actions:

| Action | Effect |
| --- | --- |
| msg_person | Direct message to `slack_user_id` (shown as plain text; links are clickable) |
| msg_person_health_issue | Like msg_person, plus three buttons: **Fixed!** (`fixed_url`), **Not a violation** (`not_violation_url`) and **Open issue** (`issue_url`) |
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

The CTT hygiene DMs use this action once `notify.buttons` is `true` in `CTT - Config`. The Slack
workflow needs a branch for it that sends `content` to `slack_user_id` (like msg_person) with three
link buttons, labels fixed in the workflow:

| Input | Button | Opens |
| --- | --- | --- |
| `fixed_url` | Fixed! | The issue's confirmation page: one more click on Submit answers "Fixed" |
| `not_violation_url` | Not a violation | The same page for the "Not a violation" answer |
| `issue_url` | Open issue | The issue in Cortex |

Every call sends all three (typed workflow inputs reject empty values). The confirmation pages need
no Cortex login; once the issue is closed they show "expired".
