Posts a message to the CTT Slack channel through the `CTT Slack Webhook` integration (workflow
action `msg_channel`). Use it from playbooks and scripts that report to the channel, such as the
`CTT - Marketplace Updates` summary.

- The channel is the instance's **Channel ID** unless `channel_id` is given.
- A literal `\n` becomes a line break, so `!CTTSlackPost message="Line one\nLine two"` works from
  the War Room. Scripts and playbooks can pass real line breaks.
- Messages over 3,900 characters are cut, with a note that the full text is in Cortex.

## Arguments

| Argument | Required | Description |
|---|---|---|
| message | yes | The text to post. Plain text; line breaks are kept and URLs are clickable. |
| channel_id | no | Slack channel ID. Defaults to the instance's channel ID. |

## Outputs

| Path | Type | Description |
|---|---|---|
| CTT.SlackPost.channel | String | The channel the message was posted to. |
| CTT.SlackPost.characters | Number | Characters posted. |
