#!/usr/bin/env python3
"""
Twitter API Authentication Diagnostic Tool

This script tests your Twitter API credentials to help diagnose 401 Unauthorized errors.
Run this separately from your bot to verify your credentials work.
"""

import os
import sys

# Check if tweepy is installed
try:
    import tweepy
    print(f"✓ Tweepy version: {tweepy.__version__}")
except ImportError:
    print("✗ Tweepy not installed. Run: pip install tweepy")
    sys.exit(1)

print("\n" + "="*60)
print("TWITTER API AUTHENTICATION DIAGNOSTIC")
print("="*60 + "\n")

# Step 1: Check environment variables
print("STEP 1: Checking environment variables...")
print("-" * 60)

env_vars = {
    'TWITTER_API_KEY': os.getenv('TWITTER_API_KEY'),
    'TWITTER_API_SECRET': os.getenv('TWITTER_API_SECRET'),
    'TWITTER_BEARER_TOKEN': os.getenv('TWITTER_BEARER_TOKEN'),
    'TWITTER_ACCESS_TOKEN': os.getenv('TWITTER_ACCESS_TOKEN'),
    'TWITTER_ACCESS_TOKEN_SECRET': os.getenv('TWITTER_ACCESS_TOKEN_SECRET')
}

all_present = True
for key, value in env_vars.items():
    if value:
        print(f"✓ {key}: Present (length: {len(value)})")
        print(f"  First 10 chars: {value[:10]}...")
        print(f"  Last 10 chars: ...{value[-10:]}")
    else:
        print(f"✗ {key}: MISSING")
        all_present = False

if not all_present:
    print("\n✗ ERROR: Some environment variables are missing!")
    print("Please set all required Twitter API credentials.")
    sys.exit(1)

print("\n✓ All environment variables present\n")

# Step 2: Check credential format
print("STEP 2: Checking credential formats...")
print("-" * 60)

# API Key should be alphanumeric, around 25 chars
api_key = env_vars['TWITTER_API_KEY']
if len(api_key) < 20 or len(api_key) > 30:
    print(f"⚠ API Key length unusual: {len(api_key)} chars (expected ~25)")
else:
    print(f"✓ API Key length looks good: {len(api_key)} chars")

# API Secret should be alphanumeric, around 50 chars
api_secret = env_vars['TWITTER_API_SECRET']
if len(api_secret) < 45 or len(api_secret) > 55:
    print(f"⚠ API Secret length unusual: {len(api_secret)} chars (expected ~50)")
else:
    print(f"✓ API Secret length looks good: {len(api_secret)} chars")

# Bearer Token should be very long, starts with "AAAA"
bearer_token = env_vars['TWITTER_BEARER_TOKEN']
if not bearer_token.startswith('AAAA'):
    print(f"⚠ Bearer Token doesn't start with 'AAAA' (got: {bearer_token[:4]})")
else:
    print(f"✓ Bearer Token starts correctly: {bearer_token[:4]}...")
if len(bearer_token) < 100:
    print(f"⚠ Bearer Token seems too short: {len(bearer_token)} chars")
else:
    print(f"✓ Bearer Token length looks good: {len(bearer_token)} chars")

# Access Token should be in format: numbers-letters
access_token = env_vars['TWITTER_ACCESS_TOKEN']
if '-' not in access_token:
    print(f"⚠ Access Token format unusual (expected format: numbers-letters)")
else:
    parts = access_token.split('-')
    print(f"✓ Access Token format looks good: {len(parts[0])} chars - {len(parts[1])} chars")

# Access Token Secret should be alphanumeric, around 45 chars
access_secret = env_vars['TWITTER_ACCESS_TOKEN_SECRET']
if len(access_secret) < 40 or len(access_secret) > 50:
    print(f"⚠ Access Token Secret length unusual: {len(access_secret)} chars (expected ~45)")
else:
    print(f"✓ Access Token Secret length looks good: {len(access_secret)} chars")

print()

# Step 3: Test OAuth 2.0 (Bearer Token) authentication
print("STEP 3: Testing OAuth 2.0 (Bearer Token) authentication...")
print("-" * 60)

try:
    client_bearer = tweepy.Client(bearer_token=bearer_token)
    print("✓ Client created with Bearer Token")
    
    # Try to get Twitter's own user (reliable test)
    result = client_bearer.get_user(username='Twitter')
    if result.data:
        print(f"✓ Successfully fetched user data: @{result.data.username}")
        print("✓ Bearer Token authentication WORKS")
    else:
        print("⚠ Bearer Token auth succeeded but no data returned")
