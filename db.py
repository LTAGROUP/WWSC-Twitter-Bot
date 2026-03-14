"""
Supabase database client for the multi-tenant Discord Twitter Bot.
Handles loading configurations, logging tweets, and refreshing configs.
"""

import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

try:
    from supabase import create_client, Client
except ImportError:
    raise ImportError("Install supabase-py: pip install supabase")

logger = logging.getLogger('DiscordTwitterBot.DB')


class BotDatabase:
    """Manages all Supabase interactions for the bot."""

    def __init__(self):
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")
        self.client: Client = create_client(url, key)

    def load_all_configs(self) -> List[dict]:
        """Load all enabled channel configurations with joined Twitter accounts and guilds."""
        try:
            response = self.client.table('channel_configs').select(
                '*, guilds(guild_id, guild_name, log_channel_id), '
                'twitter_accounts(id, twitter_api_key, twitter_api_secret, '
                'twitter_bearer_token, twitter_access_token, twitter_access_token_secret, '
                'is_valid, account_name)'
            ).eq('enabled', True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to load configs from Supabase: {e}")
            return []

    def log_tweet(self, channel_config_id: str, tweet_text: str,
                  tweet_id: Optional[str] = None,
                  discord_message_id: Optional[str] = None,
                  status: str = 'posted',
                  error_message: Optional[str] = None) -> None:
        """Log a tweet attempt to the tweet_history table."""
        try:
            self.client.table('tweet_history').insert({
                'channel_config_id': channel_config_id,
                'tweet_text': tweet_text[:5000],  # Truncate very long text
                'tweet_id': tweet_id,
                'discord_message_id': discord_message_id,
                'status': status,
                'error_message': error_message[:1000] if error_message else None,
            }).execute()
        except Exception as e:
            logger.error(f"Failed to log tweet: {e}")

    def get_guild_config(self, guild_id: str) -> Optional[dict]:
        """Get the guild record by Discord guild ID."""
        try:
            response = self.client.table('guilds').select('*').eq(
                'guild_id', guild_id
            ).single().execute()
            return response.data
        except Exception:
            return None

    def get_channel_configs_for_guild(self, guild_discord_id: str) -> List[dict]:
        """Get all channel configs for a specific Discord guild."""
        try:
            # First get the guild UUID
            guild = self.get_guild_config(guild_discord_id)
            if not guild:
                return []

            response = self.client.table('channel_configs').select(
                '*, twitter_accounts(id, twitter_api_key, twitter_api_secret, '
                'twitter_bearer_token, twitter_access_token, twitter_access_token_secret, '
                'is_valid, account_name)'
            ).eq('guild_id', guild['id']).eq('enabled', True).execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to load guild configs: {e}")
            return []
