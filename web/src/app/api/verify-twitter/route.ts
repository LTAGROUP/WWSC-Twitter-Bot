import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { createServerClient } from '@/lib/supabase';
import { decrypt } from '@/lib/encryption';

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

  // Fetch the encrypted credentials
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
    // Decrypt credentials
    const bearerToken = await decrypt(account.twitter_bearer_token);

    // Test the bearer token by fetching the authenticated user
    const res = await fetch('https://api.twitter.com/2/users/me', {
      headers: { Authorization: `Bearer ${bearerToken}` },
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
      twitterUser: userData.data,
    });
  } catch (err) {
    console.error('Twitter verification error:', err);
    return NextResponse.json({
      valid: false,
      error: 'Failed to verify credentials',
    });
  }
}
