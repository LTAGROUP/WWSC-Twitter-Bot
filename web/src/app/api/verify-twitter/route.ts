import { NextRequest, NextResponse } from 'next/server';
import { createHmac, randomBytes } from 'crypto';
import { getSession } from '@/lib/auth';
import { createServerClient } from '@/lib/supabase';
import { decrypt } from '@/lib/encryption';

function buildOAuth1aHeader(
  method: string,
  url: string,
  apiKey: string,
  apiSecret: string,
  accessToken: string,
  accessTokenSecret: string
): string {
  const oauthParams: Record<string, string> = {
    oauth_consumer_key: apiKey,
    oauth_nonce: randomBytes(16).toString('hex'),
    oauth_signature_method: 'HMAC-SHA1',
    oauth_timestamp: Math.floor(Date.now() / 1000).toString(),
    oauth_token: accessToken,
    oauth_version: '1.0',
  };

  const paramString = Object.entries(oauthParams)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`)
    .join('&');

  const signatureBase = [
    method.toUpperCase(),
    encodeURIComponent(url),
    encodeURIComponent(paramString),
  ].join('&');

  const signingKey = `${encodeURIComponent(apiSecret)}&${encodeURIComponent(accessTokenSecret)}`;
  const signature = createHmac('sha1', signingKey).update(signatureBase).digest('base64');

  return (
    'OAuth ' +
    Object.entries({ ...oauthParams, oauth_signature: signature })
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([k, v]) => `${encodeURIComponent(k)}="${encodeURIComponent(v)}"`)
      .join(', ')
  );
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const { accountId } = await req.json();
  if (!accountId) {
    return NextResponse.json({ error: 'accountId required' }, { status: 400 });
  }

  const supabase = createServerClient();

  const { data: account, error } = await supabase
    .from('twitter_accounts')
    .select('*')
    .eq('id', accountId)
    .eq('owner_id', session.userId)
    .single();

  if (error || !account) {
    return NextResponse.json({ error: 'Account not found' }, { status: 404 });
  }

  try {
    const apiKey = await decrypt(account.twitter_api_key);
    const apiSecret = await decrypt(account.twitter_api_secret);
    const accessToken = await decrypt(account.twitter_access_token);
    const accessTokenSecret = await decrypt(account.twitter_access_token_secret);

    const url = 'https://api.twitter.com/1.1/account/verify_credentials.json';
    const authHeader = buildOAuth1aHeader('GET', url, apiKey, apiSecret, accessToken, accessTokenSecret);

    const res = await fetch(url, {
      headers: { Authorization: authHeader },
    });

    if (!res.ok) {
      const errBody = await res.text();
      await supabase
        .from('twitter_accounts')
        .update({ is_valid: false, last_verified_at: new Date().toISOString() })
        .eq('id', accountId);

      return NextResponse.json({
        valid: false,
        error: `Twitter API returned ${res.status}: ${errBody}`,
      });
    }

    const userData = await res.json();

    await supabase
      .from('twitter_accounts')
      .update({ is_valid: true, last_verified_at: new Date().toISOString() })
      .eq('id', accountId);

    return NextResponse.json({
      valid: true,
      twitterUser: { username: userData.screen_name },
    });
  } catch (err) {
    console.error('Twitter verification error:', err);
    return NextResponse.json({
      valid: false,
      error: 'Failed to verify credentials',
    });
  }
}
