import discord
from discord.ext import commands
import tweepy
import json
import re
import os
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
from collections import deque

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger('DiscordTwitterBot')

class TwitterRateLimiter:
    """Manages Twitter API rate limits to prevent exceeding quotas"""
    
    def __init__(self, max_posts_per_hour: int = 50, max_posts_per_day: int = 100):
        self.max_posts_per_hour = max_posts_per_hour
        self.max_posts_per_day = max_posts_per_day
        self.hourly_posts = deque()
        self.daily_posts = deque()
        logger.info(f"Rate limiter initialized: {max_posts_per_hour}/hour, {max_posts_per_day}/day")
    
    def can_post(self) -> bool:
        """Check if we can post based on rate limits"""
        now = datetime.now()
        
        # Clean old entries
        self._clean_old_entries(now)
        
        # Check limits
        hourly_count = len(self.hourly_posts)
        daily_count = len(self.daily_posts)
        
        can_post = hourly_count < self.max_posts_per_hour and daily_count < self.max_posts_per_day
        logger.debug(f"Rate limit check: hourly={hourly_count}/{self.max_posts_per_hour}, daily={daily_count}/{self.max_posts_per_day}, can_post={can_post}")
        
        return can_post
    
    def record_post(self):
        """Record a new post"""
        now = datetime.now()
        self.hourly_posts.append(now)
        self.daily_posts.append(now)
        logger.debug(f"Post recorded. Total: hourly={len(self.hourly_posts)}, daily={len(self.daily_posts)}")
    
    def _clean_old_entries(self, now: datetime):
        """Remove entries older than the time window"""
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        while self.hourly_posts and self.hourly_posts[0] < hour_ago:
            self.hourly_posts.popleft()
        
        while self.daily_posts and self.daily_posts[0] < day_ago:
            self.daily_posts.popleft()
    
    def get_status(self) -> Dict[str, int]:
        """Get current rate limit status"""
        now = datetime.now()
        self._clean_old_entries(now)
        return {
            'hourly_remaining': self.max_posts_per_hour - len(self.hourly_posts),
            'daily_remaining': self.max_posts_per_day - len(self.daily_posts)
        }


