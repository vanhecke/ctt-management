Sends one-way messages from the tenant to the CTT Slack channel through a Slack workflow webhook.

The workflow accepts JSON with `action`, `slack_user_id`, `slack_channel_id` and `content`, and supports four actions:

| Action | Effect |
| --- | --- |
| msg_person | Direct message to `slack_user_id` (shown as plain text; links are clickable) |
| msg_channel | Message to `slack_channel_id` |
| channel_update_topic | Sets the topic of the CTT channel to `content` |
| canvas_update | Replaces the 'Tenant Status' canvas in the CTT channel with `content` |

## Configure

Create one instance with the workflow trigger URL (stored encrypted), the CTT channel ID, and a placeholder Slack member ID. The workflow types its inputs and rejects a call with an empty user or channel ID (`invalid_workflow_input`), so every call carries both; the placeholder is never messaged. **Test** checks the URL format only, because any real call sends a Slack message.

## Commands

### ctt-slack-webhook-send

| Argument | Description |
| --- | --- |
| action | msg_person, msg_channel, channel_update_topic or canvas_update |
| content | The message, topic or canvas content |
| slack_user_id | Slack member ID, for msg_person |
| slack_channel_id | Slack channel ID, for msg_channel |
