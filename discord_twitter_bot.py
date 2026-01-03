import discord
from discord.ext import commands
import tweepy
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import asyncio
from collections import deque

class TwitterRateLimiter:
    """Manages Twitter API rate limits to prevent exceeding quotas"""
    
    def __init__(self, max_posts_per_hour: int = 50, max_posts_per_day: int = 100):
        self.max_posts_per_hour = max_posts_per_hour
        self.max_posts_per_day = max_posts_per_day
        self.hourly_posts = deque()
        self.daily_posts = deque()
    
    def can_post(self) -> bool:
        """Check if we can post based on rate limits"""
        now = datetime.now()
        
        # Clean old entries
        self._clean_old_entries(now)
        
        # Check limits
        hourly_count = len(self.hourly_posts)
        daily_count = len(self.daily_posts)
        
        return hourly_count < self.max_posts_per_hour and daily_count < self.max_posts_per_day
    
    def record_post(self):
        """Record a new post"""
        now = datetime.now()
        self.hourly_posts.append(now)
        self.daily_posts.append(now)
    
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
    
    def should_post(self, message: discord.Message) -> tuple[bool, Optional[str]]:
        """
        Determine if a message should be posted to Twitter
        Returns (should_post: bool, reason: str)
        """
        if not self.enabled:
            return False, "Filtering disabled"
        
        # Check if message is from a bot
        if self.exclude_bots and message.author.bot:
            return False, "Message from bot"
        
        # Check user whitelist
        if self.allowed_users and str(message.author.id) not in self.allowed_users:
            return False, "User not in allowed list"
        
        # Check roles (if in a guild)
        if self.required_roles and message.guild:
            user_roles = [role.name for role in message.author.roles]
            if not any(role in user_roles for role in self.required_roles):
                return False, "User missing required roles"
        
        # Check message length
        content_length = len(message.content)
        if content_length < self.min_length:
            return False, f"Message too short ({content_length} < {self.min_length})"
        
        if content_length > self.max_length:
            return False, f"Message too long ({content_length} > {self.max_length})"
        
        # Check required keywords
        if self.required_keywords:
            message_lower = message.content.lower()
            if not any(keyword.lower() in message_lower for keyword in self.required_keywords):
                return False, "Missing required keywords"
        
        # Check excluded keywords
        if self.excluded_keywords:
            message_lower = message.content.lower()
            if any(keyword.lower() in message_lower for keyword in self.excluded_keywords):
                return False, "Contains excluded keywords"
        
        # Check attachments requirement
        if self.require_attachments and not message.attachments:
            return False, "No attachments found"
        
        # Check custom regex
        if self.custom_regex:
            if not re.search(self.custom_regex, message.content):
                return False, "Does not match custom regex"
        
        return True, "Passed all filters"


class DiscordTwitterBot(commands.Bot):
    """Main bot class that bridges Discord and Twitter"""
    
    def __init__(self, config_path: str = 'config.json'):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        
        super().__init__(command_prefix='!tw_', intents=intents)
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize Twitter client
        self.twitter_client = self._init_twitter()
        
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
    
    def _init_twitter(self) -> tweepy.Client:
        """Initialize Twitter API client"""
        twitter_config = self.config.get('twitter', {})
        
        return tweepy.Client(
            bearer_token=twitter_config.get('bearer_token'),
            consumer_key=twitter_config.get('api_key'),
            consumer_secret=twitter_config.get('api_secret'),
            access_token=twitter_config.get('access_token'),
            access_token_secret=twitter_config.get('access_token_secret')
        )
    
    async def on_ready(self):
        """Called when bot is ready"""
        print(f'{self.user} has connected to Discord!')
        print(f'Monitoring channel ID: {self.monitored_channel_id}')
        
        # Send startup message to log channel if configured
        if self.log_channel_id:
            log_channel = self.get_channel(self.log_channel_id)
            if log_channel:
                await log_channel.send("✅ Discord-Twitter bot is now online!")
    
    async def on_message(self, message: discord.Message):
        """Handle incoming Discord messages"""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return
        
        # Check if message is from monitored channel
        if message.channel.id != self.monitored_channel_id:
            return
        
        # Process commands first
        await self.process_commands(message)
        
        # Check if message passes filters
        should_post, reason = self.message_filter.should_post(message)
        
        if not should_post:
            await self._log(f"❌ Message from {message.author.name} not posted: {reason}")
            return
        
        # Check rate limits
        if not self.rate_limiter.can_post():
            status = self.rate_limiter.get_status()
            await self._log(
                f"⚠️ Rate limit reached! Hourly: {status['hourly_remaining']}, "
                f"Daily: {status['daily_remaining']}"
            )
            return
        
        # Post to Twitter
        try:
            await self._post_to_twitter(message)
            self.rate_limiter.record_post()
            
            status = self.rate_limiter.get_status()
            await self._log(
                f"✅ Posted to Twitter from {message.author.name}\n"
                f"Remaining - Hourly: {status['hourly_remaining']}, Daily: {status['daily_remaining']}"
            )
            
            # React to the message to confirm posting
            await message.add_reaction('🐦')
            
        except Exception as e:
            await self._log(f"❌ Error posting to Twitter: {str(e)}")
            await message.add_reaction('❌')
    
    async def _post_to_twitter(self, message: discord.Message):
        """Post message content to Twitter"""
        # Prepare tweet text
        tweet_text = message.content
        
        # Truncate if needed (keeping some space for potential added text)
        max_length = 280
        if len(tweet_text) > max_length:
            tweet_text = tweet_text[:max_length-3] + "..."
        
        # Post tweet
        response = self.twitter_client.create_tweet(text=tweet_text)
        
        # You can also handle media attachments here if needed
        # This would require additional Twitter API v2 media upload
    
    async def _log(self, message: str):
        """Send log message to log channel"""
        print(message)  # Always print to console
        
        if self.log_channel_id:
            log_channel = self.get_channel(self.log_channel_id)
            if log_channel:
                await log_channel.send(message)
    
    @commands.command(name='status')
    async def status(self, ctx):
        """Check bot status and rate limits"""
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
        
        await ctx.send(embed=embed)
    
    @commands.command(name='test_filter')
    async def test_filter(self, ctx, *, test_message: str):
        """Test if a message would pass the filters"""
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
        try:
            with open('config.json', 'r') as f:
                self.config = json.load(f)
            
            # Reinitialize filter with new config
            self.message_filter = MessageFilter(self.config.get('filters', {}))
            
            await ctx.send("✅ Configuration reloaded successfully!")
        except Exception as e:
            await ctx.send(f"❌ Error reloading config: {str(e)}")


def main():
    """Main entry point"""
    bot = DiscordTwitterBot('config.json')
    
    # Get Discord token from config
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    bot.run(config['discord_token'])


if __name__ == '__main__':
    main()