class MessageFilter:
    """Handles filtering logic for Discord messages"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get('enabled', True)
        self.min_length = config.get('min_length', 0)
        self.max_length = config.get('max_length', 280)
        self.required_keywords = config.get('required_keywords', [])
        self.excluded_keywords = config.get('excluded_keywords', [])
        self.required_roles = config.get('required_roles', [])
        self.allowed_users = config.get('allowed_users', [])
        self.require_attachments = config.get('require_attachments', False)
        self.exclude_bots = config.get('exclude_bots', True)
        self.custom_regex = config.get('custom_regex', None)
        
        logger.info(f"Message filter initialized: enabled={self.enabled}, min_length={self.min_length}, max_length={self.max_length}")
        logger.info(f"Filter settings: required_keywords={self.required_keywords}, excluded_keywords={self.excluded_keywords}")
    
    def should_post(self, message: discord.Message) -> tuple[bool, Optional[str]]:
        """
        Determine if a message should be posted to Twitter
        Returns (should_post: bool, reason: str)
        """
        logger.debug(f"Filtering message from {message.author.name} (ID: {message.author.id})")
        logger.debug(f"Message content: {message.content[:100]}{'...' if len(message.content) > 100 else ''}")
        
        if not self.enabled:
            logger.debug("Filtering disabled")
            return False, "Filtering disabled"
        
        # Check if message is from a bot
        if self.exclude_bots and message.author.bot:
            logger.debug(f"Message rejected: from bot {message.author.name}")
            return False, "Message from bot"
        
        # Check user whitelist
        if self.allowed_users and str(message.author.id) not in self.allowed_users:
            logger.debug(f"Message rejected: user {message.author.id} not in allowed list {self.allowed_users}")
            return False, "User not in allowed list"
        
        # Check roles (if in a guild)
        if self.required_roles and message.guild:
            user_roles = [role.name for role in message.author.roles]
            if not any(role in user_roles for role in self.required_roles):
                logger.debug(f"Message rejected: user roles {user_roles} don't match required {self.required_roles}")
                return False, "User missing required roles"
        
        # Check message length
        content_length = len(message.content)
        if content_length < self.min_length:
            logger.debug(f"Message rejected: too short ({content_length} < {self.min_length})")
            return False, f"Message too short ({content_length} < {self.min_length})"
        
        if content_length > self.max_length:
            logger.debug(f"Message rejected: too long ({content_length} > {self.max_length})")
            return False, f"Message too long ({content_length} > {self.max_length})"
        
        # Check required keywords
        if self.required_keywords:
            message_lower = message.content.lower()
            if not any(keyword.lower() in message_lower for keyword in self.required_keywords):
                logger.debug(f"Message rejected: missing required keywords {self.required_keywords}")
                return False, "Missing required keywords"
        
        # Check excluded keywords
        if self.excluded_keywords:
            message_lower = message.content.lower()
            if any(keyword.lower() in message_lower for keyword in self.excluded_keywords):
                logger.debug(f"Message rejected: contains excluded keywords")
                return False, "Contains excluded keywords"
        
        # Check attachments requirement
        if self.require_attachments and not message.attachments:
            logger.debug(f"Message rejected: no attachments found")
            return False, "No attachments found"
        
        # Check custom regex
        if self.custom_regex:
            if not re.search(self.custom_regex, message.content):
                logger.debug(f"Message rejected: doesn't match regex {self.custom_regex}")
                return False, "Does not match custom regex"
        
        logger.info(f"Message from {message.author.name} passed all filters")
        return True, "Passed all filters"


class DiscordTwitterBot(commands.Bot):
    """Main bot class that bridges Discord and Twitter"""
    
    def __init__(self, config_path: str = 'config.json'):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        
        super().__init__(command_prefix='!tw_', intents=intents)
        
        logger.info("Initializing Discord-Twitter Bot")
        
        # Load configuration from file (for filters and rate limits)
        logger.info(f"Loading configuration from {config_path}")
        try:
            with open(config_path, 'r') as f:
                file_config = json.load(f)
            logger.info("Configuration file loaded successfully")
        except Exception as e:
            logger.error(f"Error loading configuration file: {e}")
            raise
        
        # Override credentials with environment variables
        self.config = {
            'discord_channel_id': int(os.getenv('DISCORD_CHANNEL_ID', file_config.get('discord_channel_id', 0))),
            'log_channel_id': int(os.getenv('LOG_CHANNEL_ID', file_config.get('log_channel_id', 0))) if os.getenv('LOG_CHANNEL_ID') or file_config.get('log_channel_id') else None,
            'twitter': {
                'api_key': os.getenv('TWITTER_API_KEY'),
                'api_secret': os.getenv('TWITTER_API_SECRET'),
                'bearer_token': os.getenv('TWITTER_BEARER_TOKEN'),
                'access_token': os.getenv('TWITTER_ACCESS_TOKEN'),
                'access_token_secret': os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
            },
            'rate_limits': file_config.get('rate_limits', {'hourly': 50, 'daily': 100}),
            'filters': file_config.get('filters', {})
        }
        
        # Log configuration (without sensitive data)
        logger.info(f"Discord channel ID: {self.config['discord_channel_id']}")
        logger.info(f"Log channel ID: {self.config['log_channel_id']}")
        logger.info(f"Twitter API Key present: {bool(self.config['twitter']['api_key'])}")
        logger.info(f"Twitter API Secret present: {bool(self.config['twitter']['api_secret'])}")
        logger.info(f"Twitter Bearer Token present: {bool(self.config['twitter']['bearer_token'])}")
        logger.info(f"Twitter Access Token present: {bool(self.config['twitter']['access_token'])}")
        logger.info(f"Twitter Access Token Secret present: {bool(self.config['twitter']['access_token_secret'])}")
        
        # Log first/last few characters of credentials for verification (helps debug without exposing full keys)
        if self.config['twitter']['api_key']:
            logger.debug(f"API Key starts with: {self.config['twitter']['api_key'][:5]}... ends with: ...{self.config['twitter']['api_key'][-5:]}")
        if self.config['twitter']['access_token']:
            logger.debug(f"Access Token starts with: {self.config['twitter']['access_token'][:5]}... ends with: ...{self.config['twitter']['access_token'][-5:]}")
        
        # Initialize Twitter client
        logger.info("Initializing Twitter client")
        try:
            self.twitter_client = self._init_twitter()
            logger.info("Twitter client initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Twitter client: {e}")
            raise
        
        # Initialize filter and rate limiter
        self.message_filter = MessageFilter(self.config.get('filters', {}))
        self.rate_limiter = TwitterRateLimiter(
            max_posts_per_hour=self.config.get('rate_limits', {}).get('hourly', 50),
            max_posts_per_day=self.config.get('rate_limits', {}).get('daily', 100)
        )
        
        # Monitored channel
        self.monitored_channel_id = self.config.get('discord_channel_id')
        
        # Logging
        self.log_channel_id = self.config.get('log_channel_id')
        
        # Store config path for reload command
        self.config_path = config_path
        
        logger.info("Bot initialization complete")
    
    def _init_twitter(self) -> tweepy.Client:
        """Initialize Twitter API client"""
        twitter_config = self.config.get('twitter', {})
        
        logger.info("Creating Tweepy client")
        
        # Verify all required credentials are present
        required_creds = ['bearer_token', 'api_key', 'api_secret', 'access_token', 'access_token_secret']
        missing_creds = [cred for cred in required_creds if not twitter_config.get(cred)]
        
        if missing_creds:
            logger.error(f"Missing Twitter credentials: {missing_creds}")
            raise ValueError(f"Missing Twitter credentials: {missing_creds}")
        
        try:
            client = tweepy.Client(
                bearer_token=twitter_config.get('bearer_token'),
                consumer_key=twitter_config.get('api_key'),
                consumer_secret=twitter_config.get('api_secret'),
                access_token=twitter_config.get('access_token'),
                access_token_secret=twitter_config.get('access_token_secret')
            )
            logger.info("Tweepy client created successfully")
            
            # Test the connection by getting the authenticated user
            try:
                me = client.get_me()
                logger.info(f"Successfully authenticated as Twitter user: {me.data.username if me.data else 'Unknown'}")
            except Exception as e:
                logger.warning(f"Could not verify Twitter authentication during initialization: {e}")
                logger.warning("Will attempt to post when messages arrive")
            
            return client
        except Exception as e:
            logger.error(f"Error creating Tweepy client: {e}")
            raise
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot ID: {self.user.id}')
        logger.info(f'Monitoring channel ID: {self.monitored_channel_id}')
        
        print(f'{self.user} has connected to Discord!')
        print(f'Monitoring channel ID: {self.monitored_channel_id}')
        
        # Send startup message to log channel if configured
        if self.log_channel_id:
            log_channel = self.get_channel(self.log_channel_id)
            if log_channel:
                await log_channel.send("✅ Discord-Twitter bot is now online!")
                logger.info(f"Sent startup message to log channel {self.log_channel_id}")
            else:
                logger.warning(f"Could not find log channel with ID {self.log_channel_id}")
    
    async def on_message(self, message: discord.Message):
        """Handle incoming Discord messages"""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
        
        # Check if message is from monitored channel
        if message.channel.id != self.monitored_channel_id:
            return
        
        logger.info(f"New message in monitored channel from {message.author.name} (ID: {message.author.id})")
        
        # Process commands first
        await self.process_commands(message)
        
        # Check if message passes filters
        should_post, reason = self.message_filter.should_post(message)
        
        if not should_post:
            logger.info(f"Message not posted: {reason}")
            await self._log(f"❌ Message from {message.author.name} not posted: {reason}")
            return
        
        # Check rate limits
        if not self.rate_limiter.can_post():
            status = self.rate_limiter.get_status()
            logger.warning(f"Rate limit reached! Hourly: {status['hourly_remaining']}, Daily: {status['daily_remaining']}")
            await self._log(
                f"⚠️ Rate limit reached! Hourly: {status['hourly_remaining']}, "
                f"Daily: {status['daily_remaining']}"
            )
            return
        
        # Post to Twitter
        try:
            logger.info(f"Attempting to post to Twitter: {message.content[:50]}...")
            await self._post_to_twitter(message)
            self.rate_limiter.record_post()
            
            status = self.rate_limiter.get_status()
            logger.info(f"Successfully posted to Twitter. Remaining - Hourly: {status['hourly_remaining']}, Daily: {status['daily_remaining']}")
            await self._log(
                f"✅ Posted to Twitter from {message.author.name}\n"
                f"Remaining - Hourly: {status['hourly_remaining']}, Daily: {status['daily_remaining']}"
            )
            
            # React to the message to confirm posting
            await message.add_reaction('🐦')
            
        except tweepy.errors.Unauthorized as e:
            logger.error(f"Twitter 401 Unauthorized error: {e}")
            logger.error(f"Error response: {e.response}")
            logger.error(f"Error API codes: {e.api_codes if hasattr(e, 'api_codes') else 'N/A'}")
            logger.error(f"Error API messages: {e.api_messages if hasattr(e, 'api_messages') else 'N/A'}")
            await self._log(f"❌ Twitter Authentication Error (401 Unauthorized): {str(e)}\nPlease verify your Twitter API credentials are correct and have write permissions.")
            await message.add_reaction('❌')
        except tweepy.errors.Forbidden as e:
            logger.error(f"Twitter 403 Forbidden error: {e}")
            logger.error(f"Error response: {e.response}")
            await self._log(f"❌ Twitter Forbidden Error (403): {str(e)}\nYour app may not have the correct permissions.")
            await message.add_reaction('❌')
        except tweepy.errors.TooManyRequests as e:
            logger.error(f"Twitter rate limit error: {e}")
            await self._log(f"❌ Twitter Rate Limit Error: {str(e)}")
            await message.add_reaction('⚠️')
        except tweepy.errors.TwitterServerError as e:
            logger.error(f"Twitter server error: {e}")
            await self._log(f"❌ Twitter Server Error: {str(e)}")
            await message.add_reaction('❌')
        except Exception as e:
            logger.error(f"Unexpected error posting to Twitter: {e}", exc_info=True)
            await self._log(f"❌ Error posting to Twitter: {str(e)}")
            await message.add_reaction('❌')
    
    async def _post_to_twitter(self, message: discord.Message):
        """Post message content to Twitter"""
        # Prepare tweet text
        tweet_text = message.content
        
        # Truncate if needed (keeping some space for potential added text)
        max_length = 280
        if len(tweet_text) > max_length:
            logger.debug(f"Truncating tweet from {len(tweet_text)} to {max_length} characters")
            tweet_text = tweet_text[:max_length-3] + "..."
        
        logger.debug(f"Posting tweet: {tweet_text}")
        
        # Post tweet
        try:
            response = self.twitter_client.create_tweet(text=tweet_text)
            logger.info(f"Tweet posted successfully. Response: {response}")
            
            if response.data:
                tweet_id = response.data.get('id')
                logger.info(f"Tweet ID: {tweet_id}")
        except Exception as e:
            logger.error(f"Error in create_tweet call: {e}")
            raise
        
        # You can also handle media attachments here if needed
        # This would require additional Twitter API v2 media upload
    
    async def _log(self, message: str):
        """Send log message to log channel"""
        print(message)  # Always print to console
        logger.info(f"Log message: {message}")
        
        if self.log_channel_id:
            log_channel = self.get_channel(self.log_channel_id)
            if log_channel:
                try:
                    await log_channel.send(message)
                except Exception as e:
                    logger.error(f"Error sending to log channel: {e}")
    
    @commands.command(name='status')
    async def status(self, ctx):
        """Check bot status and rate limits"""
        logger.info(f"Status command invoked by {ctx.author.name}")
        status = self.rate_limiter.get_status()
        
        embed = discord.Embed(title="Discord-Twitter Bot Status", color=0x1DA1F2)
        embed.add_field(
            name="Rate Limits",
            value=f"Hourly: {status['hourly_remaining']} remaining\n"
                  f"Daily: {status['daily_remaining']} remaining",
            inline=False
        )
        embed.add_field(
            name="Filters",
            value=f"Enabled: {self.message_filter.enabled}",
            inline=False
        )
        embed.add_field(
            name="Configuration",
            value=f"Channel: {self.monitored_channel_id}\n"
                  f"Log Channel: {self.log_channel_id or 'Not set'}",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @commands.command(name='test_filter')
    async def test_filter(self, ctx, *, test_message: str):
        """Test if a message would pass the filters"""
        logger.info(f"Test filter command invoked by {ctx.author.name}")
        
        # Create a mock message object
        class MockMessage:
            def __init__(self, content, author, attachments=None):
                self.content = content
                self.author = author
                self.attachments = attachments or []
                self.guild = ctx.guild
        
        mock_msg = MockMessage(test_message, ctx.author)
        should_post, reason = self.message_filter.should_post(mock_msg)
        
        if should_post:
            await ctx.send(f"✅ This message would be posted! Reason: {reason}")
        else:
            await ctx.send(f"❌ This message would NOT be posted. Reason: {reason}")
    
    @commands.command(name='reload_config')
    @commands.has_permissions(administrator=True)
    async def reload_config(self, ctx):
        """Reload configuration from file (Admin only)"""
        logger.info(f"Reload config command invoked by {ctx.author.name}")
        try:
            with open(self.config_path, 'r') as f:
                file_config = json.load(f)
            
            # Update config (keeping environment variable credentials)
            self.config['rate_limits'] = file_config.get('rate_limits', {'hourly': 50, 'daily': 100})
            self.config['filters'] = file_config.get('filters', {})
            
            # Reinitialize filter with new config
            self.message_filter = MessageFilter(self.config.get('filters', {}))
            
            # Reinitialize rate limiter with new limits
            self.rate_limiter = TwitterRateLimiter(
                max_posts_per_hour=self.config.get('rate_limits', {}).get('hourly', 50),
                max_posts_per_day=self.config.get('rate_limits', {}).get('daily', 100)
            )
            
            logger.info("Configuration reloaded successfully")
            await ctx.send("✅ Configuration reloaded successfully!")
        except Exception as e:
            logger.error(f"Error reloading config: {e}")
            await ctx.send(f"❌ Error reloading config: {str(e)}")


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("Starting Discord-Twitter Bot")
    logger.info("=" * 60)
    
    # Check for required environment variables
    required_env_vars = [
        'DISCORD_TOKEN',
        'DISCORD_CHANNEL_ID',
        'TWITTER_API_KEY',
        'TWITTER_API_SECRET',
        'TWITTER_BEARER_TOKEN',
        'TWITTER_ACCESS_TOKEN',
        'TWITTER_ACCESS_TOKEN_SECRET'
    ]
    
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error("Missing required environment variables:")
        for var in missing_vars:
            logger.error(f"  - {var}")
        print("ERROR: Missing required environment variables:")
        for var in missing_vars:
            print(f"  - {var}")
        print("\nPlease set these environment variables before running the bot.")
        return
    
    logger.info("All required environment variables present")
    
    # Initialize and run bot
    try:
        bot = DiscordTwitterBot('config.json')
        
        # Get Discord token from environment
        discord_token = os.getenv('DISCORD_TOKEN')
        
        logger.info("Starting bot...")
        bot.run(discord_token)
    except Exception as e:
        logger.error(f"Fatal error starting bot: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
