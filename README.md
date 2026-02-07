# Discord to Twitter Auto-Poster

A Discord bot that automatically posts messages from a specific Discord channel to Twitter, with **embed support** for restock alerts, advanced filtering, and rate limiting to manage Twitter API usage.

## Features

- ✅ **Automatic posting** from Discord to Twitter
- 🎨 **Discord embed support** - Converts embeds to natural-sounding tweets
- 🛍️ **Restock alert formatting** - Automatically formats product info (name, price, stock, limit, etc.)
- 🎯 **Advanced filtering system** with multiple criteria
- ⏱️ **Rate limiting** to stay within Twitter API limits
- 📊 **Status monitoring** commands
- 🔧 **Hot-reload** configuration without restarting
- 📝 **Logging** to dedicated Discord channel

## What's New: Embed Support

The bot now automatically detects Discord embeds (like restock alerts) and converts them into natural-sounding tweets! It extracts:

- **Product Name** (from embed title or fields)
- **Link** (from embed URL or fields)
- **Price** (automatically formatted with $ symbol)
- **Stock** (smart formatting: "Only 5 left!", "Limited Stock!", etc.)
- **Order Limit** (formatted as "Limit X per order")
- **Color/Variant** (appended to product name)
- **Size** (appended to product name)
- **Retailer** (added to link when space permits)
- **SKU** (for reference)

### Example Tweet Outputs

Input embed with fields:
```
Product: Nike Air Jordan 1 Retro High
Color: University Blue
Price: $170
Stock: 23
Limit: 2
Link: https://example.com/product
```

Output tweet (rotates between 5 templates for variety):
```
🚨 Nike Air Jordan 1 Retro High just restocked! • University Blue
💰 $170 • 23 available
📦 Limit 2 per order
🔗 https://example.com/product
```

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

Edit `config.json` with your settings:

```json
{
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
    "require_embeds": false,
    "custom_regex": null
  },
  
  "embed_settings": {
    "include_hashtags": false,
    "default_hashtags": ["restock", "instock"],
    "shorten_links": false,
    "tweet_templates": []
  }
}
```

**Set environment variables for credentials:**
```bash
export DISCORD_TOKEN="your_discord_bot_token"
export DISCORD_CHANNEL_ID="1234567890123456789"
export LOG_CHANNEL_ID="1234567890123456789"  # Optional
export TWITTER_API_KEY="your_twitter_api_key"
export TWITTER_API_SECRET="your_twitter_api_secret"
export TWITTER_BEARER_TOKEN="your_twitter_bearer_token"
export TWITTER_ACCESS_TOKEN="your_twitter_access_token"
export TWITTER_ACCESS_TOKEN_SECRET="your_twitter_access_token_secret"
```

**To get Discord channel IDs:**
1. Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
2. Right-click on a channel → Copy ID

### 5. Run the Bot

