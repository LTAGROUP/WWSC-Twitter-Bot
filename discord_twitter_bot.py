import discord
from discord.ext import commands, tasks
import tweepy
import json
import re
import os
import logging
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import asyncio
from collections import deque
from dataclasses import dataclass, field
try:
    import requests
    from requests.exceptions import ConnectionError as RequestsConnectionError
except ImportError:
    RequestsConnectionError = ConnectionError

# Multi-tenant imports
try:
    from db import BotDatabase
    from encryption import decrypt as decrypt_credential
    MULTI_TENANT = True
except ImportError:
    MULTI_TENANT = False

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


class EmbedParser:
    """Parses Discord embeds and converts them to natural-sounding tweets"""
    
    # Common field name variations for different data points
    FIELD_MAPPINGS = {
        'product_name': ['product', 'product name', 'name', 'title', 'item'],
        'link': ['link', 'url', 'product link', 'buy link', 'purchase link'],
        'sku': ['sku', 'product id', 'id', 'item number'],
        'price': ['price', 'cost', 'msrp', 'retail price'],
        'stock': ['stock', 'quantity', 'qty', 'available', 'in stock'],
        'limit': ['limit', 'order limit', 'max quantity', 'max order', 'per order'],
        'color': ['color', 'colour', 'colorway', 'variant'],
        'size': ['size', 'sizes', 'available sizes'],
        'retailer': ['retailer', 'store', 'seller', 'site'],
        'release_date': ['release date', 'drop date', 'available', 'launches'],
        'category': ['category', 'type', 'product type'],
    }
    
    # Tweet templates with variations for natural feel
    TWEET_TEMPLATES = [
        # Template 1: Casual alert style
        "🚨 {product_name} just restocked!{color_info}{size_info}\n💰 {price}{stock_info}{limit_info}\n🔗 {link}",
        
        # Template 2: Direct and informative
        "{product_name} is back in stock!{color_info}{size_info}\n\nPrice: {price}{stock_info}{limit_info}\n\n{link}",
        
        # Template 3: Excited announcement
        "⚡ RESTOCK ALERT ⚡\n\n{product_name}{color_info}{size_info}\n{price}{stock_info}{limit_info}\n\n👉 {link}",
        
        # Template 4: Clean and simple
        "✨ {product_name}{color_info}{size_info}\n\n{price}{stock_info}{limit_info}\n\nShop now: {link}",
        
        # Template 5: Urgency focused
        "🔥 {product_name} BACK IN STOCK{color_info}{size_info}\n\n💵 {price}{stock_info}{limit_info}\n\nGrab yours: {link}",
    ]
    
    def __init__(self, config: Dict = None):
        """Initialize embed parser with optional configuration"""
        self.config = config or {}
        self.template_index = 0  # Rotate through templates for variety
        
        # Allow custom templates in config
        self.custom_templates = self.config.get('tweet_templates', [])
        
        # Configuration options
        self.include_hashtags = self.config.get('include_hashtags', False)
        self.default_hashtags = self.config.get('default_hashtags', ['restock', 'instock'])
        self.shorten_links = self.config.get('shorten_links', False)  # Could integrate bit.ly later
        
        logger.info("Embed parser initialized")
    
    @staticmethod
    def _extract_url(value: str) -> str:
        """Extract a plain URL from a string that may contain Discord markdown links like [text](url)"""
        # Match markdown link [text](url)
        md_match = re.search(r'\[.*?\]\((https?://[^\s\)]+)\)', value)
        if md_match:
            return md_match.group(1)
        # Fall back to bare URL
        url_match = re.search(r'https?://\S+', value)
        if url_match:
            return url_match.group(0)
        return value

    def parse_embed(self, embed: discord.Embed) -> Dict[str, str]:
        """Extract structured data from a Discord embed"""
        data = {}

        # Get title as product name if available
        if embed.title:
            data['product_name'] = embed.title
            logger.debug(f"Found product name in title: {embed.title}")

        # Get URL from embed if available
        if embed.url:
            data['link'] = embed.url
            logger.debug(f"Found link in embed URL: {embed.url}")

        # Parse fields
        for field in embed.fields:
            field_name = field.name.lower().strip()
            field_value = field.value.strip()

            # Match field name to our known categories
            for category, variations in self.FIELD_MAPPINGS.items():
                if any(var in field_name for var in variations):
                    # Never overwrite the embed title URL with retailer link fields
                    if category == 'link' and 'link' in data:
                        logger.debug(f"Skipping field '{field.name}' — embed URL already set")
                        break
                    # For link fields, strip markdown formatting to get a plain URL
                    if category == 'link':
                        field_value = self._extract_url(field_value)
                    data[category] = field_value
                    logger.debug(f"Matched field '{field.name}' to category '{category}': {field_value}")
                    break

        # Parse description for additional info if fields are sparse
        if embed.description and len(data) < 3:
            # Try to extract link from description
            url_match = re.search(r'https?://[^\s\)]+', embed.description)
            if url_match and 'link' not in data:
                data['link'] = url_match.group(0)
                logger.debug(f"Extracted link from description: {data['link']}")

        # Parse footer for additional metadata
        if embed.footer and embed.footer.text:
            footer_text = embed.footer.text.lower()
            # Check for stock info in footer
            if 'stock' in footer_text or 'available' in footer_text:
                data['stock'] = embed.footer.text

        logger.info(f"Parsed embed data: {list(data.keys())}")
        return data
    
    def format_price(self, price_str: str) -> str:
        """Clean up price formatting"""
        # Remove extra whitespace
        price_str = price_str.strip()
        
        # Ensure it starts with currency symbol
        if not price_str.startswith('$') and not price_str.startswith('€') and not price_str.startswith('£'):
            # Try to detect if it's just a number
            if re.match(r'^\d+\.?\d*$', price_str):
                price_str = f"${price_str}"
        
        return price_str
    
    def format_stock_info(self, stock_str: str) -> str:
        """Format stock information naturally"""
        stock_str = stock_str.lower().strip()
        
        # If it's just a number
        if stock_str.isdigit():
            qty = int(stock_str)
            if qty < 10:
                return f" • Only {qty} left!"
            elif qty < 50:
                return f" • {qty} available"
            else:
                return ""  # Don't mention if plenty in stock
        
        # If it contains "in stock" or similar
        if 'in stock' in stock_str or 'available' in stock_str:
            return " • In Stock"
        
        # If it says limited
        if 'limited' in stock_str or 'low' in stock_str:
            return " • Limited Stock!"
        
        return f" • {stock_str.title()}"
    
    def format_limit_info(self, limit_str: str) -> str:
        """Format order limit information"""
        limit_str = limit_str.strip()
        
        # If it's just a number
        if limit_str.isdigit():
            return f"\n📦 Limit {limit_str} per order"
        
        # If it already says "per order" or similar
        if 'per' in limit_str.lower():
            return f"\n📦 {limit_str}"
        
        return f"\n📦 Limit: {limit_str}"
    
    def get_embed_image_url(self, embed: discord.Embed) -> Optional[str]:
        """Extract image URL from embed (checks image then thumbnail)"""
        if embed.image and embed.image.url:
            return embed.image.url
        if embed.thumbnail and embed.thumbnail.url:
            return embed.thumbnail.url
        return None

    def create_tweet_from_embed(self, embed: discord.Embed) -> str:
        """Convert embed to a tweet: Name, QTY (if available), Limit (if available), Price, Link"""
        data = self.parse_embed(embed)

        # Name
        name = data.get('product_name') or embed.title or "Product"

        # QTY available (optional)
        qty_line = ""
        if 'stock' in data:
            stock_val = data['stock'].strip()
            if stock_val:
                qty_line = f"Qty: {stock_val}"

        # Order limit (optional)
        limit_line = ""
        if 'limit' in data:
            limit_val = data['limit'].strip()
            if limit_val:
                limit_line = f"Limit: {limit_val}"

        # Price (optional)
        price_line = ""
        if 'price' in data:
            price_line = self.format_price(data['price'])

        # Link — plain URL only, no markdown, no extra retailer links
        link = data.get('link', '')
        if not link:
            logger.warning("No link found in embed")

        # Build tweet in order: Name, QTY, Limit, Price, Link, #ad
        lines = [name]
        if qty_line:
            lines.append(qty_line)
        if limit_line:
            lines.append(limit_line)
        if price_line:
            lines.append(price_line)
        if link:
            lines.append(link)
        lines.append("#ad")

        tweet = "\n".join(lines)

        # Truncate to 280 chars if needed, always preserving link and #ad at the end
        if len(tweet) > 280:
            if link:
                # Reserve space for \nlink\n#ad
                suffix = "\n" + link + "\n#ad"
                max_body = 280 - len(suffix)
                body = "\n".join(lines[:-2])  # Everything before link and #ad
                if len(body) > max_body:
                    body = body[:max_body - 1] + "…"
                tweet = body + suffix
            else:
                # Reserve space for \n#ad
                suffix = "\n#ad"
                max_body = 280 - len(suffix)
                body = "\n".join(lines[:-1])  # Everything before #ad
                if len(body) > max_body:
                    body = body[:max_body - 1] + "…"
                tweet = body + suffix

        logger.info(f"Created tweet ({len(tweet)} chars): {tweet[:100]}...")
        return tweet
    
    def create_tweet_from_text(self, text: str) -> str:
        """Handle regular text messages (passthrough with minor cleanup)"""
        # Return cleaned text as-is - truncation happens at post time
        return text.strip()


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
        self.require_embeds = config.get('require_embeds', False)  # New option
        
        logger.info(f"Message filter initialized: enabled={self.enabled}, min_length={self.min_length}, max_length={self.max_length}")
        logger.info(f"Filter settings: required_keywords={self.required_keywords}, excluded_keywords={self.excluded_keywords}")
    
    def should_post(self, message: discord.Message) -> tuple[bool, Optional[str]]:
        """
        Determine if a message should be posted to Twitter
        Returns (should_post: bool, reason: str)
        """
        logger.debug(f"Filtering message from {message.author.name} (ID: {message.author.id})")
        
        # Log if message has embeds
        if message.embeds:
            logger.debug(f"Message has {len(message.embeds)} embed(s)")
        
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
        
        # Check if embeds are required
        if self.require_embeds and not message.embeds:
            logger.debug("Message rejected: no embeds found")
            return False, "No embeds found"
        
        # For messages with embeds, check the embed content
        content_to_check = message.content
        if message.embeds:
            # Check embed title, description, and fields for keywords
            for embed in message.embeds:
                if embed.title:
                    content_to_check += " " + embed.title
                if embed.description:
                    content_to_check += " " + embed.description
                for field in embed.fields:
                    content_to_check += " " + field.name + " " + field.value
        
        # Check message length (only for text messages, embeds handled separately)
        if not message.embeds:
            content_length = len(message.content)
            if content_length < self.min_length:
                logger.debug(f"Message rejected: too short ({content_length} < {self.min_length})")
                return False, f"Message too short ({content_length} < {self.min_length})"
            
            if content_length > self.max_length:
                logger.debug(f"Message rejected: too long ({content_length} > {self.max_length})")
                return False, f"Message too long ({content_length} > {self.max_length})"
        
        # Check required keywords
        if self.required_keywords:
            content_lower = content_to_check.lower()
            if not any(keyword.lower() in content_lower for keyword in self.required_keywords):
                logger.debug(f"Message rejected: missing required keywords {self.required_keywords}")
                return False, "Missing required keywords"
        
        # Check excluded keywords
        if self.excluded_keywords:
            content_lower = content_to_check.lower()
            if any(keyword.lower() in content_lower for keyword in self.excluded_keywords):
                logger.debug(f"Message rejected: contains excluded keywords")
                return False, "Contains excluded keywords"
        
        # Check attachments requirement
        if self.require_attachments and not message.attachments:
            logger.debug(f"Message rejected: no attachments found")
            return False, "No attachments found"
        
        # Check custom regex
        if self.custom_regex:
            if not re.search(self.custom_regex, content_to_check):
                logger.debug(f"Message rejected: doesn't match regex {self.custom_regex}")
                return False, "Does not match custom regex"
        
        logger.info(f"Message from {message.author.name} passed all filters")
        return True, "Passed all filters"