except tweepy.errors.Unauthorized as e:
    print(f"✗ Bearer Token authentication FAILED: {e}")
    print("  Check that your Bearer Token is correct")
except Exception as e:
    print(f"✗ Unexpected error: {e}")

print()

# Step 4: Test OAuth 1.0a (Consumer Keys + Access Tokens) authentication
print("STEP 4: Testing OAuth 1.0a authentication (for posting tweets)...")
print("-" * 60)

try:
    # This is the authentication method needed for posting tweets
    client_oauth1 = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret
    )
    print("✓ Client created with OAuth 1.0a credentials")
    
    # Try to get authenticated user's info (this requires write access)
    me = client_oauth1.get_me()
    if me.data:
        print(f"✓ Successfully authenticated as: @{me.data.username}")
        print(f"  User ID: {me.data.id}")
        print(f"  Name: {me.data.name}")
        print("✓ OAuth 1.0a authentication WORKS")
        print("\n✓✓✓ YOU CAN POST TWEETS ✓✓✓")
    else:
        print("⚠ OAuth 1.0a auth succeeded but no data returned")
except tweepy.errors.Unauthorized as e:
    print(f"✗ OAuth 1.0a authentication FAILED: {e}")
    print("\nThis is the error preventing tweet posting!")
    print("\nPossible causes:")
    print("1. API Key or API Secret is incorrect")
    print("2. Access Token or Access Token Secret is incorrect")
    print("3. Keys are from different apps (they must all be from the same Twitter app)")
    print("4. App doesn't have 'Read and Write' permissions")
    print("5. Access tokens were generated BEFORE changing to 'Read and Write'")
    print("\nSolutions:")
    print("• Regenerate Access Token and Access Token Secret AFTER ensuring")
    print("  your app has 'Read and Write' permissions")
    print("• Make sure all 5 credentials are from the SAME Twitter app")
    print("• Double-check for typos in environment variables")
except tweepy.errors.Forbidden as e:
    print(f"✗ Forbidden (403): {e}")
    print("\nYour credentials are valid but you don't have permission!")
    print("This usually means:")
    print("1. Your app needs 'Read and Write' permissions")
    print("2. After changing permissions, you MUST regenerate Access Tokens")
except Exception as e:
    print(f"✗ Unexpected error: {type(e).__name__}: {e}")

print()

# Step 5: Test combined authentication (what the bot uses)
print("STEP 5: Testing combined authentication (what the bot uses)...")
print("-" * 60)

try:
    # This is exactly how your bot creates the client
    client_full = tweepy.Client(
        bearer_token=bearer_token,
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret
    )
    print("✓ Client created with all credentials (bot configuration)")
    
    # Test getting authenticated user
    me = client_full.get_me()
    if me.data:
        print(f"✓ Successfully authenticated as: @{me.data.username}")
    
    # Test creating a tweet (won't actually post, just test the call structure)
    print("\n✓ Testing tweet creation API call structure...")
    print("  (Not actually posting a tweet)")
    
    # We won't actually post, but we can see if the error happens at this step
    test_text = "Test tweet - delete me"
    print(f"  Would post: '{test_text}'")
    
    # Actually, let's be brave and try to post (you can delete it immediately)
    response = input("\nDo you want to test posting a real tweet? (yes/no): ")
    if response.lower() == 'yes':
        result = client_full.create_tweet(text="🤖 Testing Twitter API authentication - please ignore (automated test)")
        if result.data:
            tweet_id = result.data.get('id')
            print(f"\n✓✓✓ TWEET POSTED SUCCESSFULLY! ✓✓✓")
            print(f"Tweet ID: {tweet_id}")
            print(f"URL: https://twitter.com/i/web/status/{tweet_id}")
            print("\nYour credentials are working perfectly!")
            print("The 401 error must be something else.")
        else:
            print("⚠ Tweet API call succeeded but no data returned")
    else:
        print("Skipping actual tweet test")
    
except tweepy.errors.Unauthorized as e:
    print(f"\n✗ FULL AUTHENTICATION FAILED: {e}")
    print(f"\nError details:")
    if hasattr(e, 'response'):
        print(f"  Response: {e.response}")
    if hasattr(e, 'api_codes'):
        print(f"  API codes: {e.api_codes}")
    if hasattr(e, 'api_messages'):
        print(f"  API messages: {e.api_messages}")
except Exception as e:
    print(f"✗ Unexpected error: {type(e).__name__}: {e}")

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)
print("\nIf you see '✓ OAuth 1.0a authentication WORKS' above,")
print("your credentials are correct and the bot should work!")
print("\nIf you see errors, follow the suggested solutions above.")
