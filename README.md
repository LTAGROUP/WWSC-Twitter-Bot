# Discord to Twitter Auto-Poster

A Discord bot that automatically posts messages from a specific Discord channel to Twitter, with advanced filtering and rate limiting to manage Twitter API usage.

## Features

- ✅ **Automatic posting** from Discord to Twitter
- 🎯 **Advanced filtering system** with multiple criteria
- ⏱️ **Rate limiting** to stay within Twitter API limits
- 📊 **Status monitoring** commands
- 🔧 **Hot-reload** configuration without restarting
- 📝 **Logging** to dedicated Discord channel

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to "Bot" section and create a bot
4. Enable "Message Content Intent" under Privileged Gateway Intents
5. Copy the bot token
6. Invite bot to your server with appropriate permissions:
   - Read Messages/View Channels
   - Send Messages
   - Add Reactions
   - Read Message History

### 3. Get Twitter API Credentials

1. Go to [Twitter Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Create a new project and app
3. Generate API keys and tokens:
   - API Key (Consumer Key)
   - API Secret (Consumer Secret)
   - Access Token
   - Access Token Secret
   - Bearer Token
4. Ensure your app has "Read and Write" permissions

### 4. Configure the Bot

Edit `config.json` with your credentials:

```json
{
  "discord_token": "YOUR_DISCORD_BOT_TOKEN",
  "discord_channel_id": 1234567890123456789,
  "log_channel_id": 1234567890123456789,
  
  "twitter": {
    "api_key": "YOUR_TWITTER_API_KEY",
    "api_secret": "YOUR_TWITTER_API_SECRET",
    "bearer_token": "YOUR_TWITTER_BEARER_TOKEN",
    "access_token": "YOUR_TWITTER_ACCESS_TOKEN",
    "access_token_secret": "YOUR_TWITTER_ACCESS_TOKEN_SECRET"
  },
  
  "rate_limits": {
    "hourly": 50,
    "daily": 100
  },
  
  "filters": {
    "enabled": true,
    "min_length": 10,
    "max_length": 280,
    "required_keywords": [],
    "excluded_keywords": ["draft", "wip", "test"],
    "required_roles": [],
    "allowed_users": [],
    "require_attachments": false,
    "exclude_bots": true,
    "custom_regex": null
  }
}
```

**To get Discord channel IDs:**
1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click on a channel → Copy ID

### 5. Run the Bot

```bash
python discord_twitter_bot.py
```

## Configuration Options

### Rate Limits

Control how many tweets can be posted to avoid hitting Twitter API limits:

- `hourly`: Maximum posts per hour (default: 50)
- `daily`: Maximum posts per day (default: 100)

### Filters

Configure what messages get posted to Twitter:

#### `enabled` (boolean)
- Enable or disable all filtering
- Default: `true`

#### `min_length` (integer)
- Minimum message length in characters
- Default: `10`
- Example: `"min_length": 20` - Only post messages with 20+ characters

#### `max_length` (integer)
- Maximum message length in characters
- Default: `280` (Twitter's limit)
- Messages longer than this will be truncated

#### `required_keywords` (array of strings)
- Messages must contain at least one of these keywords
- Case-insensitive
- Default: `[]` (no requirement)
- Example: `"required_keywords": ["announcement", "news", "update"]`

#### `excluded_keywords` (array of strings)
- Messages containing any of these keywords will be blocked
- Case-insensitive
- Default: `["draft", "wip", "test"]`
- Example: `"excluded_keywords": ["draft", "private", "internal"]`

#### `required_roles` (array of strings)
- Only post messages from users with these Discord roles
- Default: `[]` (all roles allowed)
- Example: `"required_roles": ["Moderator", "Admin", "Content Creator"]`

#### `allowed_users` (array of strings)
- Only post messages from specific Discord user IDs
- Default: `[]` (all users allowed)
- Example: `"allowed_users": ["123456789012345678", "987654321098765432"]`

#### `require_attachments` (boolean)
- Only post messages that have attachments (images, files, etc.)
- Default: `false`

#### `exclude_bots` (boolean)
- Prevent bot messages from being posted
- Default: `true`

#### `custom_regex` (string or null)
- Custom regex pattern for advanced filtering
- Only messages matching this pattern will be posted
- Default: `null`
- Example: `"custom_regex": "^\\[TWEET\\].*"` - Only post messages starting with [TWEET]

## Bot Commands

All commands use the prefix `!tw_`

### `!tw_status`
Check current bot status and rate limit information

**Example:**
```
!tw_status
```

### `!tw_test_filter <message>`
Test if a message would pass the current filters without actually posting

**Example:**
```
!tw_test_filter This is a test announcement
```

### `!tw_reload_config`
Reload configuration from `config.json` without restarting the bot (Admin only)

**Example:**
```
!tw_reload_config
```

## Filter Examples

### Example 1: Announcements Only
Only post messages that contain announcement keywords:

```json
"filters": {
  "enabled": true,
  "min_length": 20,
  "required_keywords": ["announcement", "news", "update", "release"],
  "excluded_keywords": ["draft", "test"],
  "exclude_bots": true
}
```

### Example 2: Specific Users Only
Only post messages from designated content creators:

```json
"filters": {
  "enabled": true,
  "allowed_users": ["123456789012345678", "987654321098765432"],
  "min_length": 10,
  "exclude_bots": true
}
```

### Example 3: Role-Based with Keyword Filter
Only post from users with specific roles and certain keywords:

```json
"filters": {
  "enabled": true,
  "required_roles": ["Social Media Manager", "Marketing"],
  "required_keywords": ["tweet", "share", "announce"],
  "excluded_keywords": ["draft", "wip", "private", "internal"],
  "min_length": 15,
  "max_length": 280
}
```

### Example 4: Tag-Based System
Use custom regex to require a specific tag at the start of messages:

```json
"filters": {
  "enabled": true,
  "custom_regex": "^\\[TWEET\\]",
  "exclude_bots": true
}
```

Users would post: `[TWEET] This message will be posted to Twitter`

### Example 5: Conservative Rate Limiting
Very conservative posting to preserve API limits:

```json
"rate_limits": {
  "hourly": 10,
  "daily": 50
}
```

## How It Works

1. **Message Received**: Bot monitors the configured Discord channel
2. **Filter Check**: Message is checked against all enabled filters
3. **Rate Limit Check**: Verifies posting won't exceed hourly/daily limits
4. **Post to Twitter**: If all checks pass, message is posted to Twitter
5. **Confirmation**: Bot reacts to the Discord message with 🐦 emoji
6. **Logging**: Activity is logged to the configured log channel

## Troubleshooting

### Bot doesn't respond
- Check that Message Content Intent is enabled in Discord Developer Portal
- Verify bot has proper permissions in the channel

### Twitter posting fails
- Verify all Twitter API credentials are correct
- Check that your Twitter app has "Read and Write" permissions
- Ensure you haven't exceeded Twitter's rate limits

### Messages not being posted
- Use `!tw_test_filter <your message>` to see why a message is being filtered
- Check the log channel for detailed filtering reasons
- Verify filters aren't too restrictive

### Rate limits being hit
- Reduce `hourly` and `daily` limits in config
- Add more restrictive filters to reduce qualifying messages
- Check Twitter Developer Portal for your actual API limits

## Advanced Usage

### Multiple Filter Layers
You can combine multiple filter types for precise control:

```json
"filters": {
  "enabled": true,
  "required_roles": ["Approved Poster"],
  "required_keywords": ["#announcement"],
  "excluded_keywords": ["draft", "preview"],
  "min_length": 30,
  "max_length": 250,
  "exclude_bots": true
}
```

This ensures:
- Only users with "Approved Poster" role
- Message contains "#announcement"
- Doesn't contain "draft" or "preview"
- Is between 30-250 characters
- Is not from a bot

## Security Notes

- Never commit your `config.json` with real credentials to version control
- Consider using environment variables for sensitive data
- Regularly rotate your API keys
- Monitor your bot's activity through the log channel

## License

This project is provided as-is for personal or commercial use.