def _extract_tweepy_error_details(e: Exception) -> str:
    """Extract detailed error info from a tweepy exception for logging."""
    details = []
    if hasattr(e, 'response') and e.response is not None:
        try:
            details.append(f"response_body={e.response.text}")
        except Exception:
            pass
        try:
            details.append(f"url={e.response.url}")
        except Exception:
            pass
    if hasattr(e, 'api_codes') and e.api_codes:
        details.append(f"api_codes={e.api_codes}")
    if hasattr(e, 'api_messages') and e.api_messages:
        details.append(f"api_messages={e.api_messages}")
    return ' | '.join(details) if details else 'no additional details'


@dataclass
class ChannelSetup:
    """Configuration for a single monitored channel."""
    config_id: str                  # Supabase channel_config UUID
    channel_id: int                 # Discord channel ID
    guild_id: int                   # Discord guild ID
    twitter_client: tweepy.Client
    twitter_creds: Dict[str, str]   # For v1 media upload
    rate_limiter: TwitterRateLimiter
    message_filter: MessageFilter
    embed_parser: EmbedParser
    twitter_account_name: str = 'unknown'
    char_limit: int = 280
    log_channel_id: Optional[int] = None


class DiscordTwitterBot(commands.Bot):
    """Multi-tenant bot class that bridges Discord and Twitter for multiple guilds/channels"""

    def __init__(self, config_path: str = 'config.json'):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True

        super().__init__(command_prefix='!tw_', intents=intents)

        logger.info("Initializing Discord-Twitter Bot")

        # Multi-tenant mode: load from Supabase
        self.multi_tenant = MULTI_TENANT and os.getenv('SUPABASE_URL')

        # Channel configs keyed by Discord channel_id (int)
        self.channel_setups: Dict[int, ChannelSetup] = {}

        # Deduplication: track recently processed message IDs
        self._processed_message_ids: set = set()

        # Legacy single-tenant fallback
        self.config = {}
        self.twitter_client = None
        self.embed_parser = None
        self.message_filter = None
        self.rate_limiter = None
        self.monitored_channel_id = None
        self.log_channel_id = None
        self.config_path = config_path
        self.db: Optional[BotDatabase] = None

        if self.multi_tenant:
            logger.info("Multi-tenant mode enabled (Supabase)")
            self.db = BotDatabase()
            self._load_configs_from_db()
        else:
            logger.info("Single-tenant mode (legacy env vars)")
            self._init_single_tenant(config_path)

        logger.info("Bot initialization complete")

    def _init_single_tenant(self, config_path: str):
        """Legacy single-tenant initialization from env vars + config.json"""
        logger.info(f"Loading configuration from {config_path}")
        try:
            with open(config_path, 'r') as f:
                file_config = json.load(f)
            logger.info("Configuration file loaded successfully")
        except Exception as e:
            logger.error(f"Error loading configuration file: {e}")
            raise

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
            'filters': file_config.get('filters', {}),
            'embed_settings': file_config.get('embed_settings', {})
        }

        logger.info(f"Discord channel ID: {self.config['discord_channel_id']}")
        logger.info(f"Twitter API Key present: {bool(self.config['twitter']['api_key'])}")

        self.twitter_client = self._init_twitter()
        self.embed_parser = EmbedParser(self.config.get('embed_settings', {}))
        self.message_filter = MessageFilter(self.config.get('filters', {}))
        self.rate_limiter = TwitterRateLimiter(
            max_posts_per_hour=self.config.get('rate_limits', {}).get('hourly', 50),
            max_posts_per_day=self.config.get('rate_limits', {}).get('daily', 100)
        )
        self.monitored_channel_id = self.config.get('discord_channel_id')
        self.log_channel_id = self.config.get('log_channel_id')

    def _load_configs_from_db(self):
        """Load all channel configurations from Supabase."""
        if not self.db:
            return

        configs = self.db.load_all_configs()
        logger.info(f"Loaded {len(configs)} channel configs from Supabase")

        new_setups: Dict[int, ChannelSetup] = {}

        for cfg in configs:
            try:
                twitter_acc = cfg.get('twitter_accounts')
                if not twitter_acc:
                    logger.warning(f"Channel config {cfg['id']} has no Twitter account, skipping")
                    continue

                # Decrypt Twitter credentials
                creds = {
                    'api_key': decrypt_credential(twitter_acc['twitter_api_key']),
                    'api_secret': decrypt_credential(twitter_acc['twitter_api_secret']),
                    'bearer_token': decrypt_credential(twitter_acc['twitter_bearer_token']),
                    'access_token': decrypt_credential(twitter_acc['twitter_access_token']),
                    'access_token_secret': decrypt_credential(twitter_acc['twitter_access_token_secret']),
                }

                # Create tweepy client for this Twitter account
                client = tweepy.Client(
                    bearer_token=creds['bearer_token'],
                    consumer_key=creds['api_key'],
                    consumer_secret=creds['api_secret'],
                    access_token=creds['access_token'],
                    access_token_secret=creds['access_token_secret']
                )

                # Build filter config from DB fields
                filter_config = {
                    'enabled': cfg.get('filter_enabled', True),
                    'min_length': cfg.get('filter_min_length', 0),
                    'max_length': cfg.get('filter_max_length', 10000),
                    'required_keywords': cfg.get('filter_required_keywords', []),
                    'excluded_keywords': cfg.get('filter_excluded_keywords', []),
                    'required_roles': cfg.get('filter_required_roles', []),
                    'allowed_users': cfg.get('filter_allowed_users', []),
                    'require_attachments': cfg.get('filter_require_attachments', False),
                    'exclude_bots': cfg.get('filter_exclude_bots', False),
                    'require_embeds': cfg.get('filter_require_embeds', False),
                    'custom_regex': cfg.get('filter_custom_regex'),
                }

                embed_settings = {
                    'include_hashtags': cfg.get('embed_include_hashtags', False),
                    'default_hashtags': cfg.get('embed_default_hashtags', ['restock', 'instock']),
                    'shorten_links': cfg.get('embed_shorten_links', False),
                    'tweet_templates': cfg.get('embed_tweet_templates', []),
                }

                guild_data = cfg.get('guilds', {})
                guild_discord_id = int(guild_data.get('guild_id', 0)) if guild_data else 0
                log_ch = guild_data.get('log_channel_id') if guild_data else None

                channel_id = int(cfg['channel_id'])

                # Reuse existing rate limiter if channel already exists (preserves counts)
                existing = self.channel_setups.get(channel_id)
                rate_limiter = existing.rate_limiter if existing else TwitterRateLimiter(
                    max_posts_per_hour=cfg.get('rate_limit_hourly', 50),
                    max_posts_per_day=cfg.get('rate_limit_daily', 100)
                )

                setup = ChannelSetup(
                    config_id=cfg['id'],
                    channel_id=channel_id,
                    guild_id=guild_discord_id,
                    twitter_client=client,
                    twitter_creds=creds,
                    rate_limiter=rate_limiter,
                    message_filter=MessageFilter(filter_config),
                    embed_parser=EmbedParser(embed_settings),
                    twitter_account_name=twitter_acc.get('account_name', 'unknown'),
                    char_limit=cfg.get('twitter_char_limit', 280),
                    log_channel_id=int(log_ch) if log_ch else None,
                )

                new_setups[channel_id] = setup
                logger.info(f"Configured channel {channel_id} (guild {guild_discord_id}) → Twitter: {twitter_acc.get('account_name', 'unknown')}")

            except Exception as e:
                logger.error(f"Failed to load config {cfg.get('id', '?')}: {e}", exc_info=True)
                continue

        self.channel_setups = new_setups
        logger.info(f"Active channel setups: {len(self.channel_setups)}")
    
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
            
            # Skip auth tests if environment variable is set (to avoid rate limits)
            skip_auth_test = os.getenv('SKIP_AUTH_TEST', 'false').lower() == 'true'
            
            if skip_auth_test:
                logger.info("Skipping authentication tests (SKIP_AUTH_TEST=true)")
                logger.info("Authentication will be verified on first tweet attempt")
            else:
                # Test 1: Bearer Token auth (read-only)
                logger.info("=" * 60)
                logger.info("AUTHENTICATION TEST 1: Bearer Token (OAuth 2.0)")
                logger.info("=" * 60)
                try:
                    test_client = tweepy.Client(bearer_token=twitter_config.get('bearer_token'))
                    result = test_client.get_user(username='Twitter')
                    if result.data:
                        logger.info(f"✓ Bearer Token works - Read access confirmed")
                    else:
                        logger.warning("⚠ Bearer Token auth unclear")
                except tweepy.errors.TooManyRequests:
                    logger.warning("⚠ Bearer Token test skipped - Twitter rate limit")
                except Exception as e:
                    logger.error(f"✗ Bearer Token FAILED: {e}")
                
                # Test 2: OAuth 1.0a (needed for posting)
                logger.info("")
                logger.info("=" * 60)
                logger.info("AUTHENTICATION TEST 2: OAuth 1.0a (Posting tweets)")
                logger.info("=" * 60)
                try:
                    test_client_oauth = tweepy.Client(
                        consumer_key=twitter_config.get('api_key'),
                        consumer_secret=twitter_config.get('api_secret'),
                        access_token=twitter_config.get('access_token'),
                        access_token_secret=twitter_config.get('access_token_secret')
                    )
                    me = test_client_oauth.get_me()
                    if me.data:
                        logger.info(f"✓ OAuth 1.0a works - Authenticated as @{me.data.username}")
                        logger.info(f"✓ User ID: {me.data.id}")
                        logger.info("✓✓✓ TWITTER CREDENTIALS FULLY WORKING ✓✓✓")
                        logger.info("✓ Bot can post tweets successfully")
                    else:
                        logger.warning("⚠ OAuth 1.0a response unclear")
                except tweepy.errors.TooManyRequests:
                    logger.warning("⚠ OAuth 1.0a test skipped - Twitter rate limit")
                    logger.warning("Credentials will be tested when first tweet is attempted")
                except tweepy.errors.Unauthorized as e:
                    logger.error("=" * 60)
                    logger.error("✗✗✗ OAUTH 1.0a AUTHENTICATION FAILED ✗✗✗")
                    logger.error("=" * 60)
                    logger.error(f"Error: {e}")
                    if hasattr(e, 'response') and e.response:
                        try:
                            logger.error(f"Response: {e.response.text}")
                        except:
                            pass
                    logger.error("")
                    logger.error("THIS IS THE PROBLEM preventing tweet posting!")
                    logger.error("")
                    logger.error("Root cause: Your Access Token or Access Token Secret is invalid")
                    logger.error("")
                    logger.error("SOLUTION (follow exactly):")
                    logger.error("1. Go to: https://developer.twitter.com/en/portal/dashboard")
                    logger.error("2. Click on your app name")
                    logger.error("3. Go to 'Settings' tab")
                    logger.error("4. Scroll to 'User authentication settings'")
                    logger.error("5. Click 'Edit' or 'Set up' if not configured")
                    logger.error("6. Under 'App permissions', select 'Read and Write'")
                    logger.error("7. Fill in any required OAuth fields")
                    logger.error("8. Click 'Save'")
                    logger.error("9. Go to 'Keys and tokens' tab")
                    logger.error("10. Under 'Access Token and Secret', click 'Regenerate'")
                    logger.error("11. Copy the NEW Access Token")
                    logger.error("12. Copy the NEW Access Token Secret")
                    logger.error("13. In Render: Settings → Environment → Edit TWITTER_ACCESS_TOKEN")
                    logger.error("14. In Render: Settings → Environment → Edit TWITTER_ACCESS_TOKEN_SECRET")
                    logger.error("15. Click 'Save Changes' and redeploy")
                    logger.error("")
                    logger.error("IMPORTANT: Old tokens don't get new permissions automatically!")
                    logger.error("You MUST regenerate after changing permissions!")
                    logger.error("=" * 60)
                    raise ValueError("Twitter OAuth 1.0a authentication failed - see logs above for fix")
                except Exception as e:
                    logger.error(f"✗ OAuth 1.0a test error: {type(e).__name__}: {e}")
                    # Don't raise here if it's a rate limit - let the bot start
                    if not isinstance(e, tweepy.errors.TooManyRequests):
                        raise
                
                logger.info("=" * 60)
                logger.info("")
            
            return client
        except ValueError:
            # Re-raise auth failures
            raise
        except Exception as e:
            logger.error(f"Error creating Tweepy client: {e}")
            raise
    
    async def on_ready(self):
        """Called when bot is ready"""
        logger.info(f'{self.user} has connected to Discord!')
        logger.info(f'Bot ID: {self.user.id}')
        logger.info(f'Connected to {len(self.guilds)} guild(s)')

        if self.multi_tenant:
            logger.info(f'Monitoring {len(self.channel_setups)} channel(s) across guilds')
            # Start periodic config refresh
            if not self.refresh_configs.is_running():
                self.refresh_configs.start()
        else:
            logger.info(f'Monitoring channel ID: {self.monitored_channel_id}')

        print(f'{self.user} has connected to Discord!')

        # Send startup messages to log channels
        if self.multi_tenant:
            sent_channels = set()
            for setup in self.channel_setups.values():
                if setup.log_channel_id and setup.log_channel_id not in sent_channels:
                    log_channel = self.get_channel(setup.log_channel_id)
                    if log_channel:
                        await log_channel.send("✅ Discord-Twitter bot is now online! (Multi-tenant mode)")
                        sent_channels.add(setup.log_channel_id)
        elif self.log_channel_id:
            log_channel = self.get_channel(self.log_channel_id)
            if log_channel:
                await log_channel.send("✅ Discord-Twitter bot is now online!")

    @tasks.loop(seconds=60)
    async def refresh_configs(self):
        """Periodically refresh channel configurations from Supabase."""
        try:
            self._load_configs_from_db()
            logger.debug(f"Config refresh: {len(self.channel_setups)} active channels")
        except Exception as e:
            logger.error(f"Config refresh failed: {e}")
    
    async def on_message(self, message: discord.Message):
        """Handle incoming Discord messages"""
        # Ignore messages from the bot itself
        if message.author == self.user:
            return

        # Deduplicate: skip if this message was already handled
        if message.id in self._processed_message_ids:
            return
        self._processed_message_ids.add(message.id)
        if len(self._processed_message_ids) > 1000:
            self._processed_message_ids.clear()

        # Process commands first (works in any channel)
        await self.process_commands(message)

        # Multi-tenant: look up channel setup
        if self.multi_tenant:
            setup = self.channel_setups.get(message.channel.id)
            if not setup:
                return  # Not a monitored channel
            await self._handle_message_for_channel(message, setup)
        else:
            # Legacy single-tenant
            if message.channel.id != self.monitored_channel_id:
                return
            await self._handle_message_legacy(message)

    async def _handle_message_for_channel(self, message: discord.Message, setup: ChannelSetup):
        """Handle a message for a specific multi-tenant channel configuration."""
        logger.info(f"[{setup.config_id[:8]}] Message in channel {setup.channel_id} from {message.author.name}")

        # Check filters
        should_post, reason = setup.message_filter.should_post(message)
        if not should_post:
            logger.info(f"[{setup.config_id[:8]}] Not posted: {reason}")
            return

        # Check rate limits
        if not setup.rate_limiter.can_post():
            status = setup.rate_limiter.get_status()
            logger.warning(f"[{setup.config_id[:8]}] Rate limit reached! H:{status['hourly_remaining']} D:{status['daily_remaining']}")
            await self._log_to_channel(setup.log_channel_id,
                f"⚠️ Rate limit reached for channel <#{setup.channel_id}>")
            return

        # Post to Twitter
        try:
            tweet_text = await self._post_to_twitter_mt(message, setup)
            setup.rate_limiter.record_post()

            # Log to DB
            if self.db:
                tweet_id = None  # Will be set if we can extract it
                self.db.log_tweet(
                    channel_config_id=setup.config_id,
                    tweet_text=tweet_text,
                    tweet_id=tweet_id,
                    discord_message_id=str(message.id),
                    status='posted'
                )

            status = setup.rate_limiter.get_status()
            logger.info(f"[{setup.config_id[:8]}] Posted. H:{status['hourly_remaining']} D:{status['daily_remaining']}")
            await self._log_to_channel(setup.log_channel_id,
                f"✅ Posted to Twitter from {message.author.name}\n"
                f"Preview: {tweet_text[:100]}...")
            await message.add_reaction('🐦')

        except tweepy.errors.Unauthorized as e:
            err_details = _extract_tweepy_error_details(e)
            logger.error(
                f"[{setup.config_id[:8]}] Twitter 401 | "
                f"twitter_account={setup.twitter_account_name} | "
                f"discord_user={message.author.name} (id={message.author.id}) | "
                f"channel={setup.channel_id} | guild={setup.guild_id} | "
                f"operation=create_tweet | error={e} | {err_details}"
            )
            if self.db:
                self.db.log_tweet(setup.config_id, str(e), status='failed',
                    discord_message_id=str(message.id), error_message=str(e))
            await message.add_reaction('❌')
        except tweepy.errors.Forbidden as e:
            err_details = _extract_tweepy_error_details(e)
            logger.error(
                f"[{setup.config_id[:8]}] Twitter 403 | "
                f"twitter_account={setup.twitter_account_name} | "
                f"discord_user={message.author.name} (id={message.author.id}) | "
                f"channel={setup.channel_id} | guild={setup.guild_id} | "
                f"operation=create_tweet | error={e} | {err_details}"
            )
            if self.db:
                self.db.log_tweet(setup.config_id, str(e), status='failed',
                    discord_message_id=str(message.id), error_message=str(e))
            await message.add_reaction('❌')
        except tweepy.errors.TooManyRequests as e:
            err_details = _extract_tweepy_error_details(e)
            logger.error(
                f"[{setup.config_id[:8]}] Twitter rate limit | "
                f"twitter_account={setup.twitter_account_name} | "
                f"discord_user={message.author.name} (id={message.author.id}) | "
                f"channel={setup.channel_id} | guild={setup.guild_id} | "
                f"operation=create_tweet | error={e} | {err_details}"
            )
            if self.db:
                self.db.log_tweet(setup.config_id, str(e), status='rate_limited',
                    discord_message_id=str(message.id), error_message=str(e))
            await message.add_reaction('⚠️')
        except Exception as e:
            logger.error(
                f"[{setup.config_id[:8]}] Error posting | "
                f"twitter_account={setup.twitter_account_name} | "
                f"discord_user={message.author.name} (id={message.author.id}) | "
                f"channel={setup.channel_id} | guild={setup.guild_id} | "
                f"operation=create_tweet | error={e}",
                exc_info=True
            )
            if self.db:
                self.db.log_tweet(setup.config_id, str(e), status='failed',
                    discord_message_id=str(message.id), error_message=str(e))
            await message.add_reaction('❌')

    async def _handle_message_legacy(self, message: discord.Message):
        """Handle a message in legacy single-tenant mode."""
        logger.info(f"New message in monitored channel from {message.author.name}")

        should_post, reason = self.message_filter.should_post(message)
        if not should_post:
            logger.info(f"Message not posted: {reason}")
            await self._log(f"❌ Message from {message.author.name} not posted: {reason}")
            return

        if not self.rate_limiter.can_post():
            status = self.rate_limiter.get_status()
            logger.warning(f"Rate limit reached! Hourly: {status['hourly_remaining']}, Daily: {status['daily_remaining']}")
            await self._log(f"⚠️ Rate limit reached!")
            return

        try:
            tweet_text = await self._post_to_twitter(message)
            self.rate_limiter.record_post()

            status = self.rate_limiter.get_status()
            logger.info(f"Posted. Remaining - H:{status['hourly_remaining']}, D:{status['daily_remaining']}")
            await self._log(
                f"✅ Posted to Twitter from {message.author.name}\n"
                f"Tweet preview: {tweet_text[:100]}...")
            await message.add_reaction('🐦')

        except tweepy.errors.Unauthorized as e:
            err_details = _extract_tweepy_error_details(e)
            logger.error(
                f"Twitter 401 | discord_user={message.author.name} (id={message.author.id}) | "
                f"channel={message.channel.id} | guild={getattr(message.guild, 'id', 'N/A')} | "
                f"operation=create_tweet | error={e} | {err_details}"
            )
            await self._log(f"❌ Twitter Auth Error: {str(e)}")
            await message.add_reaction('❌')
        except tweepy.errors.Forbidden as e:
            err_details = _extract_tweepy_error_details(e)
            logger.error(
                f"Twitter 403 | discord_user={message.author.name} (id={message.author.id}) | "
                f"channel={message.channel.id} | guild={getattr(message.guild, 'id', 'N/A')} | "
                f"operation=create_tweet | error={e} | {err_details}"
            )
            await self._log(f"❌ Twitter Forbidden: {str(e)}")
            await message.add_reaction('❌')
        except tweepy.errors.TooManyRequests as e:
            err_details = _extract_tweepy_error_details(e)
            logger.error(
                f"Twitter rate limit | discord_user={message.author.name} (id={message.author.id}) | "
                f"channel={message.channel.id} | guild={getattr(message.guild, 'id', 'N/A')} | "
                f"operation=create_tweet | error={e} | {err_details}"
            )
            await self._log(f"❌ Twitter Rate Limit: {str(e)}")
            await message.add_reaction('⚠️')
        except Exception as e:
            logger.error(
                f"Error posting | discord_user={message.author.name} (id={message.author.id}) | "
                f"channel={message.channel.id} | guild={getattr(message.guild, 'id', 'N/A')} | "
                f"operation=create_tweet | error={e}",
                exc_info=True
            )
            await self._log(f"❌ Error: {str(e)}")
            await message.add_reaction('❌')
    
    async def _post_to_twitter_mt(self, message: discord.Message, setup: ChannelSetup) -> str:
        """Post message to Twitter using multi-tenant channel setup."""
        TWITTER_CHAR_LIMIT = setup.char_limit

        image_url = None
        if message.embeds:
            embed = message.embeds[0]
            tweet_text = setup.embed_parser.create_tweet_from_embed(embed)
            image_url = setup.embed_parser.get_embed_image_url(embed)
        else:
            tweet_text = setup.embed_parser.create_tweet_from_text(message.content)

        if len(tweet_text) > TWITTER_CHAR_LIMIT:
            tweet_text = tweet_text[:TWITTER_CHAR_LIMIT - 3] + "..."

        # Upload image if present
        media_id = None
        if image_url:
            media_id = await self._upload_image_to_twitter(image_url, setup.twitter_creds)

        # Post with retry
        max_retries = 3
        retry_delay = 5
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2

                kwargs = {"text": tweet_text}
                if media_id:
                    kwargs["media_ids"] = [media_id]

                response = setup.twitter_client.create_tweet(user_auth=True, **kwargs)
                logger.info(f"Tweet posted. Response: {response}")
                return tweet_text

            except (ConnectionResetError, ConnectionError, RequestsConnectionError, tweepy.errors.TwitterServerError) as e:
                if attempt < max_retries - 1:
                    body = getattr(getattr(e, 'response', None), 'text', '') or ''
                    logger.warning(f"Transient error attempt {attempt + 1}/{max_retries}: {e} | body: {body[:300]}")
                    continue
                raise
            except Exception as e:
                error_str = str(e).lower()
                if 'connection' in error_str and ('reset' in error_str or 'aborted' in error_str):
                    if attempt < max_retries - 1:
                        continue
                raise

        return tweet_text

    async def _upload_image_to_twitter(self, image_url: str, twitter_creds: Optional[Dict[str, str]] = None) -> Optional[str]:
        """Download image from URL and upload to Twitter, returning media_id"""
        import tempfile
        import mimetypes
        try:
            logger.info(f"Downloading image: {image_url}")
            resp = requests.get(image_url, timeout=15)
            resp.raise_for_status()

            # Detect file extension from content-type or URL
            content_type = resp.headers.get('content-type', 'image/jpeg').split(';')[0].strip()
            ext = mimetypes.guess_extension(content_type) or '.jpg'
            if ext == '.jpe':
                ext = '.jpg'

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(resp.content)
                tmp_path = tmp.name

            logger.info(f"Uploading image to Twitter ({len(resp.content)} bytes, {content_type})")
            # Use tweepy v1 API for media upload (v2 doesn't support it directly)
            tw = twitter_creds if twitter_creds else self.config.get('twitter', {})
            auth = tweepy.OAuth1UserHandler(
                consumer_key=tw.get('api_key'),
                consumer_secret=tw.get('api_secret'),
                access_token=tw.get('access_token'),
                access_token_secret=tw.get('access_token_secret')
            )
            api_v1 = tweepy.API(auth)
            media = api_v1.media_upload(filename=tmp_path)
            media_id = str(media.media_id)
            logger.info(f"Image uploaded successfully, media_id: {media_id}")

            import os as _os
            _os.unlink(tmp_path)
            return media_id

        except Exception as e:
            err_details = _extract_tweepy_error_details(e)
            logger.warning(
                f"Failed to upload image (tweet will post without it) | "
                f"image_url={image_url} | operation=media_upload | "
                f"error={e} | {err_details}"
            )
            return None

    async def _post_to_twitter(self, message: discord.Message) -> str:
        """Post message content to Twitter, handling both embeds and text"""
        
        # Twitter's hard character limit - read from config, defaults to 280
        # Set to 25000 in config if you have Twitter Blue/X Premium
        TWITTER_CHAR_LIMIT = self.config.get('twitter_char_limit', 280)
        
        image_url = None
        if message.embeds:
            logger.info(f"Processing message with {len(message.embeds)} embed(s)")
            embed = message.embeds[0]
            tweet_text = self.embed_parser.create_tweet_from_embed(embed)
            image_url = self.embed_parser.get_embed_image_url(embed)
        else:
            logger.info("Processing text message")
            tweet_text = self.embed_parser.create_tweet_from_text(message.content)
        
        # Truncate to Twitter's character limit if needed
        if len(tweet_text) > TWITTER_CHAR_LIMIT:
            logger.warning(f"Tweet too long ({len(tweet_text)} chars), truncating to {TWITTER_CHAR_LIMIT}")
            tweet_text = tweet_text[:TWITTER_CHAR_LIMIT - 3] + "..."
        
        logger.info(f"Final tweet text ({len(tweet_text)} chars):\n{tweet_text}")

        # Upload image if present
        media_id = None
        if image_url:
            logger.info(f"Found image in embed: {image_url}")
            media_id = await self._upload_image_to_twitter(image_url)
        
        # Post tweet with retry logic for transient connection errors
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt}/{max_retries - 1} after {retry_delay}s...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # backoff: 5s then 10s
                
                kwargs = {"text": tweet_text}
                if media_id:
                    kwargs["media_ids"] = [media_id]

                response = self.twitter_client.create_tweet(**kwargs)
                logger.info(f"Tweet posted successfully. Response: {response}")
                
                if response.data:
                    tweet_id = response.data.get('id')
                    logger.info(f"Tweet ID: {tweet_id}")
                    logger.info(f"Tweet URL: https://twitter.com/i/web/status/{tweet_id}")
                
                return tweet_text  # Success - exit retry loop
                
            except (ConnectionResetError, ConnectionError, RequestsConnectionError) as e:
                logger.warning(f"Connection error on attempt {attempt + 1}/{max_retries}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Will retry in {retry_delay}s...")
                else:
                    logger.error(f"All {max_retries} attempts failed with connection errors")
                    raise
                    
            except Exception as e:
                # Check if the exception wraps a connection reset (tweepy wraps requests errors)
                error_str = str(e).lower()
                if 'connection' in error_str and ('reset' in error_str or 'aborted' in error_str):
                    logger.warning(f"Wrapped connection error on attempt {attempt + 1}/{max_retries}: {e}")
                    if attempt < max_retries - 1:
                        logger.info(f"Will retry in {retry_delay}s...")
                        continue
                    else:
                        logger.error(f"All {max_retries} attempts failed with connection errors")
                        raise
                # Auth errors, rate limits, etc. - don't retry these
                logger.error(f"Error in create_tweet call: {e}")
                raise
        
        return tweet_text
    
    async def _log(self, message: str):
        """Send log message to log channel (legacy single-tenant)"""
        print(message)
        logger.info(f"Log message: {message}")

        if self.log_channel_id:
            log_channel = self.get_channel(self.log_channel_id)
            if log_channel:
                try:
                    await log_channel.send(message)
                except Exception as e:
                    logger.error(f"Error sending to log channel: {e}")

    async def _log_to_channel(self, channel_id: Optional[int], message: str):
        """Send log message to a specific log channel."""
        logger.info(message)
        if channel_id:
            log_channel = self.get_channel(channel_id)
            if log_channel:
                try:
                    await log_channel.send(message)
                except Exception as e:
                    logger.error(f"Error sending to log channel {channel_id}: {e}")
    
    @commands.command(name='status')
    async def status(self, ctx):
        """Check bot status and rate limits"""
        logger.info(f"Status command invoked by {ctx.author.name}")

        if self.multi_tenant:
            # Show status for all channels in this guild
            guild_channels = {ch_id: s for ch_id, s in self.channel_setups.items()
                              if s.guild_id == ctx.guild.id}

            if not guild_channels:
                await ctx.send("No channels configured for this server. Set up channels at the web portal.")
                return

            embed_msg = discord.Embed(title="Discord-Twitter Bot Status", color=0x1DA1F2)
            embed_msg.add_field(name="Mode", value="Multi-tenant", inline=False)
            embed_msg.add_field(name="Monitored Channels", value=str(len(guild_channels)), inline=False)

            for ch_id, setup in guild_channels.items():
                rl_status = setup.rate_limiter.get_status()
                embed_msg.add_field(
                    name=f"<#{ch_id}>",
                    value=f"Hourly: {rl_status['hourly_remaining']} left\n"
                          f"Daily: {rl_status['daily_remaining']} left\n"
                          f"Filters: {'On' if setup.message_filter.enabled else 'Off'}",
                    inline=True
                )

            await ctx.send(embed=embed_msg)
        else:
            rl_status = self.rate_limiter.get_status()
            embed_msg = discord.Embed(title="Discord-Twitter Bot Status", color=0x1DA1F2)
            embed_msg.add_field(
                name="Rate Limits",
                value=f"Hourly: {rl_status['hourly_remaining']} remaining\n"
                      f"Daily: {rl_status['daily_remaining']} remaining",
                inline=False
            )
            embed_msg.add_field(
                name="Filters",
                value=f"Enabled: {self.message_filter.enabled}\n"
                      f"Require Embeds: {self.message_filter.require_embeds}",
                inline=False
            )
            embed_msg.add_field(
                name="Configuration",
                value=f"Channel: {self.monitored_channel_id}\n"
                      f"Log Channel: {self.log_channel_id or 'Not set'}",
                inline=False
            )
            await ctx.send(embed=embed_msg)
    
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
                self.embeds = []
        
        mock_msg = MockMessage(test_message, ctx.author)
        should_post, reason = self.message_filter.should_post(mock_msg)
        
        if should_post:
            await ctx.send(f"✅ This message would be posted! Reason: {reason}")
        else:
            await ctx.send(f"❌ This message would NOT be posted. Reason: {reason}")
    
    @commands.command(name='test_embed')
    async def test_embed(self, ctx):
        """Test embed parsing on the most recent embed in the channel"""
        logger.info(f"Test embed command invoked by {ctx.author.name}")
        
        # Look for the most recent message with an embed
        async for msg in ctx.channel.history(limit=50):
            if msg.embeds:
                embed = msg.embeds[0]
                tweet_text = self.embed_parser.create_tweet_from_embed(embed)
                
                # Send preview
                preview_embed = discord.Embed(
                    title="Tweet Preview",
                    description=f"```{tweet_text}```",
                    color=0x1DA1F2
                )
                preview_embed.add_field(name="Character Count", value=f"{len(tweet_text)}/280")
                preview_embed.set_footer(text=f"Based on embed from message by {msg.author.name}")
                
                await ctx.send(embed=preview_embed)
                return
        
        await ctx.send("❌ No recent embeds found in this channel!")
    
    @commands.command(name='reload_config')
    @commands.has_permissions(administrator=True)
    async def reload_config(self, ctx):
        """Reload configuration (Admin only). In multi-tenant mode, refreshes from Supabase."""
        logger.info(f"Reload config command invoked by {ctx.author.name}")
        try:
            if self.multi_tenant:
                self._load_configs_from_db()
                guild_channels = sum(1 for s in self.channel_setups.values() if s.guild_id == ctx.guild.id)
                await ctx.send(f"✅ Configuration reloaded from Supabase! {guild_channels} channel(s) active in this server.")
            else:
                with open(self.config_path, 'r') as f:
                    file_config = json.load(f)

                self.config['rate_limits'] = file_config.get('rate_limits', {'hourly': 50, 'daily': 100})
                self.config['filters'] = file_config.get('filters', {})
                self.config['embed_settings'] = file_config.get('embed_settings', {})

                self.message_filter = MessageFilter(self.config.get('filters', {}))
                self.rate_limiter = TwitterRateLimiter(
                    max_posts_per_hour=self.config.get('rate_limits', {}).get('hourly', 50),
                    max_posts_per_day=self.config.get('rate_limits', {}).get('daily', 100)
                )
                self.embed_parser = EmbedParser(self.config.get('embed_settings', {}))

                await ctx.send("✅ Configuration reloaded successfully!")
        except Exception as e:
            logger.error(f"Error reloading config: {e}")
            await ctx.send(f"❌ Error reloading config: {str(e)}")


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("Starting Discord-Twitter Bot")
    logger.info("=" * 60)

    # Determine mode: multi-tenant (Supabase) or single-tenant (env vars)
    multi_tenant = MULTI_TENANT and os.getenv('SUPABASE_URL')

    if multi_tenant:
        logger.info("Mode: MULTI-TENANT (Supabase)")
        required_env_vars = [
            'DISCORD_TOKEN',
            'SUPABASE_URL',
            'SUPABASE_SERVICE_ROLE_KEY',
            'ENCRYPTION_KEY',
        ]
    else:
        logger.info("Mode: SINGLE-TENANT (legacy)")
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

    # Initialize and run bot with retry logic for rate limits
    max_retries = 5
    retry_delay = 60

    for attempt in range(max_retries):
        try:
            bot = DiscordTwitterBot('config.json')

            discord_token = os.getenv('DISCORD_TOKEN')

            logger.info("Starting bot...")
            bot.run(discord_token)
            break

        except discord.errors.HTTPException as e:
            if e.status == 429:
                if attempt < max_retries - 1:
                    logger.warning(f"Discord rate limit hit (attempt {attempt + 1}/{max_retries})")
                    logger.warning(f"Waiting {retry_delay} seconds before retry...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error("Max retries reached. Discord is rate limiting the bot.")
                    raise
            else:
                logger.error(f"Discord HTTP error: {e}")
                raise
        except Exception as e:
            logger.error(f"Fatal error starting bot: {e}", exc_info=True)
            raise


if __name__ == '__main__':
    main()