```bash
python discord_twitter_bot_with_embeds.py
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

#### `require_embeds` (boolean)
- Only post messages that contain embeds
- Perfect for restock alert channels
- Default: `false`

#### `exclude_bots` (boolean)
- Prevent bot messages from being posted
- Set to `false` if your restock alerts come from a bot
- Default: `true`

#### `min_length` / `max_length` (integer)
- For text-only messages (embeds bypass this)
- Default: `10` / `280`

#### `required_keywords` (array of strings)
- Messages must contain at least one of these keywords
- Checked in embed title, description, and fields
- Case-insensitive
- Default: `[]` (no requirement)

#### `excluded_keywords` (array of strings)
- Messages containing any of these keywords will be blocked
- Case-insensitive
- Default: `["draft", "wip", "test"]`

#### `required_roles` (array of strings)
- Only post messages from users with these Discord roles
- Default: `[]` (all roles allowed)

#### `allowed_users` (array of strings)
- Only post messages from specific Discord user IDs
- Default: `[]` (all users allowed)

#### `custom_regex` (string or null)
- Custom regex pattern for advanced filtering
- Default: `null`

### Embed Settings

Customize how embeds are converted to tweets:

#### `include_hashtags` (boolean)
- Add hashtags to the end of tweets
- Only added if there's room (under 280 chars)
- Default: `false`

#### `default_hashtags` (array of strings)
- Hashtags to include when `include_hashtags` is true
- Default: `["restock", "instock"]`

#### `tweet_templates` (array of strings)
- Custom tweet templates (leave empty to use built-in templates)
- Available variables: `{product_name}`, `{color_info}`, `{size_info}`, `{price}`, `{stock_info}`, `{limit_info}`, `{link}`
- Default: `[]` (uses 5 built-in templates that rotate)

**Example custom template:**
```json
"tweet_templates": [
  "🔔 {product_name} ALERT{color_info}\n\n💵 {price}{stock_info}{limit_info}\n\n👉 {link}"
]
```

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

### `!tw_test_embed`
Test embed parsing on the most recent embed in the channel - shows you what the tweet would look like

**Example:**
```
!tw_test_embed
```

### `!tw_reload_config`
Reload configuration from `config.json` without restarting the bot (Admin only)

**Example:**
```
!tw_reload_config
```

## How Embed Parsing Works

The bot intelligently extracts data from Discord embeds:

1. **Field Matching** - Recognizes common field names:
   - Product Name: "product", "name", "title", "item"
   - Link: "link", "url", "buy link"
   - SKU: "sku", "product id"
   - Price: "price", "cost", "msrp"
   - Stock: "stock", "quantity", "available"
   - Limit: "limit", "order limit", "max quantity"
   - Color: "color", "colorway", "variant"
   - Size: "size", "sizes"
   - Retailer: "retailer", "store"

2. **Smart Formatting**:
   - Prices get $ symbol if missing
   - Stock under 10: "Only X left!"
   - Stock 10-50: "X available"
   - Stock over 50: not mentioned
   - Limits formatted as "Limit X per order"

3. **Template Rotation**:
   - 5 different tweet styles to keep feed feeling natural
   - Templates automatically rotate with each post

4. **URL Extraction**:
   - Checks embed URL field
   - Falls back to links in description
   - Ensures every tweet has a way to purchase

## Configuration Examples

### Example 1: Restock Channel (Embeds Only)
Only post embeds from your restock bot:

```json
"filters": {
  "enabled": true,
  "require_embeds": true,
  "exclude_bots": false,
  "excluded_keywords": []
}
```

### Example 2: Manual Announcements (Text Messages)
Only post text messages from moderators:

```json
"filters": {
  "enabled": true,
  "require_embeds": false,
  "required_roles": ["Moderator", "Admin"],
  "min_length": 20,
  "excluded_keywords": ["draft", "test"]
}
```

### Example 3: Mixed Content with Keywords
Post both embeds and text, but only if they contain certain keywords:

```json
"filters": {
  "enabled": true,
  "require_embeds": false,
  "required_keywords": ["restock", "drop", "available now"],
  "exclude_bots": false
}
```

### Example 4: Custom Tweet Template
Use your own tweet format:

```json
"embed_settings": {
  "include_hashtags": true,
  "default_hashtags": ["sneakers", "restock", "kicks"],
  "tweet_templates": [
    "⚡️ LIVE NOW ⚡️\n\n{product_name}{color_info}\n{price}{stock_info}{limit_info}\n\nCop here: {link}"
  ]
}
```

## Troubleshooting

### Bot doesn't respond
- Check that Message Content Intent is enabled in Discord Developer Portal
- Verify bot has proper permissions in the channel

### Twitter posting fails (401 Unauthorized)
- Verify all Twitter API credentials are correct
- Check that your Twitter app has "Read and Write" permissions
- Ensure you haven't exceeded Twitter's rate limits
- Look at the detailed error logs for API error codes

### Embeds not being posted
- Check if `require_embeds` is set correctly
- Use `!tw_test_embed` to see if embed is being parsed
- Verify the bot is monitoring the correct channel
- Check logs for filtering reasons

### Tweets look wrong
- Use `!tw_test_embed` to preview the output
- Adjust `embed_settings` in config
- Create custom `tweet_templates` if needed
- Check if embed fields match expected names

### Rate limits being hit
- Reduce `hourly` and `daily` limits in config
- Add more restrictive filters
- Check Twitter Developer Portal for your actual API limits

## Advanced Usage

### Custom Field Names
If your embeds use non-standard field names, the bot will try to extract links from descriptions as a fallback. You can also add custom templates that work with your specific embed structure.

### Testing Workflow
1. Use `!tw_test_embed` to see how an embed will be converted
2. Adjust `embed_settings` if needed
3. Use `!tw_reload_config` to apply changes
4. Test again without restarting the bot

### Multiple Templates for Variety
The bot rotates through templates to make your Twitter feed feel more natural and less bot-like. You can define multiple custom templates:

```json
"tweet_templates": [
  "🚨 {product_name} RESTOCKED!{color_info}\n💰 {price}{limit_info}\n{link}",
  "⚡ {product_name} back in stock{color_info}\n\nPrice: {price}{stock_info}\n\n{link}",
  "🔥 Live: {product_name}{color_info}\n{price}{limit_info}\n\nGo go go: {link}"
]
```

## Logging

The bot provides comprehensive logging:
- **Console**: All events logged to stdout
- **bot.log file**: Persistent log file for debugging
- **Discord log channel**: Real-time notifications (if configured)

Log levels:
- INFO: Normal operations, successful posts
- WARNING: Rate limits, authentication issues
- ERROR: Failed posts, API errors
- DEBUG: Detailed filtering decisions, embed parsing

## Security Notes

- Never commit your `config.json` with real credentials to version control
- Use environment variables for sensitive data
- Regularly rotate your API keys
- Monitor your bot's activity through the log channel

## License

This project is provided as-is for personal or commercial use.
