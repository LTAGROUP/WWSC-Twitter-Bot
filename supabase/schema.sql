-- WWSC Twitter Bot - Multi-User Database Schema
-- Run this in Supabase SQL Editor to set up all tables

-- Users authenticated via Discord OAuth2
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  discord_id TEXT UNIQUE NOT NULL,
  discord_username TEXT NOT NULL,
  discord_avatar TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Discord servers (guilds) registered with the bot
CREATE TABLE guilds (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  guild_id TEXT UNIQUE NOT NULL,
  guild_name TEXT NOT NULL,
  owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
  log_channel_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Twitter accounts with encrypted credentials
CREATE TABLE twitter_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_id UUID REFERENCES users(id) ON DELETE CASCADE,
  account_name TEXT NOT NULL,
  twitter_api_key TEXT NOT NULL,
  twitter_api_secret TEXT NOT NULL,
  twitter_bearer_token TEXT NOT NULL,
  twitter_access_token TEXT NOT NULL,
  twitter_access_token_secret TEXT NOT NULL,
  is_valid BOOLEAN DEFAULT FALSE,
  last_verified_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Channel-to-Twitter mappings
CREATE TABLE channel_configs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  guild_id UUID REFERENCES guilds(id) ON DELETE CASCADE,
  channel_id TEXT NOT NULL,
  channel_name TEXT,
  twitter_account_id UUID REFERENCES twitter_accounts(id) ON DELETE SET NULL,
  enabled BOOLEAN DEFAULT TRUE,

  -- Filter settings
  filter_enabled BOOLEAN DEFAULT TRUE,
  filter_min_length INT DEFAULT 0,
  filter_max_length INT DEFAULT 10000,
  filter_required_keywords JSONB DEFAULT '[]',
  filter_excluded_keywords JSONB DEFAULT '[]',
  filter_required_roles JSONB DEFAULT '[]',
  filter_allowed_users JSONB DEFAULT '[]',
  filter_require_attachments BOOLEAN DEFAULT FALSE,
  filter_exclude_bots BOOLEAN DEFAULT FALSE,
  filter_require_embeds BOOLEAN DEFAULT FALSE,
  filter_custom_regex TEXT,

  -- Rate limit settings
  rate_limit_hourly INT DEFAULT 50,
  rate_limit_daily INT DEFAULT 100,

  -- Embed settings
  twitter_char_limit INT DEFAULT 280,
  embed_include_hashtags BOOLEAN DEFAULT FALSE,
  embed_default_hashtags JSONB DEFAULT '["restock", "instock"]',
  embed_shorten_links BOOLEAN DEFAULT FALSE,
  embed_tweet_templates JSONB DEFAULT '[]',

  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  UNIQUE(guild_id, channel_id)
);

-- Tweet history log
CREATE TABLE tweet_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_config_id UUID REFERENCES channel_configs(id) ON DELETE CASCADE,
  tweet_text TEXT NOT NULL,
  tweet_id TEXT,
  discord_message_id TEXT,
  status TEXT DEFAULT 'posted',
  error_message TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_guilds_guild_id ON guilds(guild_id);
CREATE INDEX idx_guilds_owner_id ON guilds(owner_id);
CREATE INDEX idx_twitter_accounts_owner_id ON twitter_accounts(owner_id);
CREATE INDEX idx_channel_configs_guild_id ON channel_configs(guild_id);
CREATE INDEX idx_channel_configs_channel_id ON channel_configs(channel_id);
CREATE INDEX idx_channel_configs_twitter_account_id ON channel_configs(twitter_account_id);
CREATE INDEX idx_tweet_history_channel_config_id ON tweet_history(channel_config_id);
CREATE INDEX idx_tweet_history_created_at ON tweet_history(created_at);

-- Row Level Security (RLS)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE guilds ENABLE ROW LEVEL SECURITY;
ALTER TABLE twitter_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE channel_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE tweet_history ENABLE ROW LEVEL SECURITY;

-- RLS Policies: Users can only access their own data
-- The service_role key bypasses RLS (used by the bot)

CREATE POLICY "Users can read own profile"
  ON users FOR SELECT
  USING (discord_id = current_setting('app.current_user_discord_id', true));

CREATE POLICY "Users can update own profile"
  ON users FOR UPDATE
  USING (discord_id = current_setting('app.current_user_discord_id', true));

CREATE POLICY "Users can read own guilds"
  ON guilds FOR SELECT
  USING (owner_id IN (SELECT id FROM users WHERE discord_id = current_setting('app.current_user_discord_id', true)));

CREATE POLICY "Users can manage own guilds"
  ON guilds FOR ALL
  USING (owner_id IN (SELECT id FROM users WHERE discord_id = current_setting('app.current_user_discord_id', true)));

CREATE POLICY "Users can read own Twitter accounts"
  ON twitter_accounts FOR SELECT
  USING (owner_id IN (SELECT id FROM users WHERE discord_id = current_setting('app.current_user_discord_id', true)));

CREATE POLICY "Users can manage own Twitter accounts"
  ON twitter_accounts FOR ALL
  USING (owner_id IN (SELECT id FROM users WHERE discord_id = current_setting('app.current_user_discord_id', true)));

CREATE POLICY "Users can read own channel configs"
  ON channel_configs FOR SELECT
  USING (guild_id IN (SELECT id FROM guilds WHERE owner_id IN (SELECT id FROM users WHERE discord_id = current_setting('app.current_user_discord_id', true))));

CREATE POLICY "Users can manage own channel configs"
  ON channel_configs FOR ALL
  USING (guild_id IN (SELECT id FROM guilds WHERE owner_id IN (SELECT id FROM users WHERE discord_id = current_setting('app.current_user_discord_id', true))));

CREATE POLICY "Users can read own tweet history"
  ON tweet_history FOR SELECT
  USING (channel_config_id IN (
    SELECT cc.id FROM channel_configs cc
    JOIN guilds g ON cc.guild_id = g.id
    WHERE g.owner_id IN (SELECT id FROM users WHERE discord_id = current_setting('app.current_user_discord_id', true))
  ));
