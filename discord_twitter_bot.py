import discord
from discord.ext import commands
import tweepy
import json
import re
import os
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
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
    
    def create_tweet_from_embed(self, embed: discord.Embed) -> str:
        """Convert embed to a natural-sounding tweet"""
        data = self.parse_embed(embed)
        
        # Ensure we have minimum required info
        if 'product_name' not in data:
            data['product_name'] = embed.title or "Product"
            logger.warning("No product name found, using default")
        
        if 'link' not in data:
            logger.warning("No link found in embed")
            data['link'] = "Link in bio"  # Fallback
        
        # Format the data components
        product_name = data['product_name']
        
        # Optional components with natural formatting
        color_info = ""
        if 'color' in data:
            color_info = f" • {data['color']}"
        
        size_info = ""
        if 'size' in data:
            size_info = f" • {data['size']}"
        
        price = self.format_price(data.get('price', 'Check site for pricing'))
        
        stock_info = ""
        if 'stock' in data:
            stock_info = self.format_stock_info(data['stock'])
        
        limit_info = ""
        if 'limit' in data:
            limit_info = self.format_limit_info(data['limit'])
        
        link = data['link']
        
        # Select template (use custom if available, otherwise rotate through defaults)
        if self.custom_templates:
            template = self.custom_templates[self.template_index % len(self.custom_templates)]
        else:
            template = self.TWEET_TEMPLATES[self.template_index % len(self.TWEET_TEMPLATES)]
        
        # Increment template index for next time
        self.template_index += 1
        
        # Format the tweet
        tweet = template.format(
            product_name=product_name,
            color_info=color_info,
            size_info=size_info,
            price=price,
            stock_info=stock_info,
            limit_info=limit_info,
            link=link
        )
        
        # Add hashtags if enabled
        if self.include_hashtags:
            hashtags = ' '.join([f'#{tag}' for tag in self.default_hashtags])
            # Only add if we have room
            if len(tweet) + len(hashtags) + 2 <= 280:
                tweet = f"{tweet}\n\n{hashtags}"
        
        # Add retailer info if available and we have room
        if 'retailer' in data and len(tweet) < 240:
            tweet = tweet.replace(link, f"{data['retailer']}: {link}")
        
        logger.info(f"Created tweet ({len(tweet)} chars): {tweet[:100]}...")
        
        return tweet
    
    def create_tweet_from_text(self, text: str) -> str:
        """Handle regular text messages (passthrough with minor cleanup)"""
        # Just clean up the text a bit
        text = text.strip()
        
        # Truncate if needed
        if len(text) > 280:
            text = text[:277] + "..."
        
        return text


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
            'filters': file_config.get('filters', {}),
            'embed_settings': file_config.get('embed_settings', {})
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
        
        # Initialize embed parser
        self.embed_parser = EmbedParser(self.config.get('embed_settings', {}))
        
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
        logger.info(f'Monitoring channel ID: {self.monitored_channel_id}')
        
        print(f'{self.user} has connected to Discord!')
        print(f'Monitoring channel ID: {self.monitored_channel_id}')
        
        # Send startup message to log channel if configured
        if self.log_channel_id:
            log_channel = self.get_channel(self.log_channel_id)
            if log_channel:
                await log_channel.send("✅ Discord-Twitter bot is now online! (Now with embed support)")
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
        if message.embeds:
            logger.info(f"Message contains {len(message.embeds)} embed(s)")
        
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
            logger.info("Attempting to post to Twitter")
            tweet_text = await self._post_to_twitter(message)
            self.rate_limiter.record_post()
            
            status = self.rate_limiter.get_status()
            logger.info(f"Successfully posted to Twitter. Remaining - Hourly: {status['hourly_remaining']}, Daily: {status['daily_remaining']}")
            await self._log(
                f"✅ Posted to Twitter from {message.author.name}\n"
                f"Tweet preview: {tweet_text[:100]}...\n"
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
    
    async def _post_to_twitter(self, message: discord.Message) -> str:
        """Post message content to Twitter, handling both embeds and text"""
        
        # Check if message has embeds
        if message.embeds:
            logger.info(f"Processing message with {len(message.embeds)} embed(s)")
            # Use the first embed
            embed = message.embeds[0]
            tweet_text = self.embed_parser.create_tweet_from_embed(embed)
        else:
            # Regular text message
            logger.info("Processing text message")
            tweet_text = self.embed_parser.create_tweet_from_text(message.content)
        
        # Final truncation safety check
        if len(tweet_text) > 280:
            logger.warning(f"Tweet too long ({len(tweet_text)} chars), truncating to 280")
            tweet_text = tweet_text[:277] + "..."
        
        logger.info(f"Final tweet text ({len(tweet_text)} chars): {tweet_text}")
        
        # Post tweet
        try:
            response = self.twitter_client.create_tweet(text=tweet_text)
            logger.info(f"Tweet posted successfully. Response: {response}")
            
            if response.data:
                tweet_id = response.data.get('id')
                logger.info(f"Tweet ID: {tweet_id}")
                logger.info(f"Tweet URL: https://twitter.com/i/web/status/{tweet_id}")
        except Exception as e:
            logger.error(f"Error in create_tweet call: {e}")
            raise
        
        return tweet_text
    
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
            value=f"Enabled: {self.message_filter.enabled}\n"
                  f"Require Embeds: {self.message_filter.require_embeds}",
            inline=False
        )
        embed.add_field(
            name="Configuration",
            value=f"Channel: {self.monitored_channel_id}\n"
                  f"Log Channel: {self.log_channel_id or 'Not set'}\n"
                  f"Templates: {len(self.embed_parser.custom_templates or self.embed_parser.TWEET_TEMPLATES)}",
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
        """Reload configuration from file (Admin only)"""
        logger.info(f"Reload config command invoked by {ctx.author.name}")
        try:
            with open(self.config_path, 'r') as f:
                file_config = json.load(f)
            
            # Update config (keeping environment variable credentials)
            self.config['rate_limits'] = file_config.get('rate_limits', {'hourly': 50, 'daily': 100})
            self.config['filters'] = file_config.get('filters', {})
            self.config['embed_settings'] = file_config.get('embed_settings', {})
            
            # Reinitialize components
            self.message_filter = MessageFilter(self.config.get('filters', {}))
            self.rate_limiter = TwitterRateLimiter(
                max_posts_per_hour=self.config.get('rate_limits', {}).get('hourly', 50),
                max_posts_per_day=self.config.get('rate_limits', {}).get('daily', 100)
            )
            self.embed_parser = EmbedParser(self.config.get('embed_settings', {}))
            
            logger.info("Configuration reloaded successfully")
            await ctx.send("✅ Configuration reloaded successfully!")
        except Exception as e:
            logger.error(f"Error reloading config: {e}")
            await ctx.send(f"❌ Error reloading config: {str(e)}")


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("Starting Discord-Twitter Bot with Embed Support")
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
    
    # Initialize and run bot with retry logic for rate limits
    max_retries = 5
    retry_delay = 60  # Start with 60 seconds
    
    for attempt in range(max_retries):
        try:
            bot = DiscordTwitterBot('config.json')
            
            # Get Discord token from environment
            discord_token = os.getenv('DISCORD_TOKEN')
            
            logger.info("Starting bot...")
            bot.run(discord_token)
            break  # If successful, exit the loop
            
        except discord.errors.HTTPException as e:
            if e.status == 429:  # Rate limit error
                if attempt < max_retries - 1:
                    logger.warning("=" * 60)
                    logger.warning(f"Discord rate limit hit (attempt {attempt + 1}/{max_retries})")
                    logger.warning(f"Waiting {retry_delay} seconds before retry...")
                    logger.warning("This happens when the bot is restarted too frequently")
                    logger.warning("=" * 60)
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    logger.info(f"Retrying connection (attempt {attempt + 2}/{max_retries})...")
                else:
                    logger.error("=" * 60)
                    logger.error("Max retries reached. Discord is rate limiting the bot.")
                    logger.error("Please wait 15-30 minutes before restarting.")
                    logger.error("=" * 60)
                    raise
            else:
                # Other HTTP error
                logger.error(f"Discord HTTP error: {e}")
                raise
        except Exception as e:
            logger.error(f"Fatal error starting bot: {e}", exc_info=True)
            raise


if __name__ == '__main__':
    main()
